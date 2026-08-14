import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { applyAiPatch, buildIndex } from "../build-index.mjs";

function write(root, rel, content) {
  const path = join(root, rel);
  mkdirSync(join(path, ".."), { recursive: true });
  writeFileSync(path, content, "utf8");
}

function json(root, name) {
  return JSON.parse(readFileSync(join(root, "_workspace", "index", name), "utf8"));
}

export async function test(register, assert) {
  register("deterministic indexer가 심볼·호출·API·SQL 인덱스를 생성한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-"));
    try {
      write(root, "_workspace/indexer-config.json", JSON.stringify({
        init_layout: "monorepo",
        workspace_mode: true,
        workspaces: [
          { id: "backend", path: "backend", kind: "backend", stack: "Spring Boot" },
          { id: "frontend", path: "frontend", kind: "frontend", stack: "TypeScript", calls_backend_api: true },
        ],
      }));
      write(root, "backend/OrderController.java", `package com.acme;
@RequestMapping("/orders")
public class OrderController {
  @Autowired private OrderService service;
  @PostMapping("/{id}/cancel")
  public void cancel() { service.cancel(); }
}
class OrderService {
  @Transactional
  public void cancel() { repository.remove(); }
}
class Repository { public void remove() {} }
`);
      write(root, "backend/OrderMapper.xml", `<mapper namespace="OrderMapper">
  <update id="cancel">UPDATE ORDERS SET STATUS='CANCEL' WHERE ID=#{id}</update>
</mapper>`);
      write(root, "frontend/api.ts", `export async function cancelOrder(id: string) {
  return fetch(\`/orders/\${id}/cancel\`, { method: "POST" });
}`);

      const first = buildIndex({ root, mode: "init", tier: "Standard", config: null });
      assert.ok(first.indexes.includes("symbols"), "symbols index");
      assert.ok(first.indexes.includes("api_contract"), "api contracts index");
      assert.ok(first.indexes.includes("sql_usage"), "sql usage index");
      assert.ok(json(root, "symbols.json").symbols.some((item) => item.id === "com.acme.OrderController"), "OrderController symbol");
      const callGraph = json(root, "call_graph.json");
      assert.ok(callGraph.edges.some((item) => item.type === "call" && item.to.endsWith("OrderService.cancel")), `service.cancel call edge: ${JSON.stringify(callGraph)}`);
      assert.equal(json(root, "api_contract.json").matches.length, 1);
      assert.equal(json(root, "sql_usage.json").sqls[0].id, "OrderMapper.cancel");
      assert.equal(json(root, "_meta.json").init_layout, "monorepo");

      // 2026-08-14부터 파일별 해시 캐시(.index-cache/)를 폐지 — incremental도 매번 전체 재분석한다.
      const second = buildIndex({ root, mode: "incremental", tier: "Standard", config: null });
      assert.equal(second.analyzed, second.files);
      assert.equal(second.reused, 0);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("Lite도 AI 없이 기본 기계 인덱스를 생성한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-lite-"));
    try {
      write(root, "src/simple.ts", "export function hello() { return 'hello'; }\n");
      const result = buildIndex({ root, mode: "init", tier: "Lite", config: null });
      assert.ok(result.indexes.includes("symbols"));
      assert.ok(result.indexes.includes("call_graph"));
      assert.equal(json(root, "_meta.json").tier, "Lite");
      assert.equal(json(root, "_meta.json").init_layout, "single-root");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("Init Scope Gate의 include_paths 밖 소스는 읽지 않는다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-scope-"));
    try {
      write(root, "_workspace/indexer-config.json", JSON.stringify({
        init_layout: "selected-paths",
        include_paths: ["selected"],
        workspace_mode: false,
        workspaces: [{ id: "root", path: "", kind: "backend", stack: "unknown" }],
      }));
      write(root, "selected/Included.ts", "export function included() { return 1; }\n");
      write(root, "outside/Excluded.ts", "export function excluded() { return 2; }\n");
      const result = buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const symbols = json(root, "symbols.json").symbols;
      assert.equal(result.files, 1);
      assert.equal(json(root, "_meta.json").init_layout, "selected-paths");
      assert.ok(symbols.some((item) => item.file === "selected/Included.ts"));
      assert.ok(!symbols.some((item) => item.file === "outside/Excluded.ts"));
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("raw SQL은 완결된 SQL 문장만 추출하고 UI·HTTP·번역 문자열을 제외한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-raw-sql-"));
    try {
      write(root, "src/WebConfig.java", `registry.allowedMethods("GET", "POST", "DELETE");\n`);
      write(root, "src/ui.js", `
const css = "select-router-transition";
const action = "delete-node";
const query = "SELECT ID, STATUS FROM ORDERS WHERE ID = ?";
const mutation = 'UPDATE ORDERS SET STATUS = ? WHERE ID = ?';
`);
      write(root, "src/mock.json", JSON.stringify({ select: "select-one", delete: "Delete", update: "update:" }));
      write(root, "src/data.sql", "INSERT INTO LABELS VALUES ('Delete', 'Select');\n");
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const sqls = json(root, "sql_usage.json").sqls;
      assert.equal(sqls.map((item) => item.type).sort().join(","), "select,update");
      assert.ok(sqls.some((item) => item.tables.includes("ORDERS")));
      assert.ok(sqls.every((item) => ["select", "insert", "update", "delete", "ddl"].includes(item.type)));
      assert.ok(!sqls.some((item) => /WebConfig|mock\.json|data\.sql/.test(item.file)));
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("AI 보강은 전체 JSON 재작성 없이 작은 edge patch만 병합한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-patch-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\nexport function second() { return 2; }\n");
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [{ op: "add_edge", edge: { from: "src.simple.first", to: "src.simple.second", type: "call", confidence: "MEDIUM", evidence: "dynamic dispatch resolved from cited snippet" } }],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 1);
      assert.ok(json(root, "call_graph.json").edges.some((item) => item.origin === "ai-enrichment"));
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("AI 보강 patch는 analyzer 문서형(flat)과 중첩형을 모두 적용한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-patch-flat-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\nexport function second() { return 2; }\n");
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      // agents/analyzer.md가 지시하는 평면 형태. 이전 구현은 이걸 전부 조용히 거부했다.
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [{
          op: "add_edge", from: "src.simple.first", to: "src.simple.second", type: "call",
          file: "src/simple.ts", line: 1, confidence: "HIGH", reason: "호출 인자 타입이 단일 후보를 가리킴",
        }],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 1, `flat patch 적용: ${JSON.stringify(result)}`);
      assert.equal(result.rejected, 0);
      const edge = json(root, "call_graph.json").edges.find((item) => item.origin === "ai-enrichment");
      assert.ok(edge, "ai-enrichment edge");
      assert.equal(edge.evidence, "호출 인자 타입이 단일 후보를 가리킴", "flat form의 reason이 근거로 보존된다");
      assert.equal(json(root, "_meta.json").ai_enrichment.applied, 1);
      // digest는 그래프에서 파생되므로 보강 후 값이 갱신돼야 한다.
      const digest = json(root, "_analysis_input.json").digest;
      assert.ok(digest.hubs.some((item) => item.id === "src.simple.second"), `보강된 허브 반영: ${JSON.stringify(digest.hubs)}`);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("AI 보강 patch가 전부 거부되면 조용히 성공하지 않고 사유를 남긴다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-patch-reject-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\n");
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [
          { op: "add_edge", from: "does.not.Exist", to: "src.simple.first", type: "call" },
          { op: "add_node", id: "src.simple.invented" },
          { op: "add_edge", from: "src.simple.first", to: "src.simple.first", type: "teleport" },
        ],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 0);
      assert.equal(result.rejected, 3, JSON.stringify(result));
      assert.equal(result.rejected_reasons.unknown_from_node, 1);
      assert.equal(result.rejected_reasons.unsupported_op, 1);
      assert.equal(result.rejected_reasons.invalid_edge_type, 1);
      assert.ok(result.rejected_samples.length >= 3, "거부 표본 기록");
      assert.equal(json(root, "_meta.json").ai_enrichment.rejected, 3);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("AI 보강으로 API 엔드포인트·외부 통신에 설명을 추가할 수 있다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-desc-"));
    try {
      write(root, "src/OrderController.java", `package com.acme;
@RequestMapping("/orders")
public class OrderController {
  @PostMapping("/{id}/cancel")
  public void cancel() { }
}
class PaymentGatewayClient {
  RestTemplate restTemplate;
}
`);
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const endpointId = json(root, "api_contract.json").endpoints[0].id;
      const commId = json(root, "external_io.json").communications[0].id;
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [
          { op: "set_endpoint_description", id: endpointId, description: "주문을 취소 처리한다" },
          { op: "set_communication_description", id: commId, description: "결제 게이트웨이에 취소 요청을 전달한다" },
        ],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 2, JSON.stringify(result));
      assert.equal(result.rejected, 0);
      assert.equal(json(root, "api_contract.json").endpoints[0].description, "주문을 취소 처리한다");
      assert.equal(json(root, "external_io.json").communications[0].description, "결제 게이트웨이에 취소 요청을 전달한다");
      assert.equal(json(root, "_meta.json").ai_enrichment.applied, 2);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("설명 보강 오퍼레이션이 존재하지 않는 id를 가리키면 unknown_id로 거부된다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-desc-reject-"));
    try {
      write(root, "src/OrderController.java", `package com.acme;
@RequestMapping("/orders")
public class OrderController {
  @PostMapping("/{id}/cancel")
  public void cancel() { }
}
`);
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [{ op: "set_endpoint_description", id: "does.not.exist", description: "존재하지 않는 엔드포인트" }],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 0);
      assert.equal(result.rejected, 1);
      assert.equal(result.rejected_reasons.unknown_id, 1, JSON.stringify(result));
      assert.equal(json(root, "api_contract.json").endpoints[0].description, undefined, "거부된 항목은 description이 안 생김");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("add_edge와 설명 보강이 섞인 패치도 서로 오염 없이 각자 적용된다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-desc-mixed-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\nexport function second() { return 2; }\n");
      write(root, "src/OrderController.java", `package com.acme;
@RequestMapping("/orders")
public class OrderController {
  @PostMapping("/{id}/cancel")
  public void cancel() { }
}
`);
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const endpointId = json(root, "api_contract.json").endpoints[0].id;
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [
          { op: "add_edge", from: "src.simple.first", to: "src.simple.second", type: "call", confidence: "MEDIUM", evidence: "동적 디스패치" },
          { op: "set_endpoint_description", id: endpointId, description: "주문을 취소 처리한다" },
          { op: "add_node", id: "src.simple.invented" },
        ],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 2, JSON.stringify(result));
      assert.equal(result.rejected, 1);
      assert.equal(result.rejected_reasons.unsupported_op, 1, "add_node는 여전히 unsupported_op로 집계된다");
      assert.ok(json(root, "call_graph.json").edges.some((item) => item.origin === "ai-enrichment"), "call_graph edge 보강은 그대로 동작");
      assert.equal(json(root, "api_contract.json").endpoints[0].description, "주문을 취소 처리한다");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("set_node_note/set_edge_note로 콜 그래프 노드·엣지에 설명을 추가할 수 있다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-note-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\nexport function second() { return 2; }\n");
      write(root, "src/OrderController.java", `package com.acme;
@RequestMapping("/orders")
public class OrderController {
  @Autowired private OrderService service;
  @PostMapping("/{id}/cancel")
  public void cancel() { service.cancel(); }
}
class OrderService {
  public void cancel() { }
}
`);
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const graph = json(root, "call_graph.json");
      const serviceNode = graph.nodes.find((n) => n.id.endsWith("OrderService.cancel"));
      const callEdge = graph.edges.find((e) => e.type === "call" && e.to.endsWith("OrderService.cancel"));
      assert.ok(serviceNode, `OrderService.cancel 노드: ${JSON.stringify(graph.nodes)}`);
      assert.ok(callEdge, `호출 엣지: ${JSON.stringify(graph.edges)}`);
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [
          { op: "set_node_note", id: serviceNode.id, note: "주문 취소 업무 로직을 처리한다" },
          { op: "set_edge_note", from: callEdge.from, to: callEdge.to, type: callEdge.type, note: "취소 요청을 서비스 계층으로 위임한다" },
        ],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 2, JSON.stringify(result));
      assert.equal(result.rejected, 0);
      const updated = json(root, "call_graph.json");
      assert.equal(updated.nodes.find((n) => n.id === serviceNode.id).note, "주문 취소 업무 로직을 처리한다");
      const updatedEdge = updated.edges.find((e) => e.from === callEdge.from && e.to === callEdge.to && e.type === callEdge.type);
      assert.equal(updatedEdge.note, "취소 요청을 서비스 계층으로 위임한다");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("set_node_note/set_edge_note가 존재하지 않는 대상을 가리키면 거부된다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-note-reject-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\n");
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [
          { op: "set_node_note", id: "does.not.exist", note: "존재하지 않음" },
          { op: "set_edge_note", from: "does.not.exist", to: "src.simple.first", type: "call", note: "존재하지 않는 엣지" },
        ],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 0);
      assert.equal(result.rejected, 2, JSON.stringify(result));
      assert.equal(result.rejected_reasons.unknown_id, 1);
      assert.equal(result.rejected_reasons.unknown_edge, 1);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("add_edge로 새로 추가한 엣지에 같은 패치의 set_edge_note로 바로 설명을 붙일 수 있다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-note-combo-"));
    try {
      write(root, "src/simple.ts", "export function first() { return 1; }\nexport function second() { return 2; }\n");
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      write(root, "_workspace/index/_ai_patch.json", JSON.stringify({
        version: 1,
        operations: [
          { op: "add_edge", from: "src.simple.first", to: "src.simple.second", type: "call", confidence: "MEDIUM", evidence: "동적 디스패치" },
          { op: "set_edge_note", from: "src.simple.first", to: "src.simple.second", type: "call", note: "두 번째 값 계산을 위임한다" },
          { op: "set_node_note", id: "src.simple.first", note: "첫 번째 값을 계산한다" },
        ],
      }));
      const result = applyAiPatch(root, "_workspace/index/_ai_patch.json");
      assert.equal(result.applied, 3, JSON.stringify(result));
      assert.equal(result.rejected, 0);
      const graph = json(root, "call_graph.json");
      const edge = graph.edges.find((e) => e.from === "src.simple.first" && e.to === "src.simple.second" && e.type === "call");
      assert.ok(edge, "add_edge로 추가된 엣지");
      assert.equal(edge.note, "두 번째 값 계산을 위임한다", "같은 패치 내에서 방금 추가한 엣지에도 note 적용됨");
      assert.equal(graph.nodes.find((n) => n.id === "src.simple.first").note, "첫 번째 값을 계산한다");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("분석 입력 팩이 허브·모듈·위험 digest를 상한과 함께 제공한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-digest-"));
    try {
      write(root, "src/main/java/com/acme/OrderController.java", `package com.acme;
@RequestMapping("/orders")
public class OrderController {
  @Autowired private OrderService service;
  @PostMapping("/{id}/cancel")
  public void cancel() { service.cancel(); }
}
class OrderService {
  @Transactional
  public void cancel() { repository.remove(); }
  public void neverCalled() {}
}
class Repository { public void remove() {} }
`);
      write(root, "src/main/resources/mapper/OrderMapper.xml", `<mapper namespace="com.acme.OrderMapper">
  <update id="cancel">UPDATE TBL_ORDER SET STATUS='CANCEL' WHERE ID=#{id}</update>
</mapper>`);
      write(root, "legacy/list.jsp", "<%@ page contentType=\"text/html\" %><script src=\"/js/list.js\"></script>");

      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const input = json(root, "_analysis_input.json");
      const digest = input.digest;
      assert.ok(digest, "digest 블록 존재");
      // 허브: 호출을 받는 심볼이 in-degree 순으로 노출된다.
      assert.ok(digest.hubs.some((item) => item.id.endsWith("OrderService.cancel")), `허브 목록: ${JSON.stringify(digest.hubs)}`);
      assert.ok(digest.hubs.every((item) => typeof item.in_degree === "number" && typeof item.out_degree === "number"));
      assert.ok(digest.entry_points.length > 0, "진입점 목록");
      assert.ok(digest.modules.some((item) => item.path.startsWith("src/main")), `모듈 목록: ${JSON.stringify(digest.modules)}`);
      assert.ok(digest.transactions.some((item) => item.marker), "트랜잭션 경계 요약");
      assert.ok(digest.sql_top_tables.some((item) => item.name === "tbl_order"), `SQL 상위 테이블: ${JSON.stringify(digest.sql_top_tables)}`);
      assert.ok(digest.endpoints.some((item) => item.method === "POST"), `엔드포인트 요약: ${JSON.stringify(digest.endpoints)}`);
      // PARTIAL 확장자를 노출해야 analyzer가 전체 재순회 없이 커버리지 구멍을 메울 수 있다.
      assert.ok(digest.partial_coverage_extensions.some((item) => item.extension === ".jsp"), `PARTIAL 노출: ${JSON.stringify(digest.partial_coverage_extensions)}`);
      // 상한과 잘린 개수를 항상 함께 기록한다.
      assert.ok(Number.isInteger(digest.hubs_truncated) && Number.isInteger(digest.modules_truncated));
      assert.ok(Number.isInteger(input.evidence.representative_files_truncated));
      assert.equal(input.analyzer_contract.digest_guided_selective_read, true);
      // Standard에서도 데드 코드 후보와 API 인덱스를 갖는다 (이전에는 Full/pair 전용이었다).
      assert.ok(digest.dead_code_candidates.some((item) => item.id.endsWith("OrderService.neverCalled")), `데드 코드 후보: ${JSON.stringify(digest.dead_code_candidates)}`);
      assert.ok(json(root, "_meta.json").indexes.includes("api_contract"), "단일 저장소도 api_contract 생성");
      assert.equal(json(root, "api_contract.json").matches.length, 0, "consumer가 없으면 매칭은 빈 배열");
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("ESM/CJS 확장자(.mjs/.cjs/.mts/.cts)도 FULL로 인덱싱한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-esm-"));
    try {
      write(root, "src/service.mjs", "export function loadOrder() { return 1; }\nexport function cancelOrder() { return loadOrder(); }\n");
      write(root, "src/legacy.cjs", "function helper() { return 2; }\nmodule.exports = { helper };\n");
      write(root, "src/typed.mts", "export function typedHandler(): number { return 3; }\n");
      // TypeScript 반환 타입 주석이 있으면 예전 정규식이 함수를 통째로 놓쳤다.
      write(root, "src/typed.ts", `export async function fetchOrders(id: string): Promise<Order[]> { return []; }
export const buildLabel = (value: number): string => { return String(value); };
class OrderStore {
  save(order: Order): void { }
}
`);
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const symbols = json(root, "symbols.json").symbols.map((item) => item.id);
      const graphNodes = json(root, "call_graph.json").nodes.map((item) => item.id);
      assert.ok(symbols.some((id) => id.endsWith("fetchOrders")), `async Promise 반환 타입 함수: ${JSON.stringify(symbols)}`);
      assert.ok(symbols.some((id) => id.endsWith("buildLabel")), `타입 주석 화살표 함수: ${JSON.stringify(symbols)}`);
      assert.ok(graphNodes.some((id) => id.endsWith("OrderStore.save")), `타입 주석 클래스 메서드: ${JSON.stringify(graphNodes)}`);
      // 확장자 목록이 네 곳에 중복돼 .mjs가 누락되면 ESM 프로젝트 심볼이 0건이 된다.
      assert.ok(symbols.some((id) => id.endsWith("loadOrder")), `.mjs 심볼: ${JSON.stringify(symbols)}`);
      assert.ok(symbols.some((id) => id.endsWith("helper")), `.cjs 심볼: ${JSON.stringify(symbols)}`);
      assert.ok(symbols.some((id) => id.endsWith("typedHandler")), `.mts 심볼: ${JSON.stringify(symbols)}`);
      assert.ok(json(root, "call_graph.json").edges.some((edge) => edge.to.endsWith("loadOrder")), "ESM 내부 호출 엣지");
      const coverage = json(root, "_meta.json").adapter_coverage;
      for (const ext of [".mjs", ".cjs", ".mts"]) {
        const entry = coverage.extensions.find((item) => item.extension === ext);
        assert.equal(entry?.level, "FULL", `${ext}는 FULL 커버리지여야 함: ${JSON.stringify(coverage.extensions)}`);
      }
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("대표 파일 목록 상한이 Tier에 비례한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-repfiles-"));
    try {
      for (let i = 0; i < 80; i += 1) {
        write(root, `src/mod${i}.ts`, `export function handler${i}() { return ${i}; }\n`);
      }
      buildIndex({ root, mode: "init", tier: "Lite", config: null });
      const lite = json(root, "_analysis_input.json").evidence;
      assert.ok(lite.representative_files.length <= 50, `Lite 상한 50: ${lite.representative_files.length}`);
      buildIndex({ root, mode: "init", tier: "Full", config: null });
      const full = json(root, "_analysis_input.json").evidence;
      assert.ok(full.representative_files.length > lite.representative_files.length, `Full이 더 많은 대표 파일을 준다: ${full.representative_files.length}`);
      assert.equal(full.representative_files_truncated, 0);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("미해결 관계가 200건을 넘어도 잘라내지 않고 전부 기록한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-unresolved-"));
    try {
      const calls = Array.from({ length: 250 }, (_, i) => `  target.run(${i});`).join("\n");
      write(root, "src/ambiguous.ts", `class First {\n  run(value: number) {}\n}\nclass Second {\n  run(value: number) {}\n}\nexport function caller(target: unknown) {\n${calls}\n}\n`);
      buildIndex({ root, mode: "init", tier: "Standard", config: null });
      const lines = readFileSync(join(root, "_workspace", "index", "_unresolved.jsonl"), "utf8").trim().split(/\r?\n/);
      assert.equal(lines.length, 250);
      assert.equal(json(root, "_meta.json").unresolved_count, 250);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  register("DDL FK·인덱스와 MyBatis JOIN 관계·mapper 사용처를 결정적으로 전수 추출한다", () => {
    const root = mkdtempSync(join(tmpdir(), "ax-indexer-db-relations-"));
    try {
      write(root, "src/main/java/com/acme/OrderMapper.java", `package com.acme;
public interface OrderMapper {
  void findOrders();
  void findTenantOrders();
}
`);
      write(root, "src/main/resources/mapper/OrderMapper.xml", `<mapper namespace="com.acme.OrderMapper">
  <select id="findOrders">
    SELECT O.ORDER_ID, U.USER_NAME
      FROM TBL_ORDER O
      JOIN TBL_USER U ON O.USER_ID = U.USER_ID
  </select>
  <select id="findTenantOrders">
    SELECT O.ORDER_ID
      FROM TBL_ORDER O, TBL_TENANT T
     WHERE O.TENANT_ID = T.TENANT_ID
  </select>
</mapper>`);
      write(root, "src/main/resources/schema.sql", `CREATE TABLE TBL_USER (
  USER_ID VARCHAR(20) PRIMARY KEY,
  USER_NAME VARCHAR(100)
);
CREATE TABLE TBL_TENANT (
  TENANT_ID VARCHAR(20) PRIMARY KEY
);
CREATE TABLE TBL_ORDER (
  ORDER_ID VARCHAR(20) PRIMARY KEY,
  USER_ID VARCHAR(20),
  TENANT_ID VARCHAR(20),
  CONSTRAINT FK_ORDER_USER FOREIGN KEY (USER_ID) REFERENCES TBL_USER (USER_ID)
);
CREATE UNIQUE INDEX IF NOT EXISTS IDX_ORDER_USER ON TBL_ORDER (USER_ID);
`);

      buildIndex({ root, mode: "init", tier: "Full", config: null });
      const schema = json(root, "schema.json");
      const sqlUsage = json(root, "sql_usage.json");
      const order = schema.tables.find((table) => table.name === "TBL_ORDER");
      assert.ok(order.foreign_keys.some((fk) => fk.name === "FK_ORDER_USER" && fk.references_table === "TBL_USER"), JSON.stringify(order));
      assert.ok(order.indexes.some((index) => index.name === "IDX_ORDER_USER" && index.unique === true), JSON.stringify(order));
      assert.ok(schema.relations.some((relation) => relation.type === "foreign_key" && relation.from_table === "TBL_ORDER" && relation.to_table === "TBL_USER"), JSON.stringify(schema.relations));
      assert.ok(schema.relations.some((relation) => relation.type === "query_join" && relation.from_table === "TBL_ORDER" && relation.to_table === "TBL_USER"), JSON.stringify(schema.relations));
      assert.ok(schema.relations.some((relation) => relation.type === "query_join" && [relation.from_table, relation.to_table].includes("TBL_TENANT")), JSON.stringify(schema.relations));
      assert.ok(sqlUsage.usages.some((usage) => usage.method === "com.acme.OrderMapper.findOrders" && usage.confidence === "HIGH"), JSON.stringify(sqlUsage.usages));
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
}

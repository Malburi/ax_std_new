# Index Specification

`_workspace/index/` 하위 JSON 파일들의 스키마 정의.

후속 에이전트(impact-analyzer, sql-reviewer, change-safety, migration-planner 등)가 조회한다.

## 생성 주체

| 파일 | 생성 주체 |
|------|---------|
| `symbols` · `call_graph` · `sql_usage` · `transactions` · `external_io` · `env_branches` · `schema` · `api_contract` · `dead_code` | `agents/lib/build-index.mjs` (결정론적 인덱서, LLM 미개입) |
| `call_graph`의 모호 관계 보강 | analyzer가 `_ai_patch.json`의 `add_edge` 오퍼레이션으로 제출 → 인덱서가 검증 후 병합 |
| `api_contract`의 `endpoints[]`/`consumers[]` 선택적 `description` | analyzer가 `_ai_patch.json`의 `set_endpoint_description`(`{id, description}`) 오퍼레이션으로 제출 |
| `external_io`의 `communications[]` 선택적 `description` | analyzer가 `_ai_patch.json`의 `set_communication_description`(`{id, description}`) 오퍼레이션으로 제출 |
| `data_flow` · `owasp_top10` · `client_index` | analyzer (판단이 필요해 기계화 대상 아님) |
| `schema` (라이브 DB 접속으로 뜬 경우) | analyzer |
| Vue 컴포넌트·Pinia 스토어 노드와 `import`·`inject` 엣지 | `agents/lib/index_extractor_vue.py` (인덱서 결과에 병합) |

인덱서가 없는 환경(node 18 미만)에서는 스택별 Python 추출기가 `symbols`·`call_graph`만 만들고, 그것도 실패하면 analyzer가 전부 작성한다. 상세는 `skills/harness-init/SKILL.md` 2-0.5.

인덱서는 제어 파일 3종을 함께 만든다 — `_meta.json`(전역 매니페스트: tier·복잡도·어댑터 커버리지·생성된 인덱스 목록), `_analysis_input.json`(analyzer가 읽는 상한 있는 요약과 계약), `_unresolved.jsonl`(후보가 둘 이상이라 확정하지 못한 관계). 이 셋은 `_meta` 블록을 갖지 않으므로 아래 9필드 규칙 대상이 아니다.

---

## 공통 규칙

- 파일 형식: JSON
- 인코딩: UTF-8 (BOM 없음)
- 들여쓰기: 2칸 (압축 안 함, 사람이 검토 가능)
- 용량 한도: 각 파일 종류별 한도 (analyzer.md 참조). 초과 시 분할.

`_meta`의 9개 필드(`generated_at`~`files_total`)는 모든 인덱스 파일에 필수다 — 없으면 `validator_checks.py`가 하드 FAIL 처리한다.

`generated_at`은 analyzer가 추측해 지어내는 값이 아니라 `agents/lib/now_kst.py` 실행 결과(KST, UTC+9, `+09:00` 오프셋)여야 한다 — `git_commit`을 `git rev-parse HEAD`로 얻는 것과 동일하게 실제 명령 실행 결과를 쓴다.

`call_graph.json`의 모든 edge는 `from`/`to`가 `nodes` 배열에 실존하는 id를 가리켜야 한다 (dangling 금지, `validator_checks.py`가 기계 검증). `_meta.node_count`/`edge_count`도 실제 배열 길이와 일치해야 한다.

각 인덱스 파일은 최상위에 메타 정보:

```json
{
  "_meta": {
    "generated_at": "2026-06-02T15:30:00+09:00",
    "generator": "analyzer",
    "version": "1.0",
    "source_root": "/path/to/project",
    "mode": "init|incremental|feature-scoped",
    "git_commit": "abc1234... (git rev-parse HEAD, git 저장소 아니면 null)",
    "sampled": false,
    "files_scanned": 1180,
    "files_total": 1234,
    "node_count": 1234,
    "edge_count": 5678
  },
  "data": [...]
}
```

---

## call_graph.json

호출 관계 그래프.

```json
{
  "_meta": {...},
  "nodes": [
    {
      "id": "com.example.OrderService.cancel",
      "type": "method",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 42,
      "visibility": "public",
      "static": false,
      "annotations": ["@Transactional"],
      "signature": "void cancel(Long orderId)"
    }
  ],
  "edges": [
    {
      "from": "com.example.OrderController.cancel",
      "to": "com.example.OrderService.cancel",
      "type": "call",
      "file": "src/main/java/com/example/OrderController.java",
      "line": 56
    }
  ]
}
```

`type` 값:
- `call` — 메서드 직접 호출
- `inject` — DI 주입 관계 (Spring `@Autowired` 등)
- `inherit` — 상속/구현
- `import` — 파일/모듈 간 import 관계. 결정론적 인덱서는 **이 타입을 만들지 않는다**(파일 노드가 없는 순수 심볼 그래프라 `to`가 노드가 아니게 된다). Vue 추출기 등 파일 단위 관계를 내는 생성기만 쓴다
- `reflect` — 리플렉션 가능성 (heuristic, 신뢰도 낮음). 인덱서는 만들지 않고 analyzer가 `_ai_patch.json`으로만 추가한다
- `ui_event` · `markup_event` · `scheduler` · `process_entry` — 진입점에서 핸들러로 가는 관계. 출발점은 `trigger:<파일>#<트리거>` 형태의 합성 노드다

모든 레코드에는 `origin`(`deterministic-indexer` | `ai-enrichment` | `analyzer`)과 `confidence`(`HIGH`/`MEDIUM`/`LOW`)가 붙는다 — 어디서 온 사실인지 구분하기 위한 것이다.

**후보가 둘 이상이면 엣지를 만들지 않는다.** 인덱서는 이름 해석 결과가 정확히 하나일 때만 엣지를 쓰고, 둘 이상이면 `_unresolved.jsonl`에 후보 목록과 함께 넘기며, 하나도 없으면(외부 라이브러리 호출 등) 버린다. 그래서 dangling 엣지가 구조적으로 생기지 않는다. analyzer는 이 목록을 판정해 `_ai_patch.json`으로만 보강하며, 이때도 **기존 노드 사이의 엣지만** 추가할 수 있다.

미해결이 대량인 레거시 시스템에서는 `_analysis_input.json`의 `analyzer_contract.process_all_unresolved`가 `false`가 되고 `unresolved_priority`(후보 적은 순 상위 N건)만 판정 대상이 된다. 그 밖의 레코드는 위치와 후보 수만 남고 `candidates_omitted: true`가 붙는다.

---

## symbols.json

모든 클래스/메서드/함수 심볼 인덱스.

```json
{
  "_meta": {...},
  "symbols": [
    {
      "id": "com.example.OrderService",
      "type": "class",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 10,
      "package": "com.example",
      "extends": "AbstractService",
      "implements": ["OrderOperations"],
      "annotations": ["@Service"],
      "methods": [
        {"name": "cancel", "id": "com.example.OrderService.cancel", "line": 42, "visibility": "public"}
      ]
    }
  ]
}
```

언어별 식별자:
- Java: 완전 자격 이름 (`com.example.X.method`)
- Python: 모듈.클래스.함수 (`services.order.OrderService.cancel`)
- JavaScript/TypeScript: 파일경로::심볼명 (`src/services/order.ts::cancelOrder`)
- Go: 패키지.함수 (`services.CancelOrder`)

---

## sql_usage.json

SQL ID ↔ 호출 위치 매핑.

```json
{
  "_meta": {...},
  "sqls": [
    {
      "id": "ORDER_LMS_S01",
      "file": "WEB-INF/config/query/query-order-ora.xml",
      "line": 23,
      "type": "select",
      "tables": ["TBL_ORDER"],
      "columns_selected": ["ORDER_ID", "USER_ID", "STATUS"],
      "columns_where": ["USER_ID", "STATUS"],
      "text_preview": "SELECT ORDER_ID, USER_ID, STATUS FROM TBL_ORDER WHERE USER_ID = ? AND STATUS = ?"
    }
  ],
  "usages": [
    {
      "sql_id": "ORDER_LMS_S01",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 78,
      "method": "com.example.OrderService.findByUser"
    }
  ]
}
```

`type` 값: `select`, `insert`, `update`, `delete`, `ddl`.

`tables`/`columns_*` 는 best-effort 파싱. 동적 SQL은 누락 가능.

---

## schema.json

DB 스키마 스냅샷.

```json
{
  "_meta": {
    ...,
    "source": "live_db|ddl_files|orm_mapping",
    "dialect": "oracle|postgresql|mysql|..."
  },
  "tables": [
    {
      "name": "TBL_ORDER",
      "schema": "PUBLIC",
      "columns": [
        {
          "name": "ORDER_ID",
          "type": "NUMBER(19)",
          "nullable": false,
          "default": null,
          "primary_key": true
        },
        {
          "name": "STATUS",
          "type": "VARCHAR2(20)",
          "nullable": false,
          "default": "'PENDING'"
        }
      ],
      "primary_key": ["ORDER_ID"],
      "foreign_keys": [
        {
          "name": "FK_ORDER_USER",
          "columns": ["USER_ID"],
          "references_table": "TBL_USER",
          "references_columns": ["USER_ID"]
        }
      ],
      "indexes": [
        {
          "name": "IDX_ORDER_USER_STATUS",
          "columns": ["USER_ID", "STATUS"],
          "unique": false
        }
      ],
      "row_count_estimate": 1234567
    }
  ],
  "views": [...],
  "procedures": [...],
  "functions": [...],
  "triggers": [...]
}
```

`source` 값:
- `live_db` — 운영/스테이징 DB read-only 직접 조회
- `ddl_files` — `*.sql`, `V*.sql`, Liquibase changeset 등에서 파싱
- `orm_mapping` — `@Entity` 클래스에서 역추출

`row_count_estimate` 는 live_db 모드일 때만 채워짐.

---

## transactions.json

트랜잭션 경계 식별.

```json
{
  "_meta": {...},
  "boundaries": [
    {
      "id": "tx_001",
      "entry_method": "com.example.OrderService.cancel",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 42,
      "marker": "@Transactional",
      "propagation": "REQUIRED",
      "isolation": "DEFAULT",
      "rollback_for": ["Exception.class"],
      "methods_in_scope": [
        "com.example.OrderService.cancel",
        "com.example.OrderDao.updateStatus",
        "com.example.RefundService.process"
      ],
      "external_io_calls": [
        {"target": "com.example.PaymentGatewayClient.refund", "type": "http"}
      ]
    }
  ]
}
```

`external_io_calls` 는 트랜잭션 경계 안에서의 외부 호출 — 위험 항목.

---

## external_io.json

외부 통신 식별.

```json
{
  "_meta": {...},
  "communications": [
    {
      "id": "ext_001",
      "type": "http",
      "file": "src/main/java/com/example/PaymentClient.java",
      "line": 45,
      "method": "com.example.PaymentClient.charge",
      "target": "https://api.payment.example.com/charge",
      "timeout_ms": 30000,
      "retry_policy": "exponential_backoff(3)",
      "in_transaction": false,
      "description": "결제 게이트웨이에 승인 요청을 전달한다"
    },
    {
      "id": "ext_002",
      "type": "kafka_producer",
      "topic": "orders.events",
      "file": "src/main/java/com/example/OrderEventPublisher.java",
      "line": 12
    },
    {
      "id": "ext_003",
      "type": "file_io",
      "operation": "read",
      "path_pattern": "/data/batch/*.csv",
      "file": "src/main/java/com/example/BatchJob.java",
      "line": 30
    }
  ]
}
```

`type` 값: `http`, `kafka_producer`, `kafka_consumer`, `rabbit_*`, `sqs_*`, `file_io`, `external_db`, `ldap`, `mail`, `redis`, `s3`, etc.

`description`은 선택 필드다 — 인덱서는 채우지 않고, analyzer가 `_ai_patch.json`의 `set_communication_description`으로 보강한다(위 "생성 주체" 표 참조). 없어도 정상이다.

---

## env_branches.json

환경 분기 코드 위치.

```json
{
  "_meta": {...},
  "profiles": ["dev", "stg", "prod"],
  "branches": [
    {
      "file": "src/main/java/com/example/SomeConfig.java",
      "line": 23,
      "type": "annotation",
      "marker": "@Profile(\"prod\")",
      "method": "com.example.SomeConfig.productionOnlyBean"
    },
    {
      "file": "src/main/resources/application.yml",
      "line": null,
      "type": "config_file",
      "marker": "spring.profiles.active",
      "values_per_profile": {
        "dev": "localhost",
        "prod": "prod-db.internal"
      }
    },
    {
      "file": "src/services/feature.ts",
      "line": 12,
      "type": "code_if",
      "marker": "if (process.env.NODE_ENV === 'production')",
      "method": "feature.ts::initialize"
    }
  ]
}
```

---

## owasp_top10.json

OWASP Top 10 (2021) 카테고리별 매핑. 정적 분석 증거 기반 — 증거 없는 카테고리는 `미탐지`로 남기며, 이는 "취약점 없음"의 보증이 아니다.

```json
{
  "_meta": {"generated_at": "2026-06-02T15:30:00+09:00", "sampled": false},
  "categories": [
    {
      "id": "A01:2021",
      "name": "Broken Access Control",
      "status": "발견",
      "findings": [
        {
          "file": "src/main/java/com/example/OrderController.java",
          "line": 56,
          "evidence": "cancel(Long orderId) — 소유자 검증 없이 orderId로 직접 조회",
          "severity": "high",
          "confidence": "medium"
        }
      ]
    }
  ]
}
```

`id` 값: `A01:2021` ~ `A10:2021` (OWASP Top 10 2021 edition), 10개 카테고리 고정.

`status` 값:
- `발견` — 코드에서 구체적 증거를 찾음
- `확인필요` — 정적 분석 한계로 사람 검토 필요 (예: A06 의존성 CVE 대조, A04 비즈니스 로직 설계)
- `미탐지` — 해당 패턴 자체를 코드에서 못 찾음

`severity` 값: `high`/`medium`/`low`/`unknown`. `confidence` 값: `high`/`medium`/`low`/`n/a` (샘플링 모드면 low로 낮춘다).

---

## dead_code.json

데드 코드 후보 (확정 아님 — 리플렉션 등 동적 호출 가능성).

```json
{
  "_meta": {
    ...,
    "warning": "Static analysis only. Dynamic invocation (reflection, DI by name, external triggers) NOT detected. Verify before removal."
  },
  "unused_methods": [
    {
      "id": "com.example.LegacyService.unusedMethod",
      "file": "src/main/java/com/example/LegacyService.java",
      "line": 88,
      "visibility": "public",
      "reason": "in_degree=0 in call_graph"
    }
  ],
  "unused_sql_ids": [
    {
      "id": "ORDER_LMS_OLD_S01",
      "file": "WEB-INF/config/query/query-order-ora.xml",
      "line": 99,
      "reason": "not referenced in sql_usage"
    }
  ],
  "unused_jsps": [
    {
      "file": "WEB-INF/jsp/back/order/oldList.jsp",
      "reason": "not in any forward path"
    }
  ]
}
```

각 항목에 `reason` 명시. 사용자 검토 후에만 제거.

---

## 인덱스 갱신 정책

| 시나리오 | 동작 |
|---------|------|
| 최초 분석 (init) | 전체 인덱스 생성 |
| incremental | git diff 또는 mtime 비교로 변경 파일만 재분석. 영향받는 노드/엣지만 갱신 |
| feature-scoped | 사용자 지정 범위만. 인덱스에 부분 추가 (기존 데이터 보존) |

인덱스 stale 감지:
- 각 인덱스의 `_meta.generated_at`과 코드 파일 mtime 비교
- 코드 파일이 더 최신이면 stale 경고

---

## 인덱스가 없거나 stale일 때의 fallback

각 에이전트는 인덱스 우선 조회, 없으면 grep fallback:

| 에이전트 | 인덱스 의존 | Fallback |
|---------|---------|---------|
| impact-analyzer | call_graph, sql_usage, schema | grep 호출 패턴 |
| sql-reviewer | sql_usage, schema | grep SQL ID, DDL 파일 파싱 |
| change-safety | call_graph, external_io | impact-analyzer 결과 활용 |
| migration-planner | call_graph, external_io, transactions, dead_code | analyzer 리포트 마크다운만 활용 |

Fallback은 느리고 정확도가 떨어진다. 인덱스 정기 갱신을 권장.

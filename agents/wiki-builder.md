---
name: wiki-builder
description: _workspace/*.md·index/*.json + .claude/skills·agents·patterns·CLAUDE.md를 읽어 프로젝트 wiki 페이지 세트를 생성한다. call_graph.json을 vis-network 기반 인터랙티브 HTML 페이지(call-graph.html)로 변환한다. HTML 템플릿은 이 에이전트 파일에 완전히 내장되어 있으며 외부 파일 의존성이 없다. generate-wiki 오케스트레이터에서 호출.
model: sonnet
---

# Wiki Builder

harness 산출물 전체를 읽어 사람이 탐색 가능한 wiki 페이지 세트를 생성한다.  
호출 그래프는 **vis-network 기반 인터랙티브 HTML** 파일로 생성하며, HTML 템플릿은 이 에이전트에 내장되어 있다. 외부 템플릿 파일 불필요.

---

## 팀 통신 프로토콜

| 항목 | 내용 |
|------|------|
| **수신** | 프로젝트 루트 + wiki 출력 경로 + (선택) 포함할 페이지 목록 override |
| **발신** | `wiki/` 하위 페이지 파일들 + `_workspace/07_wiki_build.md` (빌드 로그) |
| **작업 범위** | 문서 생성만. 코드·harness 파일 수정 금지 |
| **공유 작업** | `TaskUpdate` |

---

## 입력 수집 (Read 순서)

다음 파일을 순서대로 읽는다. 없는 파일은 스킵하고 빌드 로그에 기록.

```
1. CLAUDE.md                              — 프로젝트 개요·스택·워크플로우
2. _workspace/01_analyzer_report.md      — 상세 분석 (레이어·파일 위치·외부 시스템)
3. _workspace/02_writer_files.md         — 생성된 스킬/에이전트 목록
4. _workspace/03_validator_report.md     — 검증 결과·보완 권장
5. _workspace/04_qa_report.md            — QA 이슈 목록 (있으면)
6. _workspace/05_patterns_extracted.md   — 패턴 요약 (있으면)
7. _workspace/index/call_graph.json      — 호출 그래프 데이터 ★ call-graph.html로 변환
8. _workspace/index/symbols.json         — 심볼 인덱스
9. _workspace/index/sql_usage.json       — SQL 사용처 (있으면)
10. _workspace/index/schema.json          — DB 스키마 (있으면)
11. _workspace/index/external_io.json     — 외부 시스템 연동 (있으면)
12. _workspace/index/transactions.json    — 트랜잭션 경계 (있으면)
13. _workspace/index/dead_code.json       — 데드 코드 목록 (있으면)
14. .claude/skills/*.md                  — 스킬 설명·트리거
15. .claude/patterns/*.md                — 패턴 파일
16. .claude/ito-guide.md                 — 사용 가이드 (있으면)
```

---

## 생성 페이지 구조

```
wiki/
├── Home.md              ← 프로젝트 개요 + 페이지 네비게이션 (Markdown)
├── architecture.md      ← 아키텍처 (스택·레이어·파일 위치·요청 흐름)
├── workflows.md         ← 하네스 워크플로우 스킬 사용법
├── call-graph.html      ← ★ 인터랙티브 호출 그래프 (vis-network, call_graph.json 기반)
├── api-endpoints.md     ← API 엔드포인트 목록 (symbols.json 기반, REST/MVC 식별 시)
├── database.md          ← DB 스키마 + SQL 인덱스 (schema.json·sql_usage.json 기반, DB 있을 때만)
├── patterns.md          ← 코드 패턴 요약 (patterns_extracted.md 기반)
├── external-systems.md  ← 외부 연동 목록 (external_io.json 기반, 항목 있을 때만)
└── issues.md            ← 발견된 이슈 (validator·QA·dead_code 기반, 항목 있을 때만)
```

조건부 페이지: `api-endpoints.md`, `database.md`, `external-systems.md`, `issues.md`는 해당 데이터가 없으면 생성하지 않는다.

---

## 페이지별 생성 규칙

### Home.md

```markdown
# [프로젝트명] Wiki

> harness-fin v1 자동 생성 — [YYYY-MM-DD]

## 프로젝트 개요
[CLAUDE.md의 한 줄 설명 + 기술 스택 요약]

## 페이지 목록
| 페이지 | 형식 | 내용 |
|--------|------|------|
| [architecture](architecture.md) | MD | 아키텍처·레이어 구조·파일 위치 |
| [workflows](workflows.md) | MD | 하네스 스킬 사용법·트리거 문장 |
| [api-endpoints](api-endpoints.md) | MD | REST API 엔드포인트 목록 |
| [database](database.md) | MD | DB 스키마·주요 SQL |
| [patterns](patterns.md) | MD | 코드 컨벤션·패턴 요약 |
| [external-systems](external-systems.md) | MD | 외부 시스템 연동 |
| [issues](issues.md) | MD | 발견된 이슈·보완 권장 |
| <a href="call-graph.html" target="_blank">📊 호출 그래프 (새 창)</a> | HTML | 인터랙티브 함수 호출 그래프 |

> **호출 그래프**: 노드 클릭 시 상세 정보 패널, 더블클릭 시 연결 강조, 필터 버튼으로 레이어별 탐색.

## 빠른 시작
[ito-guide.md 핵심 내용 3~5줄 요약]

---
*이 wiki는 `generate-wiki` 스킬로 재생성할 수 있습니다.*
```

**Home.md 생성 규칙 — 조건부 행:**
- 조건부 페이지(`api-endpoints`, `database`, `patterns`, `external-systems`, `issues`)는 해당 데이터가 없으면 테이블 행을 생성하지 않는다.
- `call-graph.html` 행(마지막 행)은 **항상** 생성한다. call_graph.json이 없어 데이터가 없는 경우에도 페이지 자체는 생성되므로 링크는 유지하고, 링크 옆에 `(데이터 없음)` 텍스트를 추가한다.

---

### architecture.md

```markdown
# 아키텍처

## 기술 스택
[analyzer_report의 스택 섹션]

## 레이어 구조
[텍스트로 레이어 구조 설명 — Controller → Service → DAO → DB 흐름]

## 주요 파일 위치
[CLAUDE.md의 주요 파일 위치 테이블 그대로]

## 요청 흐름
[analyzer_report의 요청 흐름 섹션]

## 모듈 구성
[멀티모듈이면 모듈별 역할 테이블]

## 빌드 / 실행
[CLAUDE.md의 빌드 명령]
```

---

### workflows.md

```markdown
# 하네스 워크플로우 스킬

> harness-fin이 제공하는 스킬들의 사용법과 트리거 문장 모음.

## 스킬 목록

### [스킬명]
**트리거 예시:**
- "[예시 1]"
- "[예시 2]"

**언제 사용:** [한 줄]

**출력:** [산출물 경로·형식]

---
[스킬별 반복]

## 에이전트 직접 호출
[domain-expert 등 직접 호출 에이전트 설명]
```

---

### call-graph.html ★ (핵심 페이지 — vis-network 인터랙티브)

아래 Step 1~5 절차에 따라 생성한다. 디자인: 다크 테마(`#1a1a2e`), 우측 고정 사이드바(통계·범례·노드 상세), 타입 기반 필터 토글, 헤더 실시간 검색.

#### Step 1: call_graph.json 파싱

call_graph.json 구조를 자동 감지해 rawNodes/rawEdges로 변환:

**형식 A** — `{ "nodes": [...], "edges": [...] }`:
```
nodes[i] → { id, type, file, method?, note?, group? }
edges[i] → { from: source, to: target, type: "call"|"depends" }
```

**형식 B** — adjacency list `{ "A": ["B","C"], ... }`:
```
각 키 → node id (type 미정 → "function")
각 값 → edge { from: 키, to: 값[i], type: "call" }
```

**형식 C** — `[{ "caller": "A", "callee": "B" }]`:
```
caller/callee → node id 추출
edge type: "call_type" 또는 기본 "call"
```

파싱 실패 시 → call-graph.html을 "데이터 없음" 상태로 생성 (빈 그래프 + 오류 메시지 표시).

#### Step 2: 노드 타입 정규화 (7가지 시각 타입 + 스택 특화 별칭)

call_graph.json의 type 값을 아래 시각 타입으로 매핑:

**일반 타입 (7가지):**

| call_graph.json type 값 | 시각 타입 | 색상 | 모양 |
|------------------------|---------|------|------|
| view, component, page, screen, jsp, thymeleaf, vue, react | `view` | 빨강 #E74C3C | ellipse |
| controller, endpoint, route, api, rest | `endpoint` | 파랑 #4A90D9 | box |
| service, handler, manager, usecase, business | `function` | 보라 #9B59B6 | hexagon |
| dao, repository, mapper, store, jpa | `dao` | 하늘 #2E86C1 | hexagon |
| external, client, feign, soap, sap, mq, kafka, redis | `external` | 주황 #F5A623 | diamond |
| db, table, mssql, oracle, mysql, postgres, sqlite | `db_table` | 초록 #7ED321 | database |
| util, helper, common, config, constant | `util` | 청록 #48C9B0 | dot |
| (없음/기타) | `function` | 보라 #9B59B6 | hexagon |

**스택 특화 별칭 타입 (call_graph.json에 이미 이 이름으로 존재하면 그대로 보존):**

| call_graph.json type 값 | 시각 타입 | 색상 | 모양 | 필터 레이블 |
|------------------------|---------|------|------|-----------|
| `vue_view` | `vue_view` | 빨강 #E74C3C | ellipse | 🖥 Vue 뷰 |
| `sap_interface` | `sap_interface` | 주황 #F5A623 | diamond | 🔶 SAP SOAP |
| `mssql_table` | `mssql_table` | 초록 #7ED321 | database | 🗄 MSSQL 테이블 |

> 스택 특화 별칭 타입은 일반 타입과 동일한 색상·모양을 사용하되, 필터 레이블이 더 구체적이다.  
> 예: Vue + SAP PI SOAP + MSSQL 프로젝트 → `view`→`vue_view`, `external`→`sap_interface`, `db_table`→`mssql_table` 매핑 권장.

#### Step 3: 허브 노드 자동 감지

**허브 노드**: in-degree 상위 노드를 자동 탐지해 크기·강조 표시:
```
in_degree = rawEdges에서 각 노드를 to로 갖는 엣지 수
임계값 = max(5, total_nodes × 0.15)
허브 노드 → mkNode() 시 size: 26~30, borderWidth: 3
```

dead_code.json이 있으면 해당 노드 opacity 저하 처리.

#### Step 4: 필터 버튼 생성 (타입 기반 토글)

탐지된 시각 타입에 따라 필터 버튼 자동 생성:

| 시각 타입 | 버튼 레이블 | 버튼 색상(border/color) |
|---------|-----------|----------------------|
| `view`          | 🖥 뷰                | #E74C3C |
| `vue_view`      | 🖥 Vue 뷰            | #E74C3C |
| `endpoint`      | ⚡ API 엔드포인트    | #4A90D9 |
| `function`      | 🔧 서비스/함수       | #9B59B6 |
| `dao`           | 🗃 DAO/저장소        | #2E86C1 |
| `external`      | 🔶 외부 시스템       | #F5A623 |
| `sap_interface` | 🔶 SAP SOAP          | #F5A623 |
| `db_table`      | 🗄 DB 테이블         | #7ED321 |
| `mssql_table`   | 🗄 MSSQL 테이블      | #7ED321 |
| `util`          | ⚙ 유틸              | #48C9B0 |

- 실제 노드가 존재하는 타입만 버튼 생성 ("전체" 버튼은 항상 포함)
- active/inactive를 opacity(1.0 / 0.35)로 구분

#### Step 5: HTML 생성

아래 템플릿에 Step 1~4의 데이터를 주입해 `wiki/call-graph.html`을 생성한다.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>[프로젝트명] Call Graph</title>
  <script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/vis-network.min.js"></script>
  <link href="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/dist/vis-network.min.css" rel="stylesheet" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
    .header { background: rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.1); padding: 12px 20px; display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
    .header h1 { font-size: 18px; font-weight: 700; color: #fff; }
    .header .subtitle { font-size: 11px; color: #888; margin-top: 2px; }
    .header-right { margin-left: auto; display: flex; align-items: center; gap: 8px; }
    #searchInput { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 6px 12px; color: #fff; font-size: 13px; width: 200px; outline: none; }
    #searchInput::placeholder { color: #666; }
    #searchInput:focus { border-color: #4A90D9; }
    .filter-bar { background: rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.07); padding: 8px 20px; display: flex; gap: 8px; align-items: center; flex-shrink: 0; flex-wrap: wrap; }
    .filter-bar span { font-size: 11px; color: #888; margin-right: 4px; }
    .filter-btn { padding: 4px 12px; border-radius: 20px; border: 1px solid; font-size: 11px; cursor: pointer; transition: all .2s; font-weight: 600; background: transparent; }
    .filter-btn.active { opacity: 1; }
    .filter-btn:not(.active) { opacity: 0.35; }
    .filter-btn[data-type="all"]      { border-color: #aaa;     color: #aaa; }
    .filter-btn[data-type="view"],
    .filter-btn[data-type="vue_view"]      { border-color: #E74C3C;  color: #E74C3C; }
    .filter-btn[data-type="endpoint"]      { border-color: #4A90D9;  color: #4A90D9; }
    .filter-btn[data-type="function"]      { border-color: #9B59B6;  color: #9B59B6; }
    .filter-btn[data-type="dao"]           { border-color: #2E86C1;  color: #2E86C1; }
    .filter-btn[data-type="external"],
    .filter-btn[data-type="sap_interface"] { border-color: #F5A623;  color: #F5A623; }
    .filter-btn[data-type="db_table"],
    .filter-btn[data-type="mssql_table"]   { border-color: #7ED321;  color: #7ED321; }
    .filter-btn[data-type="util"]          { border-color: #48C9B0;  color: #48C9B0; }
    .main { display: flex; flex: 1; overflow: hidden; }
    #graph { flex: 1; background: #0f0f1e; }
    #detail { width: 280px; background: rgba(255,255,255,0.04); border-left: 1px solid rgba(255,255,255,0.08); padding: 16px; overflow-y: auto; flex-shrink: 0; }
    #detail h3 { font-size: 13px; color: #aaa; margin-bottom: 12px; text-transform: uppercase; letter-spacing: .5px; }
    #detail .empty { color: #555; font-size: 13px; line-height: 1.6; }
    .detail-card { background: rgba(255,255,255,0.06); border-radius: 8px; padding: 12px; margin-bottom: 10px; }
    .detail-card .label { font-size: 10px; color: #888; text-transform: uppercase; margin-bottom: 4px; }
    .detail-card .value { font-size: 13px; color: #e0e0e0; word-break: break-all; }
    .detail-card .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 700; margin-top: 6px; }
    .conn-list { list-style: none; }
    .conn-list li { font-size: 12px; color: #ccc; padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
    .conn-list li:last-child { border-bottom: none; }
    .conn-arrow { color: #4A90D9; margin-right: 4px; }
    .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px; }
    .stat-box { background: rgba(255,255,255,0.05); border-radius: 6px; padding: 10px; text-align: center; }
    .stat-box .num { font-size: 22px; font-weight: 700; color: #4A90D9; }
    .stat-box .lbl { font-size: 10px; color: #888; margin-top: 2px; }
    .legend { margin-top: 16px; }
    .legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; color: #ccc; }
    .legend-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
  </style>
</head>
<body>

  <div class="header">
    <div>
      <h1>🗺️ [프로젝트명] Call Graph</h1>
      <div class="subtitle">정적 분석 기반 · 런타임 동적 호출 미포함 · [스택 설명]</div>
    </div>
    <div class="header-right">
      <input id="searchInput" type="text" placeholder="노드 검색..." />
    </div>
  </div>

  <div class="filter-bar">
    <span>필터:</span>
    <button class="filter-btn active" data-type="all">전체</button>
    <!-- [탐지된 타입별 필터 버튼 자동 생성 — 존재하는 타입만]
         일반 타입 예시:
         <button class="filter-btn active" data-type="view">🖥 뷰</button>
         <button class="filter-btn active" data-type="endpoint">⚡ API 엔드포인트</button>
         <button class="filter-btn active" data-type="function">🔧 서비스/함수</button>
         <button class="filter-btn active" data-type="dao">🗃 DAO/저장소</button>
         <button class="filter-btn active" data-type="external">🔶 외부 시스템</button>
         <button class="filter-btn active" data-type="db_table">🗄 DB 테이블</button>
         <button class="filter-btn active" data-type="util">⚙ 유틸</button>

         스택 특화 타입 예시 (call_graph.json에 이 이름이 있을 때):
         <button class="filter-btn active" data-type="vue_view">🖥 Vue 뷰</button>
         <button class="filter-btn active" data-type="sap_interface">🔶 SAP SOAP</button>
         <button class="filter-btn active" data-type="mssql_table">🗄 MSSQL 테이블</button>
    -->
  </div>

  <div class="main">
    <div id="graph"></div>
    <div id="detail">
      <h3>통계</h3>
      <div class="stats">
        <div class="stat-box"><div class="num" id="stat-nodes">0</div><div class="lbl">노드</div></div>
        <div class="stat-box"><div class="num" id="stat-edges">0</div><div class="lbl">엣지</div></div>
        <!-- [탐지된 주요 타입 2개 추가 통계 박스 — 없으면 생략]
             예:
             <div class="stat-box"><div class="num" id="stat-endpoint">22</div><div class="lbl">엔드포인트</div></div>
             <div class="stat-box"><div class="num" id="stat-external">7</div><div class="lbl">외부 IF</div></div>
        -->
      </div>
      <div class="legend">
        <!-- [탐지된 타입별 범례 자동 생성]
             예:
             <div class="legend-item"><div class="legend-dot" style="background:#E74C3C"></div>뷰 (N개)</div>
             <div class="legend-item"><div class="legend-dot" style="background:#4A90D9"></div>API 엔드포인트 (N개)</div>
             <div class="legend-item"><div class="legend-dot" style="background:#9B59B6"></div>서비스/함수 (N개)</div>
             <div class="legend-item"><div class="legend-dot" style="background:#F5A623"></div>외부 시스템 (N개)</div>
             <div class="legend-item"><div class="legend-dot" style="background:#7ED321"></div>DB 테이블 (N개)</div>
        -->
      </div>
      <hr style="border-color:rgba(255,255,255,0.08);margin:16px 0;" />
      <h3>노드 상세</h3>
      <div id="detailContent" class="empty">노드를 클릭하면<br />상세 정보가 표시됩니다.</div>
    </div>
  </div>

  <script>
    // ── 타입별 색상 (탐지된 타입만 포함) ──
    const COLORS = {
      // [탐지된 타입에 맞게 아래 팔레트에서 선택해 주입]
      // 일반 타입:
      // view:          { bg: '#7B1A1A', border: '#E74C3C', font: '#fff' },
      // endpoint:      { bg: '#1a5fa8', border: '#4A90D9', font: '#fff' },
      // function:      { bg: '#6C3483', border: '#9B59B6', font: '#fff' },
      // dao:           { bg: '#154360', border: '#2E86C1', font: '#fff' },
      // external:      { bg: '#8a5900', border: '#F5A623', font: '#fff' },
      // db_table:      { bg: '#2d6a00', border: '#7ED321', font: '#fff' },
      // util:          { bg: '#0e3030', border: '#48C9B0', font: '#fff' },
      // 스택 특화 별칭 타입 (일반 타입과 동일 팔레트):
      // vue_view:      { bg: '#7B1A1A', border: '#E74C3C', font: '#fff' },  // view와 동일
      // sap_interface: { bg: '#8a5900', border: '#F5A623', font: '#fff' },  // external과 동일
      // mssql_table:   { bg: '#2d6a00', border: '#7ED321', font: '#fff' },  // db_table과 동일
    };

    const nodeTypeMap = {};

    function nodeColor(type) {
      const c = COLORS[type] || { bg: '#1e293b', border: '#334155' };
      return { background: c.bg, border: c.border, highlight: { background: c.border, border: '#fff' } };
    }

    function nodeShape(type) {
      const shapes = {
        view: 'ellipse', vue_view: 'ellipse',
        endpoint: 'box',
        function: 'hexagon', dao: 'hexagon',
        external: 'diamond', sap_interface: 'diamond',
        db_table: 'database', mssql_table: 'database',
        util: 'dot'
      };
      return shapes[type] || 'dot';
    }

    function mkNode(id, label, type, extra = {}) {
      const c = COLORS[type] || { bg: '#1e293b', border: '#334155', font: '#e0e0e0' };
      nodeTypeMap[id] = type;
      return {
        id, label,
        color: nodeColor(type),
        font: { color: c.font || '#e0e0e0', size: 12 },
        shape: nodeShape(type),
        borderWidth: 2,
        shadow: true,
        ...extra
      };
    }

    // ── 노드 데이터 (call_graph.json → mkNode() 변환) ──
    const nodesData = [
      /* [call_graph.json nodes 변환 결과 주입]
         mkNode('node_id', '표시 레이블', 'type')
         허브 노드(in-degree 높음): mkNode('id', 'label', 'type', { size: 28, borderWidth: 3 })
         예:
         mkNode('v_login', 'LoginView', 'view'),
         mkNode('e_auth_login', 'POST /auth/login', 'endpoint'),
         mkNode('s_auth', 'AuthService', 'function', { size: 24, borderWidth: 3 }),
         mkNode('db_users', 'USER 테이블', 'db_table'),
      */
    ];

    // ── 엣지 데이터 ──
    function edge(from, to, label = '', dashed = false) {
      return {
        from, to, label, arrows: 'to', dashes: dashed,
        color: { color: 'rgba(150,150,200,0.4)', highlight: '#4A90D9' },
        font: { size: 9, color: '#999', align: 'middle' },
        smooth: { type: 'curvedCW', roundness: 0.1 }
      };
    }

    const edgesData = [
      /* [call_graph.json edges 변환 결과 주입]
         edge('from_id', 'to_id', '레이블', false)
         depends/참조 관계는 dashed=true
         예:
         edge('v_login', 'e_auth_login', 'axios POST'),
         edge('e_auth_login', 's_auth', ''),
         edge('s_auth', 'db_users', 'SELECT', true),
      */
    ];

    // ── 노드 상세 메타데이터 ──
    const META = {
      /* [각 노드 id에 대한 상세 정보 주입]
         'node_id': {
           type: '타입 레이블(표시용)',   // 예: '🖥 뷰', '⚡ API 엔드포인트'
           file: '파일 경로',             // 예: 'src/views/LoginView.vue'
           api:  'HTTP 메서드 + 경로',    // 예: 'POST /api/v1/auth/login'
           note: '설명 텍스트',           // 예: '사용자 로그인 처리'
         },
         예:
         'v_login':      { type: '🖥 뷰', file: 'src/views/LoginView.vue', note: '로그인 화면' },
         'e_auth_login': { type: '⚡ API', file: 'app/api/auth.py', api: 'POST /auth/login', note: 'JWT 발급' },
      */
    };

    // ── 네트워크 초기화 ──
    const container = document.getElementById('graph');
    const nodes = new vis.DataSet(nodesData);
    const edges_ds = new vis.DataSet(edgesData);
    const network = new vis.Network(container, { nodes, edges: edges_ds }, {
      physics: {
        enabled: true, solver: 'forceAtlas2Based',
        forceAtlas2Based: { gravitationalConstant: -60, centralGravity: 0.005, springLength: 120, springConstant: 0.04, damping: 0.4 },
        stabilization: { iterations: 250 }
      },
      interaction: { hover: true, tooltipDelay: 200, navigationButtons: false, keyboard: false },
      edges: { width: 1.2, smooth: { type: 'dynamic' } },
      nodes: { borderWidth: 2, shadow: true },
      layout: { improvedLayout: true }
    });

    document.getElementById('stat-nodes').textContent = nodesData.length;
    document.getElementById('stat-edges').textContent = edgesData.length;

    // ── 클릭 — 노드 상세 패널 ──
    function getLabel(id) {
      const n = nodesData.find(x => x.id === id);
      return n ? n.label.replace(/\n/g, ' ') : id;
    }

    network.on('click', params => {
      const dc = document.getElementById('detailContent');
      if (!params.nodes.length) {
        dc.innerHTML = '<span class="empty">노드를 클릭하면<br/>상세 정보가 표시됩니다.</span>';
        return;
      }
      const id = params.nodes[0];
      const m = META[id] || {};
      const lbl = getLabel(id);
      const type = nodeTypeMap[id];
      const c = COLORS[type];
      const typeColor = c ? c.border : '#aaa';
      const connEdges = edgesData.filter(e => e.from === id || e.to === id);
      const outgoing = connEdges.filter(e => e.from === id).map(e => `<li><span class="conn-arrow">→</span>${getLabel(e.to)}</li>`).join('');
      const incoming = connEdges.filter(e => e.to === id).map(e => `<li><span class="conn-arrow">←</span>${getLabel(e.from)}</li>`).join('');
      dc.innerHTML = `
        <div class="detail-card">
          <div class="label">노드</div>
          <div class="value">${lbl}</div>
          ${m.type ? `<span class="badge" style="background:${typeColor}22;color:${typeColor};border:1px solid ${typeColor}">${m.type}</span>` : ''}
        </div>
        ${m.file ? `<div class="detail-card"><div class="label">파일</div><div class="value" style="font-family:monospace;font-size:11px">${m.file}</div></div>` : ''}
        ${m.api  ? `<div class="detail-card"><div class="label">API</div><div class="value" style="font-size:11px">${m.api}</div></div>` : ''}
        ${m.note ? `<div class="detail-card"><div class="label">설명</div><div class="value" style="font-size:11px;white-space:pre-wrap">${m.note}</div></div>` : ''}
        ${outgoing ? `<div class="detail-card"><div class="label">호출 대상 (→ ${connEdges.filter(e => e.from === id).length}개)</div><ul class="conn-list">${outgoing}</ul></div>` : ''}
        ${incoming ? `<div class="detail-card"><div class="label">호출처 (← ${connEdges.filter(e => e.to === id).length}개)</div><ul class="conn-list">${incoming}</ul></div>` : ''}
      `;
    });

    // ── 더블클릭 — 연결 노드 강조 ──
    network.on('doubleClick', params => {
      if (!params.nodes.length) { network.unselectAll(); return; }
      const id = params.nodes[0];
      const connected = edgesData.filter(e => e.from === id || e.to === id).flatMap(e => [e.from, e.to]);
      network.selectNodes([...new Set(connected)]);
    });

    // ── 필터 (타입 기반 토글) ──
    const allTypes = [...new Set(nodesData.map(n => nodeTypeMap[n.id]))];
    const activeTypes = new Set(allTypes);

    document.querySelectorAll('.filter-btn[data-type]').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.type;
        if (type === 'all') {
          const allOn = activeTypes.size === allTypes.length;
          activeTypes.clear();
          if (!allOn) allTypes.forEach(t => activeTypes.add(t));
          document.querySelectorAll('.filter-btn:not([data-type="all"])').forEach(b => b.classList.toggle('active', activeTypes.has(b.dataset.type)));
        } else {
          if (activeTypes.has(type)) activeTypes.delete(type); else activeTypes.add(type);
          btn.classList.toggle('active', activeTypes.has(type));
        }
        nodesData.forEach(n => {
          const t = nodeTypeMap[n.id];
          nodes.update({ id: n.id, hidden: !activeTypes.has(t), color: nodeColor(t) });
        });
      });
    });

    // ── 검색 ──
    document.getElementById('searchInput').addEventListener('input', e => {
      const q = e.target.value.trim().toLowerCase();
      nodesData.forEach(n => {
        const type = nodeTypeMap[n.id];
        if (!q) { nodes.update({ id: n.id, color: nodeColor(type) }); return; }
        const match = n.label.toLowerCase().includes(q);
        const c = COLORS[type] || { bg: '#1e293b', border: '#334155' };
        nodes.update({
          id: n.id,
          color: match
            ? { background: c.border, border: '#fff', highlight: { background: '#fff', border: c.border } }
            : { background: '#333', border: '#555' }
        });
      });
    });
  </script>
</body>
</html>
```

---

### database.md

```markdown
# 데이터베이스

## 스키마 요약 (schema.json 기반)

| 테이블 | 컬럼 수 | 주요 컬럼 | 인덱스 |
|--------|---------|---------|--------|
| TBL_ORDER | 12 | ID, STATUS, USER_ID | IDX_ORDER_USER |
| ... | ... | ... | ... |

## 주요 테이블 관계
[텍스트 또는 ASCII 다이어그램으로 주요 FK 관계 설명]

## SQL 인덱스 주요 항목 (sql_usage.json 기반)

| SQL ID | 호출 위치 | 주요 테이블 |
|--------|---------|---------|
| ORDER_S01 | OrderMapper.java:34 | TBL_ORDER |
| ... | ... | ... |

## 트랜잭션 경계
[transactions.json 요약]
```

---

### issues.md

```markdown
# 발견된 이슈

> validator·QA·dead_code 분석 결과. **자동 수정 없음 — 판단은 사람이.**

## HIGH 이슈

| # | 출처 | 내용 | 위치 |
|---|------|------|------|
| 1 | validator | [내용] | [파일] |

## MEDIUM 이슈
...

## LOW 이슈 / 데드 코드
[dead_code.json 요약 — 미사용 클래스·메서드]

## 권장 처리 순서
1. HIGH 이슈 먼저
2. 데드 코드 제거 전 `analyze-impact`로 확인 권장
```

---

## call_graph.json 파싱 실패 처리

파싱이 실패하거나 call_graph.json이 없는 경우 `wiki/call-graph.html`을 다음 형태로 생성:

```js
// 데이터 없음 상태 — 동일한 HTML 구조 유지, 빈 배열
const COLORS = {};
const nodesData = [];
const edgesData = [];
const META = {};
```

우측 사이드바 노드 상세 영역에 "데이터 없음 — harness-init을 Standard/Full Tier로 재실행해 call_graph.json을 생성하세요" 안내 메시지 표시.

---

## 완료 보고

`_workspace/07_wiki_build.md`:

```
=== WIKI BUILD REPORT ===

생성 시각: [YYYY-MM-DD HH:MM]
출력 경로: wiki/

생성된 파일:
- wiki/Home.md              ✅
- wiki/architecture.md      ✅
- wiki/workflows.md         ✅
- wiki/call-graph.html      ✅ (노드: N, 엣지: M, 허브: H, 데드코드: D)
                            ⚠ / ❌ (call_graph.json 없음 또는 파싱 실패)
- wiki/api-endpoints.md     ✅ / ⏭ (API 미탐지)
- wiki/database.md          ✅ / ⏭ (DB 미탐지)
- wiki/patterns.md          ✅ / ⏭ (patterns 미생성)
- wiki/external-systems.md  ✅ / ⏭ (외부 연동 없음)
- wiki/issues.md            ✅ / ⏭ (이슈 없음)

call-graph.html 상세:
- 파싱 형식: [A/B/C]
- 노드 타입 분포: endpoint N, function M, dependency K
- 허브 노드: [id 목록]
- 데드 코드 후보: [id 목록]
- 필터 그룹: [그룹명 목록]

사용된 소스:
- _workspace/01_analyzer_report.md: ✅
- _workspace/index/call_graph.json: ✅ / ❌
- _workspace/index/dead_code.json: ✅ / ⏭
- .claude/skills/: N개 파일
- .claude/patterns/: N개 파일

주의사항:
- [파싱 경고 or 스킵된 항목]

=== END ===
```

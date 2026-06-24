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

`callgraph.html`의 디자인·구조·라이브러리를 그대로 계승해서 생성한다.

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

#### Step 2: 노드 타입 정규화

call_graph.json의 type 값을 callgraph.html 스타일로 매핑:

| call_graph.json type | HTML type | 비고 |
|---------------------|-----------|------|
| controller, endpoint, route, api | `endpoint` | 파란 노드 |
| service, handler, manager, usecase | `function` | 초록/회색 노드 |
| dao, repository, mapper, store | `function` + group=dao | 주황 계열 |
| db, session, datasource, connection | `dependency` | 다이아몬드 노드 |
| util, helper, common | `function` + group=util | 회색 노드 |
| external, client, feign, soap | `function` + group=external | 별도 색상 |
| (없음/기타) | `function` | 기본 |

#### Step 3: 허브·데드 코드 자동 감지

**허브 노드 (HUB_IDS)**: in-degree 상위 노드 자동 탐지
```
in_degree = rawEdges에서 각 노드를 to로 갖는 엣지 수
임계값 = max(5, total_nodes × 0.15)   // 전체 노드의 15% 이상 in-degree
HUB_IDS = in_degree >= 임계값인 노드 id Set
```

dead_code.json이 있으면 해당 id도 HUB_IDS 후보에서 제외 + DEAD_IDS에 추가.

**데드 코드 후보 (DEAD_IDS)**: 다음 중 하나라도 해당하면 후보
```
1. in-degree = 0 AND type != "endpoint" AND type != "dependency"
2. dead_code.json에 명시된 id
3. node에 dead: true 플래그
```

#### Step 4: 그룹 자동 추론 (필터 버튼용)

그룹 결정 우선순위:
```
1. call_graph.json에 group 필드가 있으면 그대로 사용
2. 없으면 id에서 패키지/모듈명 추출:
   - "api.auth.xxx"    → group: "auth"
   - "api.order.xxx"   → group: "order"
   - "core.xxx"        → group: "core"
   - "com.example.order.controller.Xxx" → group: "order"
   - 첫 번째 또는 두 번째 세그먼트 기준
3. 타입 기반 fallback:
   - type=endpoint → group: 두 번째 세그먼트
   - type=dependency → group: "infra"
   - type=external → group: "external"
```

필터 버튼은 그룹 종류에 따라 자동 생성 (최대 6개: "전체" + 상위 5개 그룹).

#### Step 5: HTML 생성

아래 템플릿에 Step 1~4의 데이터를 주입해 `wiki/call-graph.html`을 생성한다.  
callgraph.html의 스타일(다크 테마, 색상, 레이아웃, 인터랙션)을 그대로 유지.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>[프로젝트명] 함수 호출 그래프</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/vis-network.min.js"></script>
  <link href="https://cdn.jsdelivr.net/npm/vis-network@9.1.9/dist/dist/vis-network.min.css" rel="stylesheet">
  <style>
    /* callgraph.html의 CSS를 그대로 유지 */
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; height:100vh; display:flex; flex-direction:column; overflow:hidden; }
    header { background:rgba(15,23,42,0.95); border-bottom:1px solid rgba(255,255,255,0.1); padding:12px 20px; display:flex; align-items:center; gap:16px; flex-shrink:0; z-index:10; }
    header h1 { font-size:18px; font-weight:700; color:#fff; }
    header .subtitle { font-size:13px; color:#64748b; }
    header a { margin-left:auto; color:#3b82f6; text-decoration:none; font-size:13px; }
    .legend { display:flex; gap:16px; padding:10px 20px; background:rgba(15,23,42,0.8); border-bottom:1px solid rgba(255,255,255,0.06); flex-wrap:wrap; flex-shrink:0; }
    .legend-item { display:flex; align-items:center; gap:6px; font-size:12px; color:#94a3b8; }
    .legend-dot { width:12px; height:12px; border-radius:50%; flex-shrink:0; }
    .controls { display:flex; gap:8px; padding:8px 20px; background:rgba(15,23,42,0.6); border-bottom:1px solid rgba(255,255,255,0.06); flex-shrink:0; flex-wrap:wrap; align-items:center; }
    .controls label { font-size:12px; color:#64748b; }
    .filter-btn { padding:4px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.15); background:rgba(255,255,255,0.05); color:#94a3b8; font-size:12px; cursor:pointer; transition:all 0.15s; }
    .filter-btn:hover, .filter-btn.active { background:#3b82f6; border-color:#3b82f6; color:#fff; }
    .main-area { display:flex; flex:1; overflow:hidden; }
    #network-container { flex:1; position:relative; }
    #network { width:100%; height:100%; }
    #info-panel { width:300px; background:rgba(30,41,59,0.95); border-left:1px solid rgba(255,255,255,0.08); padding:20px; overflow-y:auto; flex-shrink:0; display:none; }
    #info-panel.visible { display:block; }
    #info-panel h3 { font-size:14px; font-weight:600; color:#fff; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.1); }
    .info-row { margin-bottom:10px; }
    .info-label { font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:3px; }
    .info-value { font-size:13px; color:#e2e8f0; word-break:break-all; }
    .info-badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }
    .badge-endpoint { background:rgba(59,130,246,0.2); color:#93c5fd; }
    .badge-function { background:rgba(16,185,129,0.2); color:#6ee7b7; }
    .badge-dependency { background:rgba(245,158,11,0.2); color:#fcd34d; }
    .badge-hub { background:rgba(239,68,68,0.2); color:#fca5a5; }
    .connections-list { list-style:none; margin-top:8px; }
    .connections-list li { font-size:12px; color:#94a3b8; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.04); }
    .connections-list li:last-child { border-bottom:none; }
    .arrow-in { color:#6ee7b7; }
    .arrow-out { color:#93c5fd; }
    #close-panel { float:right; background:none; border:none; color:#64748b; cursor:pointer; font-size:16px; padding:0; line-height:1; }
    #close-panel:hover { color:#fff; }
    .stats-bar { padding:6px 20px; background:rgba(15,23,42,0.8); border-bottom:1px solid rgba(255,255,255,0.06); font-size:12px; color:#64748b; flex-shrink:0; display:flex; gap:16px; }
    .stats-bar span { color:#3b82f6; font-weight:600; }
  </style>
</head>
<body>

<header>
  <h1>[프로젝트명] 함수 호출 그래프</h1>
  <div class="subtitle">[스택 한 줄 설명 — analyzer_report 기반]</div>
  <a href="Home.md">← Wiki 홈</a>
</header>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div><span>API 엔드포인트</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#10b981"></div><span>서비스 함수</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div><span>의존성 (DB·설정)</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div><span>허브 함수 (in-degree ≥[임계값])</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:#8b5cf6;opacity:0.5;border:2px dashed #8b5cf6"></div><span>데드 코드 후보</span></div>
</div>

<div class="controls">
  <label>필터:</label>
  <button class="filter-btn active" data-filter="all">전체</button>
  <!-- [그룹별 필터 버튼 자동 생성 — 상위 5개 그룹] -->
  <!-- 예: <button class="filter-btn" data-filter="auth">인증</button> -->
</div>

<div class="stats-bar">
  노드: <span>[N]</span> &nbsp;|&nbsp; 엣지: <span>[M]</span> &nbsp;|&nbsp;
  허브 함수: <span>[HUB_COUNT]개</span> &nbsp;|&nbsp;
  데드 코드 후보: <span>[DEAD_COUNT]개</span>
</div>

<div class="main-area">
  <div id="network-container"><div id="network"></div></div>
  <div id="info-panel">
    <h3><button id="close-panel">✕</button>노드 정보</h3>
    <div id="node-details"></div>
  </div>
</div>

<script>
// ── 데이터 (call_graph.json → 변환) ─────────────────────────────────
const HUB_IDS = new Set([
  /* [hub node id 목록] */
]);

const DEAD_IDS = new Set([
  /* [dead code node id 목록] */
]);

const rawNodes = [
  /* [call_graph.json nodes를 변환한 배열]
     각 항목 형식:
     {id:"...", type:"endpoint"|"function"|"dependency", file:"...", method:"...", note:"...", group:"...", dead:true|false}
  */
];

const rawEdges = [
  /* [call_graph.json edges를 변환한 배열]
     각 항목 형식:
     {from:"...", to:"...", type:"call"|"depends"}
  */
];

// ── 필터 그룹 (그룹 자동 추론 결과) ─────────────────────────────────
const filterGroups = {
  all: null,
  /* [그룹명]: ['그룹에 속한 group값 목록'],
     예: auth: ['auth', 'core-auth'],
         order: ['order', 'order-service'],
  */
};

// ── 색상 및 노드 스타일 (callgraph.html 동일 로직) ──────────────────
function getNodeStyle(node) {
  const isHub = HUB_IDS.has(node.id);
  const isDead = node.dead || DEAD_IDS.has(node.id);

  if (isDead) {
    return {
      color:{background:'#1e293b',border:'#8b5cf6',highlight:{background:'#2d1f5e',border:'#a78bfa'}},
      borderWidth:2, borderDashes:[4,4], font:{color:'#8b5cf6'}, size:18
    };
  }
  if (isHub) {
    return {
      color:{background:'#7f1d1d',border:'#ef4444',highlight:{background:'#991b1b',border:'#f87171'}},
      borderWidth:3, font:{color:'#fca5a5',bold:true}, size:32,
      shadow:{enabled:true,color:'rgba(239,68,68,0.4)',size:12}
    };
  }
  if (node.type === 'endpoint') {
    return {
      color:{background:'#1e3a5f',border:'#3b82f6',highlight:{background:'#1e40af',border:'#60a5fa'}},
      borderWidth:2, font:{color:'#93c5fd'}, size:20
    };
  }
  if (node.type === 'dependency') {
    return {
      color:{background:'#451a03',border:'#f59e0b',highlight:{background:'#78350f',border:'#fcd34d'}},
      borderWidth:2, font:{color:'#fcd34d'}, size:18
    };
  }
  if (node.group === 'external' || node.group === 'sap' || node.group === 'mq') {
    return {
      color:{background:'#1a2e2a',border:'#10b981',highlight:{background:'#064e3b',border:'#34d399'}},
      borderWidth:2, font:{color:'#6ee7b7'}, size:18
    };
  }
  return {
    color:{background:'#1e293b',border:'#334155',highlight:{background:'#334155',border:'#64748b'}},
    borderWidth:1, font:{color:'#94a3b8'}, size:16
  };
}

function shortLabel(id) {
  const parts = id.split(/[.\/#]/);
  return parts[parts.length - 1];
}

// ── 노드/엣지 생성 ───────────────────────────────────────────────────
const nodes = rawNodes.map(n => {
  const style = getNodeStyle(n);
  return {
    id: n.id,
    label: shortLabel(n.id),
    title: `<div style="max-width:280px;font-family:monospace;font-size:12px;">
      <b style="color:#fff">${n.id}</b><br>
      <span style="color:#64748b">${n.file||''}</span><br>
      ${n.method?`<span style="color:#3b82f6">${n.method}</span><br>`:''}
      ${n.note?`<span style="color:#fbbf24">⚠ ${n.note}</span>`:''}
    </div>`,
    _raw: n,
    shape: n.type==='dependency'?'diamond':(HUB_IDS.has(n.id)?'star':'dot'),
    ...style
  };
});

const edges = rawEdges.map((e,i) => ({
  id: i, from: e.from, to: e.to, _type: e.type,
  color:{
    color: e.type==='depends'?'rgba(245,158,11,0.4)':'rgba(148,163,184,0.25)',
    highlight: e.type==='depends'?'#f59e0b':'#64748b'
  },
  dashes: e.type==='depends',
  arrows:{to:{enabled:true,scaleFactor:0.6}},
  width:1.5,
  smooth:{type:'curvedCW',roundness:0.1}
}));

// ── vis-network 초기화 ───────────────────────────────────────────────
const container = document.getElementById('network');
const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };

const options = {
  physics:{
    enabled:true, solver:'forceAtlas2Based',
    forceAtlas2Based:{gravitationalConstant:-80,centralGravity:0.01,springLength:120,springConstant:0.06,damping:0.4,avoidOverlap:0.8},
    stabilization:{iterations:200,updateInterval:10}
  },
  interaction:{hover:true,tooltipDelay:150,navigationButtons:true,keyboard:true,zoomView:true},
  layout:{improvedLayout:true},
  nodes:{borderWidth:2,font:{size:11,face:'Segoe UI,system-ui,sans-serif'}},
  edges:{smooth:{type:'dynamic'}}
};

const network = new vis.Network(container, data, options);
network.on('stabilizationIterationsDone',()=>network.setOptions({physics:{enabled:false}}));

// ── 노드 클릭 — 상세 패널 ────────────────────────────────────────────
network.on('click', params => {
  if (params.nodes.length > 0) {
    const nodeId = params.nodes[0];
    const node = rawNodes.find(n => n.id === nodeId);
    if (node) showNodeInfo(node, nodeId);
  } else if (params.edges.length === 0) {
    restoreAll();
    hidePanel();
  }
});

function showNodeInfo(node, nodeId) {
  const panel = document.getElementById('info-panel');
  const details = document.getElementById('node-details');
  const isHub = HUB_IDS.has(nodeId);
  const isDead = node.dead || DEAD_IDS.has(nodeId);
  const inEdges = rawEdges.filter(e => e.to === nodeId);
  const outEdges = rawEdges.filter(e => e.from === nodeId);
  let typeLabel = node.type, badgeClass = 'badge-function';
  if (node.type==='endpoint') badgeClass='badge-endpoint';
  if (node.type==='dependency') badgeClass='badge-dependency';
  if (isHub) { typeLabel='허브 함수'; badgeClass='badge-hub'; }
  details.innerHTML = `
    <div class="info-row"><div class="info-label">ID</div><div class="info-value" style="font-family:monospace;font-size:11px">${nodeId}</div></div>
    <div class="info-row"><div class="info-label">타입</div><div class="info-value">
      <span class="info-badge ${badgeClass}">${typeLabel}</span>
      ${isDead?'<span class="info-badge" style="background:rgba(139,92,246,0.2);color:#c4b5fd;margin-left:4px">데드 코드 후보</span>':''}
    </div></div>
    <div class="info-row"><div class="info-label">파일</div><div class="info-value" style="font-family:monospace;font-size:11px;color:#60a5fa">${node.file||'-'}</div></div>
    ${node.method?`<div class="info-row"><div class="info-label">메서드</div><div class="info-value" style="color:#34d399">${node.method}</div></div>`:''}
    ${node.note?`<div class="info-row"><div class="info-label">비고</div><div class="info-value" style="color:#fbbf24">${node.note}</div></div>`:''}
    <div class="info-row"><div class="info-label">호출하는 곳 (in-degree: ${inEdges.length})</div>
      <ul class="connections-list">
        ${inEdges.length===0?'<li style="color:#ef4444">없음 (진입점 또는 데드 코드)</li>':inEdges.map(e=>`<li><span class="arrow-in">→</span> ${e.from}</li>`).join('')}
      </ul>
    </div>
    <div class="info-row"><div class="info-label">호출하는 함수 (out-degree: ${outEdges.length})</div>
      <ul class="connections-list">
        ${outEdges.length===0?'<li style="color:#64748b">없음 (리프 노드)</li>':outEdges.map(e=>`<li><span class="arrow-out">→</span> ${e.to}</li>`).join('')}
      </ul>
    </div>`;
  panel.classList.add('visible');
}

function hidePanel() { document.getElementById('info-panel').classList.remove('visible'); }
document.getElementById('close-panel').addEventListener('click', hidePanel);

// ── 더블클릭 — 연결 강조 ─────────────────────────────────────────────
network.on('doubleClick', params => {
  if (params.nodes.length > 0) {
    const nodeId = params.nodes[0];
    const connectedEdges = network.getConnectedEdges(nodeId);
    const connectedNodes = network.getConnectedNodes(nodeId);
    data.nodes.update(rawNodes.map(n => ({id:n.id,opacity:0.15})));
    data.edges.update(rawEdges.map((_,i) => ({id:i,color:{color:'rgba(100,116,139,0.08)'}})));
    data.nodes.update([{id:nodeId,opacity:1}]);
    connectedNodes.forEach(nid => data.nodes.update([{id:nid,opacity:1}]));
    connectedEdges.forEach(eid => data.edges.update([{id:eid,color:{color:'#3b82f6'}}]));
  }
});

function restoreAll() {
  data.nodes.update(rawNodes.map(n => ({id:n.id,opacity:1})));
  data.edges.update(rawEdges.map((e,i) => ({id:i,color:{
    color:e.type==='depends'?'rgba(245,158,11,0.4)':'rgba(148,163,184,0.25)',
    highlight:e.type==='depends'?'#f59e0b':'#64748b'
  }})));
}

// ── 필터 버튼 ────────────────────────────────────────────────────────
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const groups = filterGroups[btn.dataset.filter];
    const updated = rawNodes.map(n => ({id:n.id,hidden:!(!groups||groups.includes(n.group))}));
    data.nodes.update(updated);
    const visible = new Set(updated.filter(n=>!n.hidden).map(n=>n.id));
    data.edges.update(rawEdges.map((e,i) => ({id:i,hidden:!visible.has(e.from)||!visible.has(e.to)})));
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

```html
<!-- 데이터 없음 상태 — 동일한 HTML 구조 유지, 빈 배열 + 안내 메시지 -->
const rawNodes = [];
const rawEdges = [];
```

stats-bar에 "데이터 없음 — harness-init을 Standard/Full Tier로 재실행해 call_graph.json을 생성하세요" 메시지 표시.

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
- callgraph.html 템플릿: ✅
- _workspace/01_analyzer_report.md: ✅
- _workspace/index/call_graph.json: ✅ / ❌
- _workspace/index/dead_code.json: ✅ / ⏭
- .claude/skills/: N개 파일
- .claude/patterns/: N개 파일

주의사항:
- [파싱 경고 or 스킵된 항목]

=== END ===
```

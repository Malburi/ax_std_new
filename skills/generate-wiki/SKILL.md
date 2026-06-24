---
name: generate-wiki
description: harness 산출물(_workspace + .claude)을 기반으로 프로젝트 wiki 페이지 세트를 생성한다. call_graph.json을 vis-network 기반 인터랙티브 HTML(call-graph.html)로 변환하는 것을 포함. HTML 템플릿은 wiki-builder 에이전트에 내장(외부 파일 의존성 없음). "wiki 만들어줘", "wiki 생성", "문서 wiki", "프로젝트 wiki 생성", "위키 만들어줘", "generate wiki", "위키 업데이트", "call graph 시각화", "호출 그래프 wiki" 요청 시 트리거. harness-init 완료 후 자동 제안.
---

# Generate Wiki (오케스트레이터)

`wiki-builder` 에이전트를 호출해 harness 산출물로부터 탐색 가능한 wiki 페이지 세트를 만든다.  
`_workspace/index/call_graph.json`을 **vis-network 기반 인터랙티브 HTML 파일(call-graph.html)**로 변환한다.  
HTML 구조·디자인은 `wiki-builder.md`에 내장된 템플릿을 사용하며 외부 파일 의존성이 없다.

---

## Phase 0: 사전 확인

### harness 존재 확인

| 확인 대상 | 없을 경우 |
|---------|---------|
| `_workspace/01_analyzer_report.md` | "harness-init을 먼저 실행해주세요" 안내 후 중단 |
| `CLAUDE.md` | 경고만 표시, 계속 진행 |
| `_workspace/index/call_graph.json` | call-graph.html을 "데이터 없음" 상태로 생성 |

### 기존 wiki 감지

`wiki/` 폴더가 이미 존재하면:

```
기존 wiki가 발견되었습니다 (wiki/ 폴더).
덮어쓰시겠습니까? (Y/N)
  Y: 기존 wiki/ → wiki_prev/ 로 백업 후 재생성
  N: 중단
```

사용자 확인 후 진행.

---

## Phase 1: 페이지 범위 확인

기본적으로 발견된 데이터 기반으로 자동 결정하지만, 사용자가 범위를 지정할 수 있다:

```
사용 가능한 wiki 페이지:
✅ Home, architecture, workflows          (항상 생성 — .md)
✅ call-graph.html                        (항상 생성 — vis-network 인터랙티브 HTML)
✅ api-endpoints     (API 엔드포인트 탐지됨 / ❌ 미탐지)
✅ database          (DB 사용 탐지됨 / ❌ 미탐지)
✅ patterns          (patterns/ 파일 있음 / ❌ 없음)
✅ external-systems  (외부 연동 탐지됨 / ❌ 없음)
✅ issues            (validator/QA 이슈 있음 / ❌ 없음)

전체 생성하시겠습니까? (Y) / 특정 페이지만 선택하시겠습니까? (페이지명 입력)
```

"Y" 또는 응답 없이 "생성해줘"면 전체 진행.  
페이지명이 명시되면 해당 페이지만 생성.

---

## Phase 2: wiki-builder 호출

```
Agent(
  subagent_type="general-purpose",
  description="wiki 페이지 생성",
  prompt="<wiki-builder 에이전트 지침에 따라 wiki 페이지 세트를 생성한다.
  프로젝트 루트: [절대경로].
  wiki 출력 경로: [절대경로]/wiki/.
  생성할 페이지: [Phase 1에서 확정된 목록].
  call_graph.json 경로: _workspace/index/call_graph.json.
  HTML 템플릿: wiki-builder.md 내장 (외부 파일 불필요).
  출력: wiki/ 하위 페이지 파일들 + _workspace/07_wiki_build.md>",
  model="sonnet"
)
```

---

## Phase 3: 결과 보고

`_workspace/07_wiki_build.md`를 읽어 요약 보고:

```
wiki 생성 완료

출력 위치: wiki/

생성된 파일:
- wiki/Home.md
- wiki/architecture.md
- wiki/workflows.md
- wiki/call-graph.html   ★ (노드: N개, 엣지: M개, 허브: H개, 데드코드 후보: D개)
- wiki/api-endpoints.md  (있는 경우)
- wiki/database.md       (있는 경우)
- wiki/patterns.md       (있는 경우)
- wiki/external-systems.md (있는 경우)
- wiki/issues.md         (있는 경우)

call-graph.html:
  - vis-network 라이브러리: CDN (cdn.jsdelivr.net/npm/vis-network@9.1.9)
  - 노드 타입: endpoint N개, function M개, dependency K개
  - 허브 노드: [id 목록]
  - 데드 코드 후보: [id 목록]
  - 필터 그룹: [그룹명 목록]
  - 인터랙션: 클릭(상세패널), 더블클릭(연결강조), 필터버튼, 줌/팬

주의사항:
[파싱 경고·스킵 항목 있으면 표시]

다음 단계:
  call-graph.html 보기: 브라우저로 wiki/call-graph.html 직접 열기
  GitHub Pages:        wiki/ 폴더를 gh-pages 브랜치에 push (HTML 그대로 렌더링)
  GitHub Wiki (MD):    Home.md·architecture.md·workflows.md 등 .md 파일만 wiki repo에 push
                       (call-graph.html은 별도 gh-pages로 호스팅 권장)
  로컬 서버:            cd wiki && python -m http.server 8080 → localhost:8080/call-graph.html
  wiki 업데이트:        "wiki 업데이트해줘" (기존 wiki_prev/ 백업 후 재생성)
```

---

## Phase 4: call-graph.html 특이사항 안내 (조건부)

call_graph.json이 없거나 빈 경우:

```
call-graph.html은 생성됐지만 call_graph.json이 없어 그래프 데이터가 없습니다.

해결 방법:
  1. harness-init을 Standard/Full Tier로 재실행 (인덱스 생성 포함)
  2. 또는: "인덱스만 갱신해줘" → analyzer incremental 실행 → "wiki 업데이트해줘"
```

---

## 시나리오 예시

### 시나리오 1: harness-init 완료 후 wiki 생성
사용자: "wiki 생성하시겠습니까?" → "예"

1. Phase 0: _workspace/01_analyzer_report.md ✅, templates/callgraph.html 템플릿 ✅, call_graph.json ✅
2. Phase 1: 전체 페이지 자동 확인 (DB·외부연동 탐지 기반)
3. Phase 2: wiki-builder 실행
4. Phase 3: wiki/ 9개 파일 생성 보고 (call-graph.html 포함)

### 시나리오 2: call graph만 별도 생성
사용자: "call graph html 만들어줘"

1. Phase 0: call_graph.json ✅, callgraph.html 템플릿 ✅
2. Phase 1: call-graph.html 페이지만 선택
3. Phase 2: wiki-builder 실행 (call-graph.html만)
4. Phase 3: "wiki/call-graph.html 생성 완료. 노드 47개, 엣지 132개. 허브: 3개. 브라우저로 직접 열어서 확인하세요."

### 시나리오 3: 코드 변경 후 wiki 업데이트
사용자: "인덱스 갱신 후 wiki 업데이트해줘"

1. Phase 0: 기존 wiki/ 감지 → 백업 제안
2. 사용자 Y → wiki_prev/ 백업 후 재생성
3. Phase 2~3: 최신 산출물 기반 wiki 재생성 (call-graph.html 포함)

---

## 원칙

### wiki는 산출물의 뷰, 소스는 harness
wiki 파일은 `_workspace/`·`.claude/`에서 *생성*된다.  
wiki 파일을 직접 편집해도 다음 `generate-wiki` 실행 시 덮어씌워진다.

### call-graph.html은 정적 분석 기반
런타임 동적 호출, 리플렉션, AOP 적용 메서드는 포함되지 않을 수 있다.  
call-graph.html 상단 subtitle에 이 한계를 항상 명시한다.

### HTML 템플릿은 wiki-builder.md에 내장
call-graph.html 생성에 필요한 전체 HTML 템플릿은 `wiki-builder.md` 안에 완전히 내장되어 있다.  
외부 템플릿 파일을 참조하지 않으므로 파일 누락·삭제 위험이 없다.

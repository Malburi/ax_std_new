# CLAUDE.md

> 💡 **토큰 비용 절감 꿀팁 (바이브 코딩 시 필수)**
> - **코드 수정 후 전체 재분석 금지**: 전체 재초기화 대신 `"인덱스만 갱신해줘"`라고 요청하면 변경된 파일만 부분 증분(Incremental) 분석합니다.
> - **부분 단계 실행**: 특정 요소만 갱신할 때는 `"스킬만 다시 생성"`, `"패턴만 다시"`, `"validator만 실행"` 등으로 필요한 단계만 핀포인트 요청하세요.
> - **경량 분석 모드 (Standard)**: 토큰 소비를 줄이려면 하네스 초기화 시 `"빠르게 하네스 구축해줘"` 문구를 포함하면 Standard Tier로 실행합니다 (기본은 Full, Lite Tier는 폐지됨).

## 보편 에이전트 행동 원칙

> Andrej Karpathy 가이드라인 기반. 모든 에이전트·스킬에 공통 적용.

### 1. 코딩 전 사고

구현 전 반드시.

- **가정 명시**: 불확실한 사항은 숨기지 않고 사용자에게 알린다.
- **해석 충돌**: 복수 해석이 가능하면 모두 제시하고 선택을 구한다.
- **단순 대안**: 더 간단한 방법이 있으면 먼저 제안한다. 무조건 실행하지 않는다.
- **모호함 정지**: 요청이 불명확하면 멈추고 이름을 붙여 질문한다.

### 2. 단순성 우선

요청된 것만 만든다.

- 요청받지 않은 기능·추상화·유연성은 추가하지 않는다.
- 새 에이전트·스킬 추가 전 자문: "기존 에이전트로 해결되는가?"
- 200줄로 해결 가능한데 50줄로 되면 50줄로 쓴다.

### 3. 외과적 변경

요청된 부분만 건드린다.

- 인접 코드·주석·포맷을 "개선"하지 않는다.
- 내 변경이 만든 미사용 import/변수/함수만 제거한다.
- 기존 dead code는 언급하되 삭제하지 않는다.
- 변경된 모든 줄은 사용자 요청에 직접 연결되어야 한다.

### 4. 목표 기반 실행

→ `_workspace/` 파이프라인(Phase 2-1~2-5 + Phase 4 harness-evaluator)으로 구현됨.

### 5. 한국어 출력 규칙

한국어 문장은 마침표(`.`), 물음표(`?`), 느낌표(`!`)로 끝낸다.  
목록이나 예시가 이어져도 문장 종결에 콜론(`:`)을 쓰지 않는다.  
코드·키-값 쌍·레이블 내부의 콜론은 허용.

### 6. 새 파일 헤더 주석

새 `.py` 파일 첫 줄: `# 이 파일의 역할을 한 줄 한국어로`  
`agents/*.md` 에이전트: frontmatter `description` 필드가 헤더 역할을 대신함.  
config / template / requirements 파일은 헤더 생략.

### 7. 계획 + 체크리스트 + 컨텍스트

→ `_workspace/` 파일 체계(writer_decisions.json · CLAUDE.md 변경이력)로 구현됨.

### 8. 완료 전 테스트 실행

→ `validator_checks.py` + `qa_boundary6.py` + `harness-evaluator` 루프로 구현됨.

### 9. 의미 단위 커밋

- 하나의 논리적 변경이 완료되면 즉시 커밋한다. 사용자 요청 전에.
- 커밋 메시지는 한 문장으로 설명 가능한 단위만.
- 좋은 예: `"change-safety: opus→sonnet 모델 수정"`
- 나쁜 예: `"에이전트 4개 수정 + 버그 수정 + 문서 업데이트"` (3개로 분리)
- 파트너 저장소 커밋은 자동 실행하지 않는다. 반드시 확인 후.

### 10. 에러 읽기, 추측 금지

- 전체 에러 메시지와 스택 트레이스를 읽는다. 키워드만 보지 않는다.
- 기억 기반의 "흔한 수정"을 확인 없이 적용하지 않는다.
- 원인 불명 시: print/log를 추가해 상태를 확인한 후 수정한다.
- WARN 후 폴백한 경우 폴백 사유를 `_workspace/`에 기록한다.

---

**harness-fin** — ITO/SI 조직을 위한 확장 메타 하네스 템플릿.

## 이 저장소의 역할

`.claude/` 폴더에 *코드베이스 분석 + 수정/개발/마이그레이션 작업까지* 지원하는 에이전트 팀과 워크플로우 스킬이 포함되어 있다.

대상 프로젝트의 코드베이스를 분석해 맞춤형 CLAUDE.md / 워크플로우 스킬 / 도메인 에이전트 / 패턴 / 인덱스를 한 번에 생성하고, 이후 *수정·개발·마이그레이션 작업*까지 끊김 없이 지원한다.

[neoruler001/harness-new](https://github.com/neoruler001/harness-new)의 4-에이전트 파이프라인을 기반으로 [revfactory/harness](https://github.com/revfactory/harness)의 메타 방법론을 확장 적용했다.

## 실행 모드

**에이전트 팀** — `TaskCreate` 의존성 + `_workspace/` 파일 기반 산출물 전달

**팀 구성:**
- 분석/생성 파이프라인: `analyzer` → `writer` → (`pattern-extractor`) → `validator` → `qa`
- 품질 루프: `spec-clarifier` (Phase -1, 사전 명세화) + `harness-evaluator` (Phase 4, 사후 eval)
- 작업용 에이전트: `impact-analyzer`, `change-safety`, `migration-planner`, `test-generator`, `sql-reviewer`, `legacy-decoder`, `doc-syncer`, `logic-tracer`, `feature-finder`, `api-bridge`
- 크로스 리포 에이전트: `api-bridge` (백엔드↔프론트엔드 API 계약 추출·검증·스텁 생성)

## 파일 구조

플러그인 표준 레이아웃 — `agents/`는 flat, `skills/`는 폴더/`SKILL.md`.

| 경로 | 역할 |
|------|------|
| `.claude-plugin/marketplace.json` | 마켓플레이스 카탈로그 (단일 저장소 = 단일 플러그인) |
| `.claude-plugin/plugin.json` | 플러그인 매니페스트 |
| `skills/harness-init/SKILL.md` | 메인 오케스트레이터 (분석 → 생성 → 검증 → QA → 패턴) |
| `skills/analyze-impact/SKILL.md` | 영향도 분석 워크플로우 |
| `skills/safe-modify/SKILL.md` | 안전 변경 워크플로우 (사전 영향 + 사후 안전성) |
| `skills/scaffold-feature/SKILL.md` | 컨벤션 기반 신규 기능 스캐폴딩 |
| `skills/plan-migration/SKILL.md` | 마이그레이션 계획 워크플로우 |
| `skills/review-sql/SKILL.md` | SQL 종합 리뷰 워크플로우 |
| `skills/spec-gate/SKILL.md` | 작업 전 소크라테스식 명세 명확화 워크플로우 (Ouroboros 영감) |
| `skills/harness-clean/SKILL.md` | harness 전체 제거 워크플로우 (확인 후 안전 삭제) |
| `skills/trace-logic/SKILL.md` | 기능·API·화면 처리 흐름 추적 워크플로우 |
| `skills/find-feature/SKILL.md` | 기능명·키워드로 관련 코드 위치 탐색 워크플로우 |
| `skills/generate-wiki/SKILL.md` | harness 산출물 → wiki 페이지 세트 생성 (call_graph.json → vis-network 인터랙티브 HTML) |
| `skills/pair-init/SKILL.md` | 별도 저장소 백엔드·프론트엔드 연동 (pair_config.md 생성 + API 계약 추출 + 드리프트 검증) |
| `skills/cross-repo-scaffold/SKILL.md` | 전체 스택 기능 동시 스캐폴딩 (백엔드 레이어 + 프론트엔드 서비스·컴포넌트·라우트) |
| `skills/cross-repo-modify/SKILL.md` | 페어 연동된 양쪽 저장소에 기존 기능 개선/수정 동시 반영 (safe-modify + 파트너 영향 확인·반영 게이트) |
| `skills/sync-wiki/SKILL.md` | (v1) 시스템 wiki를 폴더(wiki/)와 MSSQL 단일 테이블(harness_wiki_pages) 사이에서 상호 변환 |
| `skills/publish-wiki/SKILL.md` | 폴더 wiki를 별도 프로젝트 wiki-hub(중앙 DB, 시스템·컴포넌트·버전관리)에 발행 — `wiki-hub-publish` 콘솔 명령 호출 |
| `skills/wiki-hub/SKILL.md` | 별도 프로젝트 wiki-hub 실행 — 여러 시스템 wiki 통합 열람·검색·버전 이력·되돌리기 (`wiki-hub-serve` 콘솔 명령 호출) |
| `agents/spec-clarifier.md` | Phase -1: 소크라테스 인터뷰 + 모호성 점수화 + 명세 리포트 생성 |
| `agents/harness-evaluator.md` | Phase 4: 4차원 품질 평가 (커버리지·정확도·실행가능성·컨텍스트) + fix_targets 반환 |
| `agents/analyzer.md` | Phase 2-1: 심층 분석 (스택 + 의존성 그래프 + 데이터 흐름 + 트랜잭션 + 외부 통신 + 인덱스 생성) |
| `agents/writer.md` | Phase 2-2: 하네스 파일 + 워크플로우 스킬 생성 |
| `agents/pattern-extractor.md` | Phase 2-2.5: 컨벤션 추출 (writer 직후) |
| `agents/validator.md` | Phase 2-3: 구조 검증 + 인덱스 무결성 |
| `agents/qa.md` | Phase 2-4: 경계면 교차 비교 (Boundary 1~6) |
| `agents/impact-analyzer.md` | 변경 영향도 분석 |
| `agents/change-safety.md` | 변경 안전성 평가 (GO/HOLD/STOP) |
| `agents/migration-planner.md` | 스택 마이그레이션 계획 |
| `agents/test-generator.md` | 회귀 테스트 골격 생성 |
| `agents/sql-reviewer.md` | SQL 다각도 리뷰 |
| `agents/legacy-decoder.md` | 레거시 코드 역공학 |
| `agents/doc-syncer.md` | 코드 ↔ 문서 동기화 점검 |
| `agents/logic-tracer.md` | 기능·API·화면 처리 흐름을 진입점 → Controller → Service → DB까지 추적 |
| `agents/feature-finder.md` | 기능명·키워드로 관련 파일·클래스·메서드·SQL 위치 탐색 |
| `agents/api-bridge.md` | REST API 계약 추출(extract)·드리프트 검증(validate)·프론트 스텁 생성(generate-stub)·파트너 영향 확인(check-impact) |
| `agents/lib/wiki_generator.py` + `agents/lib/wiki_content.py` | harness 산출물을 그대로 wiki 페이지로 변환(zero-LLM) + call_graph.json → vis-network 인터랙티브 HTML |
| `agents/lib/analyzer_index_summary.py` | analyzer 리포트 Section B/D(의존성그래프·트랜잭션·외부통신·환경분기·데드코드·DB스키마)를 인덱스 JSON에서 기계 생성(zero-LLM) |
| `agents/lib/pattern_tally.py` | pattern-extractor의 `05_patterns_extracted.md` 집계 표(샘플수·신뢰도·안티패턴 수)를 개별 패턴 파일에서 기계 취합(zero-LLM) |
| `agents/lib/validator_checks.py` | validator 체크 1,2,3,4,6,7,8,9(파일존재·트리거품질·경로교차·보안·인덱스무결성·이력)를 기계 실행(zero-LLM), 체크 5·10만 validator(LLM)에 남김 |
| `agents/lib/qa_boundary6.py` | qa Boundary 6(워크플로우 스킬 ↔ 인덱스 의존성)을 기계 실행(zero-LLM) |

> 본 저장소 내의 `agents/`·`skills/` 경로는 *플러그인 소스*이며, 설치된 대상 프로젝트에서 출력되는 결과물은 여전히 대상 프로젝트의 `.claude/skills/...`·`.claude/agents/...`에 기록된다. 에이전트/스킬 본문 내부의 `.claude/...` 경로는 *대상 프로젝트* 경로를 의미한다.

## 자동 워크플로우

| 상황 | 트리거 스킬 |
|------|---------|
| 하네스 초기화 전 명세 명확화 | `spec-gate` |
| 하네스 초기화 / 재초기화 | `harness-init` |
| 하네스 전체 제거 | `harness-clean` |
| 변경 영향도 분석 | `analyze-impact` |
| 안전한 변경 진행 | `safe-modify` |
| 컨벤션 따라 신규 기능 생성 | `scaffold-feature` |
| 스택 마이그레이션 계획 | `plan-migration` |
| SQL 리뷰 | `review-sql` |
| 레거시 코드 해석 | `legacy-decoder` 직접 호출 |
| 문서 동기화 | `doc-syncer` 직접 호출 |
| 기능·API 처리 흐름 추적 | `trace-logic` |
| 기능·키워드로 코드 위치 탐색 | `find-feature` |
| harness 산출물 → wiki 생성 | `generate-wiki` |
| 백엔드·프론트엔드 별도 저장소 연동 | `pair-init` |
| 전체 스택 기능 동시 생성 | `cross-repo-scaffold` |
| 기존 기능 개선/수정 양쪽 저장소 동시 반영 | `cross-repo-modify` |
| API 드리프트 감지 | `pair-init` 재실행 |
| 프론트엔드 서비스 스텁만 생성 | `api-bridge` 직접 호출 |
| 시스템 wiki 저장 위치(폴더/v1 DB) 상호 변환 | `sync-wiki` |
| 생성된 wiki를 중앙 허브(wiki-hub)에 발행 | `publish-wiki` |
| 여러 시스템 wiki 통합 열람·검색·버전관리 | `wiki-hub` |

## 에이전트 수정

에이전트 개선은 `agents/[name].md` 파일을 직접 수정한다.  
변경사항은 아래 변경 이력 테이블에 기록한다 (revfactory/harness Phase 5-4 템플릿).

새 에이전트 추가:
1. `agents/[name].md` 작성 (frontmatter + 본문)
2. 호출하는 오케스트레이터 스킬(`skills/<name>/SKILL.md`)에 등록
3. 변경 이력 테이블에 기록

새 스킬 추가:
1. `skills/[name]/SKILL.md` 폴더 + 파일 생성 (frontmatter 필수)
2. 변경 이력 테이블에 기록

## 변경 이력

| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-06-02 | harness-new 기반 확장 — P0(impact-analyzer, change-safety) + P1(pattern-extractor, migration-planner) + P2(test-generator, sql-reviewer, legacy-decoder, doc-syncer) + 워크플로우 스킬 5종(analyze-impact, safe-modify, scaffold-feature, plan-migration, review-sql) + analyzer 심층 분석(의존성 그래프, 데이터 흐름, 트랜잭션, 외부 통신, 환경 분기, 데드 코드) + 인덱스 레이어(_workspace/index/*.json) | 전체 | ITO/SI 조직의 수정/개발/마이그레이션 작업까지 끊김 없이 지원하기 위함 |
| 2026-06-02 | Claude Code 플러그인 표준 레이아웃으로 재구성 — `.claude/agents/`·`.claude/skills/` 중복본 제거, 루트 `agents/`·`skills/<name>/SKILL.md` 단일 source-of-truth로 정리, `.claude-plugin/marketplace.json`·`plugin.json` 추가 | 저장소 구조 | `/plugin marketplace add neoruler001/ax-std-harness`로 설치 가능하도록 |
| 2026-06-02 | Vue.js 스택 지원 추가 — Vue 2/3, Nuxt 2/3, Pinia/Vuex, Vue Router, Vite, Vue CLI 탐지 + QA Boundary + 마이그레이션 매핑 (Vue 2→3, Vuex→Pinia, Nuxt 2→3, Vue CLI→Vite) | analyzer / qa / docs/stack-matrix / README | 프런트엔드 스택 커버리지 확장 |
| 2026-06-03 | 로직 탐색 에이전트 2종 추가 — `logic-tracer`(진입점→DB 처리 흐름 추적) + `feature-finder`(기능명·키워드 코드 위치 탐색) + 트리거 스킬 2종(`trace-logic`, `find-feature`) | agents / skills / CLAUDE.md | 특정 로직·기능 위치 탐색 요구 대응 |
| 2026-06-03 | 에이전트 모델 최적화 — opus→sonnet 8종(change-safety, pattern-extractor, validator, qa, test-generator, sql-reviewer, doc-syncer, logic-tracer). opus 유지 5종(analyzer, writer, legacy-decoder, impact-analyzer, migration-planner) | agents/ | 패턴 기반 처리 작업에 opus 불필요, 비용 절감 |
| 2026-06-03 | harness-init 3-Tier 적응 실행 — 복잡도 점수(파일수+DB/ORM+레거시+멀티모듈+외부시스템) 기반 Lite/Standard/Full 자동 분기. Lite: analyzer lite(sonnet)+writer(sonnet)+validator, QA·pattern 스킵. Standard: analyzer init(sonnet)+선택적 Phase B+writer(sonnet)+pattern+validator, QA 스킵. Full: 기존 파이프라인. 사용자 override 키워드 지원. | skills/harness-init / agents/analyzer | 프로젝트 규모 무관 전체 파이프라인 실행으로 인한 토큰·시간 낭비 해소 |
| 2026-06-04 | harness-clean 스킬 추가 — CLAUDE.md·.claude/skills/·agents/·patterns/·_workspace/ 안전 제거 + 플러그인 언인스톨 안내 | skills/harness-clean / CLAUDE.md | 마음에 안 들면 롤백할 수 있어야 표준으로 쓸 수 있음 |
| 2026-06-04 | Ouroboros 명세 게이트 + Karpathy eval 루프 접목 — spec-clarifier(sonnet, Phase -1: 소크라테스 인터뷰·모호성점수·GO신호) + harness-evaluator(sonnet, Phase 4: 4차원 품질평가·PASS/PARTIAL/RETRY·fix_targets 기반 타겟 재생성·1회 루프) + spec-gate 스킬 + harness-init Phase -1/-4 추가 + analyzer에 spec_context 전달 | agents/spec-clarifier, agents/harness-evaluator, skills/spec-gate, skills/harness-init, CLAUDE.md | 명세 모호성 제거(Ouroboros)·자기 개선 루프(Karpathy)로 harness 생성 품질 향상 |
| 2026-06-24 | wiki 생성 기능 추가 — `wiki-builder`(sonnet, harness 산출물→wiki 페이지·call_graph.json→vis-network 인터랙티브 HTML 변환·callgraph.html 템플릿 계승) + `generate-wiki` 오케스트레이터 스킬(기존 wiki 백업·페이지 범위 선택·call-graph.html 전용 페이지) + harness-init Phase 3.5(완료 후 wiki 생성 제안) | agents/wiki-builder, skills/generate-wiki, skills/harness-init, CLAUDE.md | harness 완료 후 탐색 가능한 wiki 문서 자동 생성 요구 대응 |
| 2026-06-30 | call-graph.html 디자인 전면 개편 — 우측 고정 사이드바(통계·범례·노드 상세), 타입 기반 필터 토글(opacity active/inactive), 헤더 실시간 검색, 7가지 시각 타입(view·endpoint·function·dao·external·db_table·util)·노드 모양(ellipse·box·hexagon·diamond·database·dot), COLORS+nodeTypeMap+META+mkNode() 구조로 교체. 기존 group 기반 필터·info-panel slide 방식 제거 | agents/wiki-builder, skills/generate-wiki | mfs-test 실사례 기반 디자인 표준화 |
| 2026-06-29 | Type B(별도 저장소) 크로스 리포 지원 추가 — `api-bridge`(sonnet, API 계약 extract/validate/generate-stub/check-impact 4-mode) + `pair-init` 스킬(두 레포 연동·pair_config.md 생성·API 드리프트 검증) + `cross-repo-scaffold` 스킬(전체 스택 기능 동시 스캐폴딩) + analyzer Step 0.5(pair_config 감지) + Step 15.5(API 계약 추출) + writer 파트너 섹션 + cross-repo-scaffold.md 조건부 생성 + impact-analyzer Step 8.5(파트너 영향) + harness-init Phase 3.5(pair-init 제안, 기존 wiki 제안은 Phase 3.6으로 이동) + scaffold-feature pair_config 인식 | agents/api-bridge, skills/pair-init, skills/cross-repo-scaffold, agents/analyzer, agents/writer, agents/impact-analyzer, skills/harness-init, skills/scaffold-feature, CLAUDE.md | 백엔드·프론트엔드 별도 저장소 구조에서 API 계약 기반 연계 개발·바이브 코딩 지원 |
| 2026-06-30 | harness-init Phase -2 추가 — harness-init 시작 시 프로젝트 구조(모노레포/멀티레포/단일 스택) 사용자 확인 질문. 멀티레포 선택 시 파트너 경로·역할·API URL 선수집 → Phase 3.5에서 pair-init 자동 실행(확인 생략). Phase 3.5를 분기 처리(모노레포/단일 스택은 스킵, 멀티레포+파트너 정보 있으면 자동 실행, Phase -2 스킵 시 기존 질문 방식 유지) | skills/harness-init, CLAUDE.md | harness-init 시작 시 구조 파악으로 pair-init 연동을 자연스러운 흐름으로 통합 |
| 2026-07-14 | writer 출력 정적 스킬 5종(analyze-impact/safe-modify/scaffold-feature/plan-migration/review-sql) 프로그램식 배포로 전환 — `agents/lib/skills/*.template.md`(정적 원본, 변수 없음) + `agents/lib/skills_builder.py`(harness-init Phase 2-2.3, `_workspace/02_writer_files.md`의 생성 결정 파싱 후 무-LLM 복사). writer는 이 5종 대신 plan-migration/review-sql 생성 여부 판단만 수행. CLAUDE.md 상단에 부분 실행·incremental 유도 배너 추가. impact-analyzer 모델은 opus 유지(2026-06-03 결정 재확인) | agents/lib/skills_builder.py, agents/lib/skills/*.template.md, agents/writer, skills/harness-init, CLAUDE.md | writer가 프로젝트별 변수 없는 고정 텍스트를 매번 LLM으로 재작성하던 출력 토큰 낭비 제거. 이전 시도(하이브리드 빌더)가 writer.md 미동기화·조건부 판단 로직 누락으로 5종 중 2종만 배포되고 CLAUDE.md/domain-expert/patterns 등 그룹 A 산출물이 누락되는 회귀를 유발해 재구현 |
| 2026-07-14 | 멀티레포 파트너 자동 하네스 생성 + 바이브코딩 크로스 리포 수정 지원 — (1) `pair-init` Phase 1: 파트너 하네스 없을 때 3지선다("자동 생성"/"없이 진행"/"중단") 추가, "자동 생성" 선택 시 subagent로 파트너 루트에서 harness-init 자체를 대신 실행. (2) `harness-init` Phase 3.5: harness-init이 주도하는 흐름(Phase -2에서 멀티레포 확인됨)에서는 위 3지선다 재질문 없이 자동 생성 적용 + 그 Agent 호출을 Phase 4(harness-evaluator) 호출과 같은 메시지에서 병렬 실행하도록 명시. (3) `harness-init` Phase 3.6: 파트너 하네스가 있으면 "통합 wiki 생성" 3지선다로 분기(단독 wiki를 선택해도 pair_config.md 기반 자동 병합이라 통합 그래프가 나온다는 점 안내) — 프론트엔드에서 실행해도 backend 쪽 call_graph.json이 자동 병합됨을 명시. (4) 신규 스킬 `cross-repo-modify` 추가 — 한쪽에서 지시한 기존 기능 개선을, `impact-analyzer`(시작 측) → `api-bridge check-impact`(파트너 영향 확인) → 사용자 확인 게이트 → 양쪽 변경 적용 → 양쪽 `change-safety` + `api-bridge validate`(드리프트 재검증) 순으로 안전하게 양쪽 저장소에 반영. 파트너 저장소는 별도 git/배포 프로세스라는 전제 하에, 파트너 파일 수정 전 반드시 확인받고 커밋은 절대 자동 실행하지 않음. (5) `wiki_generator.py`의 `merge_partner_call_graph()`가 병합 결과(merged 여부·파트너 노드 수·추론된 크로스 엣지 수·스킵 사유)를 `07_wiki_build.md`에 명시적으로 기록하도록 확장 — 이전에는 콘솔 로그에만 남고 보고서엔 안 남아 사용자가 통합 여부를 확인할 방법이 없었음. `generate-wiki` Phase 3 보고에도 반영. 프론트엔드 루트 기준 병합 시나리오(파트너 노드 2개 병합, 크로스 엣지 1개 정확히 추론)로 재검증 완료 | skills/pair-init, skills/harness-init, skills/cross-repo-modify, agents/lib/wiki_generator.py, skills/generate-wiki, CLAUDE.md | 백엔드·프론트엔드가 완전히 분리된 저장소/배포 구조에서 한쪽 harness-init만으로 양쪽 하네스·통합 wiki가 갖춰지고, 이후 바이브 코딩 개선 지시도 양쪽에 안전하게 전파되도록 지원 |
| 2026-07-14 | 하이브리드 빌드 확장 + wiki 회귀 수정 4건 — (1) `domain-expert.md`를 writer 재작성 대신 `_workspace/01_analyzer_report.md` 그대로 복사(skills_builder.py)로 전환, 100% 중복 출력 제거. (2) CLAUDE.md 하이브리드화 — `agents/lib/claude_md.template.md`(고정 워크플로우 표·변경이력 헤더·파트너 섹션 서식) + writer는 `_workspace/claude_md_fields.json`에 서술형 필드 7개만 출력, skills_builder.py가 조립(파트너 섹션은 pair_config.md 값을 그대로 옮기는 것뿐이라 완전 무-LLM). (3) `wiki_generator.py` 크로스 리포(pair-init) 그래프 병합 미구현 상태(주석만 있던 TODO)를 실제 구현 — 파트너 call_graph.json 노드/엣지 ID 프리픽스 병합 + api_contract.json 기반 메서드/경로 정규화 매칭으로 프론트-백엔드 크로스 엣지 자동 추론(전부 결정론적 문자열 매칭, LLM 미개입). wiki-builder.md에 pair_config 읽기 순서·통합 서술 지시 복원. (4) `wiki_generator.py`가 템플릿·vis-network 라이브러리를 project_root/agents/lib에서 찾던 버그 수정(스크립트 자신의 디렉터리 기준으로 변경) — 실제 플러그인 설치 환경(템플릿이 대상 프로젝트가 아닌 플러그인 저장소에 있음)에서는 Home.md가 항상 raw 기본값으로 폴백하고 architecture.md/call-graph.html이 아예 생성되지 않던 잠재 회귀였음. (5) wiki-builder.md의 `workflows` 필드가 예시 1개만 보고 전체 스킬을 나열 안 할 위험 있어 "설치된 스킬 전부" 명시. 전부 더미 데이터로 동작 검증 완료 | agents/lib/skills_builder.py, agents/lib/claude_md.template.md, agents/lib/wiki_generator.py, agents/wiki-builder, agents/writer, skills/harness-init | harness-init(LLM 위키)과 generate-wiki(시스템 위키) 양쪽의 토큰 절감을 이어가되, "절감하면 품질 떨어지는 거 아니냐"는 지적에 따라 실제 동작 검증 없이 존재하던 회귀·잠재 버그를 먼저 찾아 고침 |
| 2026-07-14 | 시스템 wiki MSSQL DB 저장 지원 추가 — `agents/lib/wiki_db.py`(pymssql, 프로젝트 루트 `.env`의 MSSQL_HOST/PORT/USER/PASSWORD/DATABASE로 접속, `harness_wiki_pages` 테이블에 페이지 upsert/조회, 폴더↔DB 완전 동기화) + `agents/lib/wiki_db_server.py`(stdlib http.server 기반 로컬 뷰어 — markdown은 이스케이프 후 렌더링, call-graph.html은 그대로 서빙, vis-network 정적 파일은 플러그인 lib에서 직접 서빙, 외부 CDN 의존 없음) + `generate-wiki` Phase 1.5(저장 위치 폴더/DB 선택 질문, `wiki_generator.py --storage folder\|db` 연동) + 신규 스킬 `sync-wiki`(폴더→DB, DB→폴더 양방향 수동 변환) + `agents/lib/requirements.txt`(pymssql) + `.env.example` 추가 + `.gitignore`에 `.env` 추가(실 접속정보 커밋 방지). 실제 MSSQL 서버(사용자 제공 계정, CREATE DATABASE 권한 없어 계정 기본 DB 사용으로 조정)에 연결해 테이블 생성·폴더→DB→폴더 왕복·DB 뷰어 HTTP 응답까지 전부 실제 실행으로 검증(테스트 데이터는 완료 후 삭제, 스키마는 유지) | agents/lib/wiki_db.py, agents/lib/wiki_db_server.py, agents/lib/wiki_generator.py, agents/lib/requirements.txt, skills/generate-wiki, skills/sync-wiki, .env.example, .gitignore, CLAUDE.md | 시스템 wiki를 파일이 아닌 DB에 보관해 여러 사용자가 공유 조회할 수 있게 하고, 폴더/DB 두 형태를 언제든 상호 변환 가능하게 하기 위함 |
| 2026-07-14 | wiki DB 저장의 다중 시스템 구분을 `WIKI_SYSTEM_KEY` 명시 입력 방식으로 강화 — 기존엔 프로젝트 폴더 basename으로만 구분해 서로 다른 시스템의 폴더명이 같으면(예: 둘 다 `backend/`) 데이터가 섞이는 문제 발견. 스키마 변경 없이(`harness_wiki_pages` 그대로, 당시 0행이라 마이그레이션 리스크 없었음 확인) `project_name` 값의 결정 로직만 `--system-key`(1회성 override) > `.env`의 `WIKI_SYSTEM_KEY` > 폴더명(경고 출력) 우선순위로 변경. `resolve_system_key()`/`ensure_system_key_in_env()`(기존 키 있으면 덮어쓰지 않음) 추가, `save_folder_to_db`/`load_db_to_folder`/`list_pages`/`get_page` 전부 `system_key` 파라미터 지원, `--list-systems` CLI(DB에 저장된 전체 시스템 + 페이지 수 + 최근 갱신 시각 조회) 추가. `generate-wiki`·`sync-wiki`는 DB 저장/DB→폴더 시 시스템 키를 묻고 `.env`에 저장(재실행 시 재사용). `wiki_db_server.py`는 `--system-key` + `?key=` 쿼리 파라미터로 시스템 전환, 인덱스 페이지에 "다른 시스템" 목록 표시. 폴더명이 같은 더미 시스템 2개(`SYS-A-BACKEND`, `SYS-B-BACKEND`)를 실제 DB에 저장해 데이터가 섞이지 않고 분리됨을 `--list-systems`·페이지 조회·서버 전환 링크로 각각 실제 실행 검증(검증 후 테스트 행 삭제, 스키마는 유지) | agents/lib/wiki_db.py, agents/lib/wiki_db_server.py, skills/generate-wiki, skills/sync-wiki, CLAUDE.md | 여러 시스템(ITO/SI에서 흔한 backend/frontend 등 동일 폴더명 반복 구조)의 wiki를 하나의 DB에 안전하게 공존시키기 위함 |
| 2026-07-14 | 폴더 모드 wiki의 브라우저 열람 기능이 실제로는 존재하지 않던 문제 발견 및 수정 — 기존 안내문("브라우저로 wiki/index.html 직접 열기")과 달리 `wiki_generator.py`는 `index.html`을 아예 생성하지 않았고(재확인용 grep으로 검증), 설령 있었어도 docsify류 클라이언트 fetch 방식은 `file://`로 열면 브라우저 CORS 정책에 막혀 대부분 동작하지 않았을 것(로컬 서버 필요). 실제로 폴더 모드에서 서버 없이 정상 동작하는 건 데이터가 인라인된 `call-graph.html` 뿐이었고 `Home.md`/`architecture.md`/`workflows.md`는 서식 없는 원본 텍스트로만 보였음. `wiki_db_server.py`의 이스케이프+`<pre>` 렌더 로직을 `agents/lib/wiki_render.py`(신규, 공용 모듈)로 추출해 `wiki_db_server.py`(리팩터, 기존 curl 회귀 테스트로 동일 동작 재확인)와 `wiki_generator.py`(신규: 각 `.md` 페이지 저장 직후 `wiki/_html/<name>.html` 정적 렌더 생성 + `wiki/index.html` 랜딩 페이지 생성) 양쪽에서 공유. `wiki_db.py`의 `load_db_to_folder`(DB→폴더)에도 동일하게 정적 렌더 생성을 추가해 폴더 모드가 어느 경로로 만들어지든(생성 직후/DB에서 복원) 항상 서버 없이 더블클릭으로 열람 가능하게 함. `_iter_wiki_files`는 `_html/`·`index.html`을 실제 콘텐츠가 아닌 보기 전용 파일로 보고 DB 동기화 대상에서 제외(안 그러면 Home.md/Home.html이 DB에 중복 저장됨). 실제 더미 프로젝트로 폴더 생성→파일 트리 확인→폴더→DB(4페이지, `_html`/`index.html` 제외 확인)→DB→폴더 복원(정적 렌더 재생성 확인)까지 전부 실행 검증(테스트 데이터 삭제, 스키마 유지) | agents/lib/wiki_render.py, agents/lib/wiki_db_server.py, agents/lib/wiki_generator.py, agents/lib/wiki_db.py, skills/generate-wiki, skills/sync-wiki, CLAUDE.md | 사용자가 "DB/폴더 두 경우 모두 브라우저로 볼 수 있는 것까지 적용됐는지" 재확인 요청 — 실제로 다시 읽어보니 폴더 모드 쪽 안내 문구가 실제 코드와 어긋나 있었음(과거 세션에 실제 실행 검증 없이 넘어간 부분) |
| 2026-07-15 | 폴더 모드 wiki의 `index.html`을 정적 랜딩 페이지에서 Docsify 4 기반으로 교체 — `render_index()`(`agents/lib/wiki_render.py`)가 Docsify 부트스트랩 HTML(외부 CDN: docsify·docsify-themeable·pretendard·prism·검색/페이지네이션/복사 플러그인)을 생성하도록 변경, `wiki_generator.py`에 `generate_sidebar_md()`/`generate_navbar_md()`/`generate_serve_bat()` 추가로 `wiki/_sidebar.md`·`wiki/_navbar.md`·`wiki/serve.bat`(`python -m http.server 3501`)을 함께 생성. 신규 `agents/lib/docsify_convert.py`(레거시 wiki 폴더를 Docsify로 수동 재변환하는 독립 CLI, wiki_generator.py 미실행). 이 변경은 다른 시스템에서 harness-init을 실행하며 플러그인 캐시(`~/.claude/plugins/cache/ax-std-harness/ax-std-harness/0.4.0`)에 직접 적용됐던 수정을 diff로 발견해 본 저장소(원본)에 역이식한 것 — `wiki_render.py` 헤더 주석(`render_markdown_page`는 CDN-프리·`file://` 호환 유지, `render_index`만 예외)과 `generate-wiki`/`sync-wiki` 스킬의 "더블클릭 열람, 서버·CDN 불필요" 안내 문구를 Docsify 요건(serve.bat 실행 필요, 인터넷 CDN 필요)에 맞게 갱신, `.gitignore`에 `__pycache__/` 추가. `wiki/_html/*.html` 개별 페이지·`wiki/call-graph.html`은 기존대로 서버 없이 열람 가능 상태 유지 | agents/lib/wiki_render.py, agents/lib/wiki_generator.py, agents/lib/docsify_convert.py, skills/generate-wiki, skills/sync-wiki, .gitignore, CLAUDE.md | 다른 환경(플러그인 캐시 직접 수정)에서 먼저 이뤄진 wiki UI 개선(네비게이션·검색·문법 강조 있는 Docsify)을 원본 저장소에 반영해 단일 소스로 유지하기 위함 |
| 2026-07-15 | DB 모드 wiki 뷰어를 Docsify와 맞물리도록 수정 — `agents/lib/wiki_db_server.py`의 markdown 페이지 응답을 `text/html`(서버 사전 렌더) 대신 `text/plain` raw markdown으로 변경(Docsify JS가 클라이언트에서 fetch·렌더). 이 변경만 플러그인 캐시에서 이식했을 경우 `_render_index()`가 여전히 구 시그니처(`heading`/`entries`/`extra_html`)로 `wiki_render.render_index()`를 호출하고 있어(2026-07-15 앞선 Docsify 이식에서 이미 그 인자들이 무시되도록 바뀜) DB 모드에서 페이지 목록·"다른 시스템" 전환 UI가 통째로 사라지는 상태였음 — `_render_index()`를 title만 넘기도록 단순화하고, `/_sidebar.md`·`/_navbar.md` 라우트를 신규 추가해 `docsify_convert.build_sidebar/build_navbar`로 DB에 저장된 페이지 목록 기반 사이드바·네비바를 동적 생성, "다른 시스템" 섹션은 사이드바 하단에 `:ignore` 링크로 추가해 복구. 미사용 상태였던 `_render_markdown_page()`는 삭제 | agents/lib/wiki_db_server.py, CLAUDE.md | 사용자가 다른 시스템의 플러그인 캐시에서 진행한 추가 수정을 재요청해 diff로 발견 — 이식만 하면 DB 뷰어가 폴더 모드보다 기능이 퇴화한 상태로 남을 것이 확인되어 함께 수정 |
| 2026-07-15 | `wiki-builder` 에이전트(LLM) 제거 + zero-LLM 크로스 리포 markdown 통합 — 사용자가 "wiki가 `_workspace`/`.claude` 산출물을 그대로 보여주면 되는데 별도 폴더에 LLM으로 다시 요약·재작성하는 건 토큰 낭비 아니냐"고 지적. 실제로 `wiki/` 8개 페이지 중 call-graph.html/index.html/_sidebar.md/_navbar.md/serve.bat/_html 렌더 사본을 뺀 나머지(Home/architecture/workflows/api-endpoints/database/patterns/external-systems/issues)는 이미 존재하는 `CLAUDE.md`·`_workspace/01_analyzer_report.md`·`.claude/skills·patterns/*.md`·`_workspace/index/*.json`을 `wiki-builder`(sonnet, 요청당 약 25~55K 토큰)가 다시 읽어 `_workspace/07_wiki_summary.json`으로 재서술한 뒤 템플릿 치환한 것에 불과했음(확인 후 삭제). 신규 `agents/lib/wiki_content.py`(LLM 미사용 순수 함수 모음)가 이를 대체 — Home←CLAUDE.md 그대로, architecture←01_analyzer_report.md 그대로, workflows/patterns←.claude/skills·patterns/*.md를 재작성 없이 목차+연결, api-endpoints/database/external-systems←api_contract.json/schema.json+sql_usage.json/external_io.json을 Python으로 표 변환(call-graph.html이 이미 하던 것과 동일 패턴), issues←03_validator_report.md+04_qa_report.md+dead_code.json 연결. `agents/wiki-builder.md`·`agents/lib/Home.template.md`·`agents/lib/architecture.template.md` 삭제, `wiki_generator.py`의 `--summary` 인자 제거(`--root`만으로 직접 읽음), `api_exists` 판정을 잘못된 소스(symbols.json)에서 올바른 소스(api_contract.json)로 교정, 자체 구현이던 사이드바/네비바 생성을 `docsify_convert.build_sidebar/build_navbar`(+ 신규 `serve_bat_content()`) 재사용으로 정리해 두 파일 간 중복 제거. **추가로** 페어 연동(`pair_config.md`, 백엔드·프론트엔드 별도 저장소) 시 지금까지 call-graph.html만 파트너 그래프를 병합하고 나머지 markdown 페이지는 자기 저장소 것만 보여주던 것을, architecture/api-endpoints/database/external-systems 4개 페이지도 파트너의 동일 산출물을 같은 zero-LLM 방식으로 읽어 "## 파트너 ({partner_type})" 섹션으로 병합하도록 확장(어느 쪽에서 `generate-wiki`를 실행해도 통합됨, 기존 call-graph 병합과 동일 원칙) — 사람이 wiki 하나로 백엔드+프론트엔드 전체 시스템을 파악하고, 바이브 코딩 시 한쪽 요청만 와도 LLM이 양쪽 분석 내용을 참고할 수 있게 하기 위함. workflows/patterns/issues는 저장소별 실행 환경·품질 이슈라 병합 대상에서 제외(설계 결정, 근거는 계획 문서 참조). `skills/cross-repo-modify`·`skills/cross-repo-scaffold`에는 통합 architecture.md를 오리엔테이션 참고용으로만 쓰고 실제 영향 분석·드리프트 검증은 기존대로 `impact-analyzer`/`api-bridge` 라이브 재분석으로 수행한다는 원칙을 한 줄 추가(wiki는 스냅샷이라 최신성 미보장) | agents/lib/wiki_content.py(신규), agents/lib/wiki_generator.py, agents/lib/docsify_convert.py, agents/wiki-builder.md(삭제), agents/lib/Home.template.md(삭제), agents/lib/architecture.template.md(삭제), skills/generate-wiki/SKILL.md, skills/harness-init/SKILL.md, skills/cross-repo-modify/SKILL.md, skills/cross-repo-scaffold/SKILL.md, CLAUDE.md | wiki-builder의 LLM 재서술 비용이 대부분 이미 있는 문서의 중복 표현이었음을 확인했고, 크로스 리포 구조에서 사람·LLM 모두 시스템 전체를 한 곳에서 파악할 수 있어야 바이브 코딩 요청을 정확히 처리할 수 있기 때문 |
| 2026-07-15 | harness-init 파이프라인(analyzer/pattern-extractor/writer/validator/qa) 중 "이미 구조화된 JSON을 LLM이 다시 프로즈로 옮겨 적는" 부분만 골라 zero-LLM 기계화 (판단이 필요한 부분은 템플릿 고정 없이 그대로 LLM 유지 — 대형/소형 시스템마다 분석 내용이 달라지는 부분을 고정하면 누락 위험이 생기기 때문). (1) `agents/lib/analyzer_index_summary.py`(신규) — analyzer 리포트 Section B(의존성그래프·트랜잭션·외부통신·환경분기·데드코드)/D(DB스키마)를 `_workspace/index/*.json`에서 카운트·표로 생성, analyzer.md는 Section A와 대응 인덱스가 없는 "비동기/스케줄/이벤트"·"인증/인가 경로"·"탐지 신뢰도"·"보완 권장"만 직접 작성. (2) `agents/lib/pattern_tally.py`(신규) — `05_patterns_extracted.md`의 집계 표(샘플수·신뢰도·안티패턴 발견 수)를 각 `.claude/patterns/*.md`에서 정규식으로 취합, pattern-extractor는 패턴 본문과 "## 권고"만 직접 작성. (3) `agents/lib/skills_builder.py` 확장 — patterns/ 스켈레톤(고정 헤더, client_pattern.md는 "LegacyStaticJS" 탐지 시 자동 추가, 이미 채워진 파일은 안 덮어씀) + `02_writer_files.md`(고정 서식) 조립 추가. writer는 이제 이 두 산출물 대신 `_workspace/writer_decisions.json`(조건부 스킬 생성 여부+사유, pattern_files 목록, 탐지 스택, 적용 결정 사유)만 출력 — `decision_for()`도 `02_writer_files.md` 정규식 파싱에서 JSON 직접 로드로 계약 변경(writer.md와 한 번에 반영). (4) `agents/lib/validator_checks.py`(신규) — validator 10개 체크 중 8개(1,2,3,4,6,7,8,9: 파일존재·트리거품질·경로교차·보안regex·인덱스무결성·harness-init.md보존·변경이력)를 기계 실행해 `_workspace/validator_mechanical.json`(기존 점수 산식 그대로, `report_fragments`에 리포트 섹션 텍스트 포함) 생성, validator(LLM)는 체크 5(레이어 커버리지)와 체크 10 중 스크립트가 "판정 불가"로 남긴 항목만 담당. (5) `agents/lib/qa_boundary6.py`(신규) — qa Boundary 6(워크플로우 스킬 ↔ 인덱스 의존성)을 기계 실행, Boundary 1~5·7(실제 소스 읽고 의미 비교 필요)은 그대로 qa(LLM) 유지. `skills/harness-init/SKILL.md`의 Phase 2-4/2-5에 두 스크립트 실행 단계를 validator/qa Agent 호출 직전에 추가(실패 시 WARN 후 기존 방식 폴백). 더미 backend 프로젝트로 5개 스크립트를 실제 파이프라인 순서(analyzer_index_summary→skills_builder→pattern_tally→validator_checks→qa_boundary6)대로 전부 실행 검증 — 이 과정에서 check 3(스킬 트리거 품질)이 정적 배포 스킬 5종·harness-init.md(둘 다 프로젝트별로 새로 판단할 트리거가 없는 고정 파일)까지 잘못 채점해 매 프로젝트마다 불필요한 FAIL 4건이 나오는 실제 버그를 발견해 수정(`STATIC_OR_PREEXISTING_SKILLS` 제외 목록 추가) | agents/lib/analyzer_index_summary.py(신규), agents/lib/pattern_tally.py(신규), agents/lib/validator_checks.py(신규), agents/lib/qa_boundary6.py(신규), agents/lib/skills_builder.py, agents/analyzer.md, agents/pattern-extractor.md, agents/writer.md, agents/validator.md, agents/qa.md, skills/harness-init/SKILL.md, CLAUDE.md | 사용자가 "토큰 절감이 목적이 아니라, 불필요한 재서술 작업만 프로그램화하고 실제 판단이 필요한 부분은 절대 템플릿으로 고정하지 말라"고 명시 — wiki-builder 제거와 동일한 원칙을 파이프라인 나머지 단계에도 적용해달라는 요청 |
| 2026-07-15 | 전체 agents/skills 재검토(fork 2개 병렬 감사) 결과 2건 수정. (1) opus/sonnet 불일치 회귀 4건 수정 — `skills/review-sql`(→sql-reviewer), `skills/safe-modify`(→change-safety), `skills/scaffold-feature`(→test-generator), `skills/trace-logic`(→logic-tracer)의 `Agent()` 호출이 대상 에이전트 frontmatter(`model: sonnet`, 2026-06-03 결정)와 다르게 `model="opus"`로 하드코딩되어 있어 매 호출 opus로 실행되던 것을 `model="sonnet"`으로 수정(analyze-impact/plan-migration은 impact-analyzer/migration-planner가 의도적으로 opus 유지 대상이라 그대로 둠, 확인 완료). (2) 스킬 4개(`review-sql`/`safe-modify`/`scaffold-feature`/`harness-init`) 끝부분 "시나리오 예시" 섹션 삭제 — 앞선 Phase별 지시를 이야기 형식으로 재진술만 할 뿐 새 판단 로직이 없어 매 스킬 호출 시 순수 재서술 토큰만 소비하던 부분 제거 | skills/review-sql/SKILL.md, skills/safe-modify/SKILL.md, skills/scaffold-feature/SKILL.md, skills/trace-logic/SKILL.md, skills/harness-init/SKILL.md, CLAUDE.md | 사용자가 "harness 생성하는 모든 agent/skill 전반 검증해서 성능 유지하며 토큰 절약 방안 검토" 요청 — fork 2개로 agents/*.md·skills/*/SKILL.md 각각 감사해 opus 하드코딩 회귀와 순수 재서술 섹션을 발견 |
| 2026-07-16 | Karpathy 가이드라인(CLAUDE (1).md) 10개 규칙을 CLAUDE.md에 "보편 에이전트 행동 원칙" 섹션으로 통합 — Rule 1(코딩 전 사고)·Rule 2(단순성)·Rule 3(외과적 변경)·Rule 5(한국어 콜론 금지)·Rule 6(파일 헤더)·Rule 9(의미 커밋)·Rule 10(에러 읽기)를 직접 명시. Rule 4/7/8은 이미 `_workspace/` 파이프라인으로 구현된 사실을 참조 형태로 명기. `skills/safe-modify/SKILL.md`에 "변경 범위 원칙(Rule: 외과적 변경)" 섹션 추가(모든 Phase에 최우선 적용). `agents/lib/*.py` 8개 파일(analyzer_index_summary·pattern_tally·qa_boundary6·skills_builder·validator_checks·wiki_db·wiki_db_server·wiki_generator)에 한국어 헤더 주석 소급 적용 | CLAUDE.md, skills/safe-modify/SKILL.md, agents/lib/analyzer_index_summary.py, agents/lib/pattern_tally.py, agents/lib/qa_boundary6.py, agents/lib/skills_builder.py, agents/lib/validator_checks.py, agents/lib/wiki_db.py, agents/lib/wiki_db_server.py, agents/lib/wiki_generator.py | 사용자가 CLAUDE (1).md(Karpathy 가이드라인)의 내용이 잘 적용될 수 있도록 검토 및 적용 요청 |
| 2026-07-22 | 플러그인 버전 0.4.0 → 0.5.0 (`.claude-plugin/plugin.json`). 이번 세션의 harness-init Phase -1/-2 병합, 진행상황 한글표시 이식, QA·wiki 온디맨드화, 후속 드리프트 수정 4건을 반영한 버전 표시 | .claude-plugin/plugin.json, CLAUDE.md | 로컬 디렉터리 마켓플레이스로 설치돼 있어 파일 자체가 곧 배포본이므로, 버전 번호는 실제 배포 산출물이 아니라 변경 이력 추적용 |
| 2026-07-22 | 사용자 요청으로 harness-init 전체 프로세스(직전 3건 변경분)를 점검해 발견한 문서·로직 드리프트 7건 수정. (1) **기능 버그**: `skills/pair-init/SKILL.md`의 "파트너 하네스 자동 생성" subagent 호출이 옛 변수명 `repo_structure`·존재하지 않는 "Phase -2"를 참조하고 있었고, 새로 추가된 Phase 0 Step 2.5(Tier 확인 질문)·Phase 3.6(QA·wiki 선택 메뉴)이 응답할 사용자가 없는 무인 subagent 실행에서 그대로 질문을 시도해 멈출 수 있는 상태였음 — `init_layout: 'paired-roots'`로 교정하고, 두 질문 모두 명시적으로 "묻지 않고 기본값(Full/지금 안 함)으로 진행" 지시를 추가. (2) `skills/harness-init/SKILL.md` 자체에 남아있던 stale 참조 정리 — 상단 "필수 파이프라인" 소개에서 qa 제거(온디맨드 항목으로 별도 명시), Step 3 실행모드 표의 "qa" 포함 문구 수정, Step 2.5 Tier별 실행구성 표에서 Lite/Standard만 "QA 스킵"으로 표시돼 있어 Full은 자동 실행되는 것처럼 보이던 오독 여지를 제거(QA는 세 Tier 모두 스킵, 별도 각주로 명시), Phase 3.6에 "Phase 3.5·3.6 질문은 순서대로 제시" 안내문 복원(재작성 시 누락됨). (3) `agents/spec-clarifier.md`·`skills/spec-gate/SKILL.md`의 description이 "harness-init Phase -1에서 자동 호출"이라고 명시하고 있었으나 실제로는 지난 변경에서 harness-init이 spec-clarifier 호출을 완전히 제거했음 — 두 파일 모두 "harness-init은 자동 호출하지 않음, 필요시 별도 호출"로 정정. (4) `README.md`·`docs/user-guide.md`·`docs/harness-description.md` 3개 문서에 남아있던 옛 설계(스펙 인터뷰 질문 흐름, 복잡도 점수 기반 자동 Tier 판정 mermaid 다이어그램·표, `00_spec_report.md`를 harness-init 산출물로 표기, "경계면 QA"를 Full Tier 전용으로 표기)를 실제 동작(구성확인 4택 + Tier 1회 확인질문, QA/wiki 전부 온디맨드, `00_init_scope.md`)에 맞게 재작성 | skills/pair-init/SKILL.md, skills/harness-init/SKILL.md, agents/spec-clarifier.md, skills/spec-gate/SKILL.md, README.md, docs/user-guide.md, docs/harness-description.md, CLAUDE.md | 사용자가 "수정된 전체 프로세스를 점검해서 오류 있는지, 정상 작동하는지 확인해달라"고 요청 — 직전 세 차례의 harness-init 수정(Phase -1/-2 병합, 진행상황 한글표시, QA·wiki 온디맨드화)이 SKILL.md 자체는 일관됐지만 연동 스킬(pair-init)과 사용자 문서(README/user-guide/harness-description) 쪽 반영이 누락돼 실제 동작과 문서·일부 로직이 어긋난 상태였음 |
| 2026-07-22 | AX-Harness-INTG-main처럼 QA(경계면 교차 비교)와 wiki 생성을 온디맨드 선택 작업으로 통합해 토큰 절감. 기존엔 QA가 Full Tier에서만 Phase 2 파이프라인 안에서 자동 실행됐음(Lite/Standard는 스킵, Full은 무조건 실행) — 이를 Tier 무관하게 항상 스킵하도록 바꾸고, Phase 1 Full 작업그래프에서 `T-Q` 제거(`T-E`는 `T-Q` 대신 `T-V`에 blockedBy), Phase 2의 `### 2-5. qa 호출` 섹션 삭제(agent 호출 스펙은 보존해 Phase 3.6으로 이동), `### 2-6. harness-evaluator`를 `### 2-5.`로 재번호. 기존 Phase 3.6(wiki 단독 질문)을 "Phase 3.6: 선택 작업 안내 (QA·Wiki)"로 교체 — INTG의 번호 메뉴 방식(복수 선택 가능, 무응답 시 아무것도 실행 안 함)을 그대로 적용해 QA와 wiki를 한 번에 묻고, 선택한 것만 실행. validator 신뢰도 < 50이면 QA 옵션에 "구조 검증 실패로 결과 없이 종료됨" 표시. 하위 참조 정리 — Phase 3 보고 템플릿의 "경계면 교차 비교(qa)" 섹션을 조건부로, 항상 읽던 `04_qa_report.md` 참조를 "(있으면)"으로, 에러 핸들링 표의 "qa 스킵" 문구를 "QA 옵션 실행 시 결과 없이 종료"로, Phase 4 fix_targets task-id 매핑에서 이제 안 쓰는 `qa→T-Q`를 제거(fix_target.agent는 애초에 analyzer/writer만 반환됨을 harness-evaluator.md에서 재확인). `README.md`의 에이전트 표·`agents/qa.md` description·`docs/workflows.md`의 안내 문구도 "Full만"→"온디맨드"로 갱신 | skills/harness-init/SKILL.md, README.md, agents/qa.md, docs/workflows.md, CLAUDE.md | 사용자가 AX-Harness-INTG-main의 QA·wiki 질의응답 방식(자동 실행 대신 사용자에게 묻고 선택한 것만 실행)을 이식해달라고 명시적으로 요청, 목적은 토큰 절감 — pattern-extractor·harness-evaluator 자동 루프는 이번 요청 범위 밖이라 건드리지 않음 |
| 2026-07-22 | AX-Harness-INTG-main의 진행상황 한글 표시 관례를 harness-init에 이식. 모든 `Agent()` 호출이 `subagent_type="general-purpose"`라 호스트 진행 화면에 `general-purpose`만 노출되던 문제를 보완 — `description` 필드를 `[task-id] · [실제 에이전트 이름] · 한글 목적` 형식(예: `T-A · analyzer · 프로젝트 구조·의존성·레거시 로직 분석`)으로 전부 교체(2-1 analyzer, 2-2 writer, 2-2.5 ito-guide, 2-3 pattern-extractor, 2-4 validator, 2-5 qa, 2-6 harness-evaluator, Phase 4 재생성·재평가 6곳). Phase 1에 표시 원칙 문단 추가 — `TaskCreate` 제목도 같은 형식 그대로 사용, `TaskCreate` 없는 호스트는 `_workspace/00_pipeline_status.md` 체크리스트로 폴백해도 동일 제목 유지, 보완·재검증 작업은 `T-A-RETRY`/`T-W-RETRY`/`T-V-RECHECK`/`T-E-RECHECK`처럼 원 단계 ID를 보존 | skills/harness-init/SKILL.md, CLAUDE.md | 사용자가 AX-Harness-INTG-main처럼 harness-init 진행사항이 한글로 표시돼야 한다고 지적 — 원인은 표시 문구가 아니라 모든 Agent 호출이 general-purpose로 위임되어 있어 호스트 진행 UI가 실제 단계를 구분해 보여줄 수 없었던 것이었음 |
| 2026-07-22 | 별도 프로젝트(AX-Harness-INTG-main)와 harness-init 단계별 비교 후 초기 확인 구간 2건 교체. (1) 기존 Phase -2(저장소 구조 3택: mono/multi/single) + Phase -1(spec-clarifier Ouroboros 인터뷰)을 단일 "Phase -1: 프로젝트 구성 확인"(4택: single-root/monorepo/paired-roots/selected-paths, 4번 "특정 폴더·모듈만" 신규 추가)으로 교체. `repo_structure` 변수를 `init_layout`으로 개명(mono→monorepo, multi→paired-roots, single→single-root), 확인 결과를 `_workspace/00_init_scope.md`에 영구 기록해 재실행 시 재질문 방지. spec-clarifier는 harness-init 호출부에서 제거(에이전트 파일·`spec-gate` 스킬은 그대로 유지, 독립 호출은 계속 가능). (2) Phase 0 Step 2.5를 "복잡도 점수 계산→Tier 자동결정" 방식에서 "기본 Full 고정 + override 키워드 없으면 Standard 다운그레이드 1회 확인질문"으로 교체 — 소스파일수/DB-ORM/레거시스택/멀티모듈/외부시스템 점수 계산 로직 전체 삭제(Tier 결정에 더 이상 안 쓰여 로직 자체 제거, 참고용으로도 남기지 않음). 하위 참조 정리 — analyzer 프롬프트의 `spec_context` 참조, harness-evaluator 입력의 `00_spec_report.md` 참조, 에러 핸들링 표의 "spec-clarifier 실패" 행, Phase 3 보고의 "복잡도 점수: N점" 표기, Phase 3.5 분기 표의 `repo_structure` 조건을 전부 `init_layout` 체계로 갱신 | skills/harness-init/SKILL.md, CLAUDE.md | 사용자가 두 프로젝트의 harness-init을 단계별로 비교해 장점을 흡수해달라고 요청 — Ouroboros 모호성 게이트 소실과 "질문 없는 자동 Tier 결정"이 "매번 1회 확인질문"으로 바뀌는 트레이드오프 2건을 먼저 제시해 사용자 승인 받은 뒤 진행 |
| 2026-07-23 | 전체 harness-init 파이프라인 감사(에이전트 3개 병렬 — 계약 정합성·lib 스크립트 계약·산출물 정확성 보증) 후 발견 결함 수정 5개 커밋. (1) **설치 환경 경로 결함**: 모든 `python agents/lib/*.py` 호출이 cwd 상대경로라 플러그인 설치 환경(cwd=대상 프로젝트)에서 스크립트를 못 찾던 문제 — skill/agent 7개 파일을 `$env:CLAUDE_PLUGIN_ROOT` 기준 절대경로로 교체, `--out`/`--summary` cwd 상대 인자 제거(파트너 자동 생성 흐름에서 엉뚱한 프로젝트에 읽기/쓰기 되던 문제 동시 해소), skills_builder `--summary` optional화. (2) **Lite Tier 폐지** (사용자 지시) — 인덱스 없는 하네스는 후속 스킬이 동작 안 해 실효 없고 validator check7/evaluator가 인덱스 부재를 상시 감점하는 모순 존재. "빠르게" 키워드는 Standard로 매핑, analyzer lite 모드 삭제, Standard 필수 Phase에 C(인덱스) 누락 교정. (3) **evaluator 옛 설계 채점 제거** — 정적 배포 스킬 5종을 여전히 writer 커스터마이즈 대상으로 채점하던 상시 감점 제거(배포 여부만 확인), fix_targets 복수 에이전트 행("analyzer+writer")을 단일 행 2개로 분리, Phase 4 재실행 model을 에이전트별 규칙으로 명시(writer 전 Tier sonnet). (4) **BOM 결함**: PowerShell 5.1산 JSON(BOM)에서 json.load 실패(더미 실행 재현) — 파이프라인 스크립트 5종 읽기를 utf-8-sig로 전환 | skills/harness-init, skills/generate-wiki, skills/sync-wiki, agents/analyzer.md, agents/qa.md, agents/pattern-extractor.md, agents/harness-evaluator.md, agents/lib/*.py, README, docs/ | 사용자가 "harness-init 전체 단계 점검 + LLM 산출물 정확성 점검" 요청 후 "순서대로 진행, Lite tier는 disabled 처리(기본 Full)" 지시 |
| 2026-07-23 | ito-guide.md 기계화 + 인덱스 내용 정확성 게이트 신설. (1) 고아 WIP였던 `ito_guide` 템플릿을 실제 구현으로 완성 — `skills_builder.deploy_ito_guide()`가 배포된 스킬 frontmatter(용도·트리거 regex 추출)·claude_md_fields(주의사항)·writer_decisions(스택·패턴)·pair_config(파트너 블록)만으로 조립, 실전 시나리오는 배포 스킬 조합 규칙 기반. harness-init 2-2.5의 sonnet Agent 호출(매회 ~5K 토큰) 삭제. (2) **정확성 게이트**: 기존 검증이 전부 구조(존재·파싱·카운트)만 보고 내용 검증은 온디맨드 QA에만 있어 기본 경로에 정확성 게이트가 0개였음 — validator_checks.py에 check 7b(call_graph 엣지 20개·sql_usage 10개 결정론적 샘플을 실제 소스와 대조, 일치율 <80%면 -15) 추가, analyzer.md에 인덱스 `_meta` 필수 필드(git_commit/sampled/files_scanned/files_total)·dead_code 진입점 화이트리스트(@Controller/@Scheduled/main 등)+샘플링 파생 confidence=low 강제·incremental stale 엣지 무효화 규칙 명시, analyzer_index_summary.py가 분석 커버리지(N/M 파일 %)를 기계 출력. (3) agents/lib 템플릿 7종을 `*.md.template`로 rename — `agents/` 재귀 스캔으로 가짜 에이전트 8개가 등록되던 문제 해소. (4) 잔여 드리프트 정리 — validator.md `client_side_pattern.md` 오탈자(매 실행 허위 WARN), QA 임계 40/50 → 50 통일, qa.md 존재하지 않는 `full` 모드 → `init`, pattern-extractor 스켈레톤 주체 stale 표기, 2-1 표에 incremental 행 추가. 전부 더미 프로젝트 실행으로 검증(스팟체크 불일치 검출·커버리지 라인·ito-guide 플레이스홀더 잔존 0 확인). 플러그인 버전 0.5.0 → 0.6.0 | agents/lib/skills_builder.py, agents/lib/validator_checks.py, agents/lib/analyzer_index_summary.py, agents/lib/*.md.template, agents/analyzer.md, agents/validator.md, agents/qa.md, agents/pattern-extractor.md, skills/harness-init, docs/index-spec.md, .claude-plugin/plugin.json | LLM이 만든 인덱스(call_graph 등)가 정확한지 기본 파이프라인이 전혀 검증하지 않는다는 감사 결론에 대한 저비용 기계 게이트 도입 + 재서술 기계화 원칙(wiki-builder 제거와 동일)을 ito-guide에도 적용 |
| 2026-07-23 | call-graph.html의 우측 정보 패널을 AX-Harness-INTG-main의 `build-wiki.mjs` graphHtml() 디자인에 맞춰 교체. 기존 2x2 통계 박스(노드/엣지 + 상위 타입 2개) → 단일 히어로 통계(큰 숫자 + "노드 · N 엣지" + "허브 X · 데드코드 후보 Y" 한 줄), 범례에서 타입별 "(N개)" 카운트 제거하고 2열 그리드로 재배치 + "◎ 허브(in-degree ≥ N)"·"☠ 데드 코드 후보" 안내 문구 추가, "노드 상세" 라벨을 "선택 노드"·빈 상태 문구를 "노드를 클릭하세요."로 교체. 툴바에 물리엔진 ON/OFF 토글 버튼(기존엔 항상 ON 고정, 토글 UI 없었음) + "찾기"(검색어로 노드 포커스)·"강조 초기화" 버튼 추가, 더블클릭 시 연결 노드만 강조하고 나머지는 opacity 0.15로 흐리게 하는 방식으로 변경(기존 vis-network 기본 selectNodes만 사용해 시각적 강조가 약했음). `wiki_generator.py`의 `{{EXTRA_STATS}}` 플레이스홀더를 `{{STAT_SUMMARY}}`로 교체하고 hub_count/dead_count 계산 로직 추가. 데이터 파이프라인(Python 쪽 zero-LLM 생성, 노드 타입 7종 COLORS/type_mapping)은 그대로 유지 — INTG는 별도 Node.js 기반 통합 wiki 시스템이라 그 코드 자체를 이식한 게 아니라 이 프로젝트의 사이드바 UI/문구만 동일하게 맞춘 것. 더미 프로젝트(노드 7·엣지 6·데드코드 1)로 실제 생성 실행 후 플레이스홀더 잔존 여부·통계/범례 출력값·JS 문법(node --check)까지 검증 완료 | agents/lib/call-graph.template.html, agents/lib/wiki_generator.py, CLAUDE.md | 사용자가 AX-Harness-INTG-main 콜그래프 화면 스크린샷을 제시하며 이 프로젝트의 콜그래프도 그렇게 나오길 요청 — 범위 확인 결과 사이드바 통계·범례 스타일 + 물리엔진 토글 + 툴바 전반 모두 반영하기로 확정 |
| 2026-07-23 | harness-init + wiki 생성 전체 절차 재점검(에이전트 2개 병렬 — 파이프라인 계약 감사 + wiki 생성 실제 POC) 후 발견 결함 다수 수정. **[파이프라인 감사]** (1) `skills/cross-repo-modify/SKILL.md` Phase 6 "양쪽 change-safety" 호출 2곳이 `model="opus"`로 잔존(2026-07-15 opus 하드코딩 회귀 4건 수정 시 당시 신규 스킬이라 감사 대상 누락) → `model="sonnet"` 교정. (2) `validator_checks.py` check4(경로 교차검증)가 cross-repo 스킬이 예시로 인용하는 파트너 저장소 경로를 "없는 경로"로 오탐 FAIL하던 것을 `pair_config.md`의 partner_root 기준으로도 존재 확인하도록 수정. (3) check7b 스팟체크의 `_simple_name()`이 `sql:PKG_X`/`page:Menu.vue`류 type-prefix 노드 id의 접두사를 벗기지 않아 실제 소스에 없는 문자열로 찾아 오탐 FAIL하던 버그 수정(prefix 정규식 추가). (4) check8(harness-init.md 보존 확인)이 애초에 `skills_builder.py`가 해당 파일을 프로젝트에 배포한 적이 없어(메타/툴링 스킬, writer 산출물 아님) 상시 FAIL 상태였던 모순 발견 — "존재하면 보존 확인, 없으면 정상(플러그인이 전역 제공)"으로 완화, `STATIC_OR_PREEXISTING_SKILLS`(check3)에서도 제외해 남은 사본은 오히려 트리거 품질 검사 대상이 되도록(정리 유도). `wiki_content.py`/`docsify_convert.py`의 workflows 목록·사이드바에서도 harness-init.md를 프로젝트 개발 워크플로우가 아닌 메타 스킬로 분리("AI 도구" 섹션), 워크플로우 목록 자체에서 제외. `skills/harness-init/SKILL.md` 백업 안내에서 "harness-init.md 제외" 예외 문구 제거(더 이상 배포 대상이 아니므로 예외 자체가 무의미). **[wiki POC]** 더미 프로젝트로 `wiki_generator.py --storage folder` 실제 실행 검증 — 15개 산출물(Home.md~offline.html, call-graph.html, _html/*) 전부 정상 생성, 플레이스홀더 잔존 0건, DB 모드는 `.env` 없을 때 graceful 실패 확인. 이 과정에서 `wiki_db.py`의 `load_db_to_folder`(DB→폴더 복원)가 2026-07-15 `wiki_render.render_index()`의 Docsify 전환 이후에도 옛 시그니처(`heading`/`entries`)로 호출 중이었고, `_sidebar.md`/`_navbar.md`/`serve.bat`/`offline.html`을 아예 생성하지 않아 DB 복원 시 폴더 모드와 달리 Docsify 네비게이션 없는 반쪽짜리 wiki가 나오던 버그 발견 — `docsify_convert.build_sidebar/build_navbar/serve_bat_content` + `wiki_render.render_static_index`를 재사용해 폴더 생성 경로와 동일한 산출물이 나오도록 수정 | skills/cross-repo-modify/SKILL.md, agents/lib/validator_checks.py, agents/lib/wiki_content.py, agents/lib/docsify_convert.py, agents/lib/wiki_generator.py, agents/lib/wiki_db.py, skills/harness-init/SKILL.md, CLAUDE.md | 사용자가 2026-07-22~23 harness-init 대규모 변경(Phase -1/-2 병합, Tier 로직 교체, QA/wiki 온디맨드화, 진행상황 한글표시, 절대경로 전환, Lite 폐지, ito-guide 기계화, check 7b 추가)이 wiki 생성까지 포함해 전체 절차에 일관 반영됐는지 점검·POC·수정 요청 |
| 2026-07-23 | 플러그인 버전 0.6.0 → 0.6.1 (`.claude-plugin/plugin.json`). 위 재점검 세션의 버그 수정 6건(cross-repo-modify opus 잔존, check4 partner_root 오탐, check7b 노드 id 접두사 오탐, check8 harness-init.md 상시 FAIL, wiki_db.py DB 복원 Docsify 미생성 등)을 반영한 버전 표시 | .claude-plugin/plugin.json, CLAUDE.md | 사용자가 플러그인 업데이트 요청 — 로컬 디렉터리 마켓플레이스 설치라 버전 번호는 배포 산출물이 아니라 변경 이력 추적용(2026-07-22 결정 재확인) |
| 2026-07-24 | 사용자가 harness-init 보안 분석·wiki에 OWASP Top 10 매핑이 있는지 질문 → 점검 결과 전무함을 확인(인증/인가 경로 트레이스와 harness 문서 내 시크릿 스캔만 존재, 실제 소스의 injection/XSS/SSRF 등 취약점 카테고리 매핑 없음) 후 추가 요청받아 신설. `agents/analyzer.md` Step 14.5(신규) — OWASP Top 10 (2021) 10개 카테고리별 탐지 방법 명시(A01 인가 트레이스 재사용, A03 SQL 문자열 결합/커맨드 인젝션, A06 의존성 버전만 추출하고 CVE 대조는 "확인필요"로 남김 등), 증거 없는 카테고리는 `미탐지`로 남기고 "취약점 없음"과 구분하도록 강제. 산출물 `_workspace/index/owasp_top10.json`(신규 인덱스, `docs/index-spec.md`에 스키마 문서화) — 리포트 재진술은 기존 zero-LLM 원칙에 맞춰 analyzer가 직접 쓰지 않고 `agents/lib/analyzer_index_summary.py`의 `_section_owasp()`(신규)가 카테고리별 상태·건수를 표로 생성해 Section B에 편입(2026-07-15 하이브리드 빌드 원칙과 동일). `agents/lib/wiki_content.py`의 `build_issues()`에 `owasp_json` 파라미터 추가 + `_owasp_table()`(신규)로 상태 아이콘(🔴발견/🟡확인필요/⚪미탐지)·대표 사례 포함 표를 issues.md 최상단에 배치, `wiki_generator.py`가 `owasp_top10.json`을 로드해 전달하도록 연결. `skills/harness-init/SKILL.md`·`agents/analyzer.md` 산출물 목록·용량 한도 표에도 반영. 페어 연동 시 병합 대상에서는 제외(issues.md는 저장소별 이슈라 기존부터 병합 대상 아님 — 2026-07-15 결정 재확인). 플러그인 버전 0.6.1 → 0.6.2 | agents/analyzer.md, agents/lib/analyzer_index_summary.py, agents/lib/wiki_content.py, agents/lib/wiki_generator.py, docs/index-spec.md, skills/harness-init/SKILL.md, .claude-plugin/plugin.json, CLAUDE.md | 사용자가 harness-init의 보안 분석과 생성된 wiki에 OWASP Top 10 웹 애플리케이션 10대 보안 취약점 매핑이 있는지 확인 요청 → 없음을 확인 후 추가 요청 |
| 2026-07-27 | 여러 시스템의 wiki를 버전 관리와 함께 중앙에서 열람하는 **wiki-hub** 기능 추가 — 별도 세션에서 이 저장소의 예전 버전을 토대로 먼저 진행된 작업 결과물(중간 산출물 폴더로 전달됨)을 검토해 이식. 검토 중 그 산출물 자체가 두 단계였음을 발견: 1차 시도는 DB 코드(스키마·버전관리·MSSQL 접속)를 harness 플러그인 안(`agents/lib/wiki_store.py` 등)에 직접 넣었으나, 곧이어 같은 세션에서 "harness는 여러 프로젝트에 설치되는데 DB 허브는 한 번 설치해 계속 떠 있어야 하는 서버 성격이라 안 맞는다"는 이유로 전량 폐기하고 **별도 독립 프로젝트 `wiki-hub`**(SQLAlchemy Core 단일 스키마로 MSSQL/PostgreSQL/Oracle/SQLite 4개 엔진 방언을 흡수, `wiki-hub-publish`/`wiki-hub-serve` 콘솔 명령 제공)로 재구성한 결과물이 최종본이었음 — 최종본만 이식하고 1차 시도는 반영하지 않음. **harness 쪽 변경**(이 저장소): `agents/lib/wiki_generator.py`의 `detected_types`(set) 정렬 없는 순회 버그 수정(`sorted()` 적용 — 내용이 같아도 call-graph.html 필터/범례 순서가 실행마다 달라져 나중에 wiki-hub에 발행할 때 헛된 버전이 쌓이는 문제 예방), 신규 스킬 `publish-wiki`(발행 오케스트레이터 — DB 엔진 선택·시스템 키/컴포넌트 확인·`wiki-hub-publish` 호출)·`wiki-hub`(허브 실행 오케스트레이터 — `wiki-hub-serve` 호출), `docs/wiki-hub.md`(왜 별도 프로젝트인지, 스키마 개요, 세 가지 열람 방법 비교), `generate-wiki` Phase 3.5(폴더 wiki 생성 완료 후 "중앙 허브에도 발행할까요?" 선택 질문 추가 — Y 시 `publish-wiki`로 연결), `harness-init`의 "위키 생성 선택 시" 안내를 Phase 0~3(기존)에서 Phase 0~3.5로 확장해 자동으로 이 질문까지 이어지도록 변경(harness-init 쪽에 별도 Phase를 중복 추가하지 않고 generate-wiki에 위임 — 원본 산출물은 harness-init에도 독립된 "Phase 3.7" 질문을 별도로 추가했으나, 이미 generate-wiki 내부에 있는 질문을 상위에서 다시 반복하는 것이라 판단해 단순화), `.env.example`·`.gitignore`에 wiki-hub용 필드(`WIKI_DB_ENGINE`/`PG_*`/`ORACLE_*`/`WIKI_DB_URL`/`WIKI_SYSTEM_NAME`/`WIKI_COMPONENT_KEY`/`WIKI_COMPONENT_TYPE`, `wiki_hub.db`류) 추가. **사용자가 명시적으로 v1(기존 `sync-wiki` 스킬 + `agents/lib/wiki_db.py`/`wiki_db_server.py` + `--storage db` 단일 테이블 저장)을 삭제하지 않고 그대로 보존하도록 결정** — wiki-hub는 v1을 대체하는 것이 아니라 "여러 시스템을 조직 차원에서 버전 관리와 함께 보는" 상위 계층으로 공존시킴. 이에 따라 원본 산출물의 wiki_generator.py 변경분 중 `--storage db` 옵션과 `wiki_db` import 제거 부분은 반영하지 않고 그대로 둠. **별도 프로젝트 wiki-hub**: 산출물 그대로 `E:/AI/wiki-hub`(이 저장소의 형제 디렉터리)에 신규 생성 — `wikihub/{models,store,publish,server,ui,render,config,index_extract}.py` + `tests/{test_dialect_compile,test_store_roundtrip}.py` + `pyproject.toml`/`README.md`/`requirements.txt`/`.env.example`. models.py·store.py 정독 결과 버전관리 로직(체크섬 비교 후에만 버전 증가·삭제는 표시만·되돌리기는 새 버전 추가) 결함 없음, CLI 인자가 `publish-wiki`/`wiki-hub` SKILL.md 문서와 정확히 일치함을 확인. ~~**미검증 항목**: 샌드박스 정책이 외부 산출물 코드의 `pip install`·테스트 스크립트 실행 자체를 차단(신뢰되지 않은 소스 코드 실행 금지 원칙)해 `tests/test_dialect_compile.py`·`tests/test_store_roundtrip.py` 실제 실행은 하지 못함 — 정적 코드 리뷰로만 확인.~~ **(2026-07-29 실행 검증 완료)**: `E:/AI/wiki-hub`에서 `pip install -e .` 실행(flat layout `pyproject.toml`의 `where=["src"]` 제거가 이미 정확히 반영돼 정상 설치됨) 후 두 테스트 모두 실제 실행. `test_dialect_compile.py` — 테이블 9개 × 엔진 4개(mssql/postgresql/oracle/sqlite) 컴파일 전부 통과(exit 0). 최초 실행 시 Windows 콘솔(cp949)이 마지막 요약 print의 em-dash·한글을 못 찍어 `UnicodeEncodeError`가 났으나 이는 로직 통과 이후의 print 단계 문제일 뿐 — `PYTHONIOENCODING=utf-8`로 재실행해 정상 출력과 exit 0을 재확인. `test_store_roundtrip.py` — SQLite 실접속으로 upsert/버전증가/무변경 스킵/삭제표시/되돌리기(이력 안 줄어듦)/검색/인덱스 교체/보관 처리 등 24개 체크 전부 OK, exit 0. 추가로 `E:/AI/00_sample/wiki-hub/src/wikihub/*.py`(8개 모듈)와 `E:/AI/wiki-hub/wikihub/*.py`를 diff해 바이트 단위 동일함을 재확인(포팅 누락 없음). 플러그인 버전 0.6.2 → 0.7.0 | agents/lib/wiki_generator.py, agents/lib/wiki_render.py, skills/publish-wiki(신규), skills/wiki-hub(신규), skills/generate-wiki/SKILL.md, skills/harness-init/SKILL.md, docs/wiki-hub.md(신규), .env.example, .gitignore, .claude-plugin/plugin.json, CLAUDE.md, [별도 프로젝트] E:/AI/wiki-hub/ 전체(신규) | 사용자가 별도 세션(E:\AI\00_sample\ax-std-harness + E:\AI\00_sample\wiki-hub)에서 진행된 다중 시스템 wiki 중앙 관리 기능을 이 저장소에도 반영해달라고 요청 |

# CLAUDE.md

**harness-fin** — ITO/SI 조직을 위한 확장 메타 하네스 템플릿.

## 이 저장소의 역할

`.claude/` 폴더에 *코드베이스 분석 + 수정/개발/마이그레이션 작업까지* 지원하는 에이전트 팀과 워크플로우 스킬이 포함되어 있다.

대상 프로젝트의 코드베이스를 분석해 맞춤형 CLAUDE.md / 워크플로우 스킬 / 도메인 에이전트 / 패턴 / 인덱스를 한 번에 생성하고, 이후 *수정·개발·마이그레이션 작업*까지 끊김 없이 지원한다.

[Malburi/harness-new](https://github.com/Malburi/harness-new)의 4-에이전트 파이프라인을 기반으로 [revfactory/harness](https://github.com/revfactory/harness)의 메타 방법론을 확장 적용했다.

## 실행 모드

**에이전트 팀** — `TaskCreate` 의존성 + `_workspace/` 파일 기반 산출물 전달

**팀 구성:**
- 분석/생성 파이프라인: `analyzer` → `writer` → (`pattern-extractor`) → `validator` → `qa`
- 품질 루프: `spec-clarifier` (Phase -1, 사전 명세화) + `harness-evaluator` (Phase 4, 사후 eval)
- 작업용 에이전트: `impact-analyzer`, `change-safety`, `migration-planner`, `test-generator`, `sql-reviewer`, `legacy-decoder`, `doc-syncer`, `logic-tracer`, `feature-finder`, `wiki-builder`

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
| `agents/wiki-builder.md` | harness 산출물 읽어 wiki 페이지 생성 + call_graph.json → vis-network 인터랙티브 HTML 변환 |

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
| 2026-06-02 | Claude Code 플러그인 표준 레이아웃으로 재구성 — `.claude/agents/`·`.claude/skills/` 중복본 제거, 루트 `agents/`·`skills/<name>/SKILL.md` 단일 source-of-truth로 정리, `.claude-plugin/marketplace.json`·`plugin.json` 추가 | 저장소 구조 | `/plugin marketplace add Malburi/harness-ito`로 설치 가능하도록 |
| 2026-06-02 | Vue.js 스택 지원 추가 — Vue 2/3, Nuxt 2/3, Pinia/Vuex, Vue Router, Vite, Vue CLI 탐지 + QA Boundary + 마이그레이션 매핑 (Vue 2→3, Vuex→Pinia, Nuxt 2→3, Vue CLI→Vite) | analyzer / qa / docs/stack-matrix / README | 프런트엔드 스택 커버리지 확장 |
| 2026-06-03 | 로직 탐색 에이전트 2종 추가 — `logic-tracer`(진입점→DB 처리 흐름 추적) + `feature-finder`(기능명·키워드 코드 위치 탐색) + 트리거 스킬 2종(`trace-logic`, `find-feature`) | agents / skills / CLAUDE.md | 특정 로직·기능 위치 탐색 요구 대응 |
| 2026-06-03 | 에이전트 모델 최적화 — opus→sonnet 8종(change-safety, pattern-extractor, validator, qa, test-generator, sql-reviewer, doc-syncer, logic-tracer). opus 유지 5종(analyzer, writer, legacy-decoder, impact-analyzer, migration-planner) | agents/ | 패턴 기반 처리 작업에 opus 불필요, 비용 절감 |
| 2026-06-03 | harness-init 3-Tier 적응 실행 — 복잡도 점수(파일수+DB/ORM+레거시+멀티모듈+외부시스템) 기반 Lite/Standard/Full 자동 분기. Lite: analyzer lite(sonnet)+writer(sonnet)+validator, QA·pattern 스킵. Standard: analyzer init(sonnet)+선택적 Phase B+writer(sonnet)+pattern+validator, QA 스킵. Full: 기존 파이프라인. 사용자 override 키워드 지원. | skills/harness-init / agents/analyzer | 프로젝트 규모 무관 전체 파이프라인 실행으로 인한 토큰·시간 낭비 해소 |
| 2026-06-04 | harness-clean 스킬 추가 — CLAUDE.md·.claude/skills/·agents/·patterns/·_workspace/ 안전 제거 + 플러그인 언인스톨 안내 | skills/harness-clean / CLAUDE.md | 마음에 안 들면 롤백할 수 있어야 표준으로 쓸 수 있음 |
| 2026-06-04 | Ouroboros 명세 게이트 + Karpathy eval 루프 접목 — spec-clarifier(sonnet, Phase -1: 소크라테스 인터뷰·모호성점수·GO신호) + harness-evaluator(sonnet, Phase 4: 4차원 품질평가·PASS/PARTIAL/RETRY·fix_targets 기반 타겟 재생성·1회 루프) + spec-gate 스킬 + harness-init Phase -1/-4 추가 + analyzer에 spec_context 전달 | agents/spec-clarifier, agents/harness-evaluator, skills/spec-gate, skills/harness-init, CLAUDE.md | 명세 모호성 제거(Ouroboros)·자기 개선 루프(Karpathy)로 harness 생성 품질 향상 |
| 2026-06-24 | wiki 생성 기능 추가 — `wiki-builder`(sonnet, harness 산출물→wiki 페이지·call_graph.json→vis-network 인터랙티브 HTML 변환·callgraph.html 템플릿 계승) + `generate-wiki` 오케스트레이터 스킬(기존 wiki 백업·페이지 범위 선택·call-graph.html 전용 페이지) + harness-init Phase 3.5(완료 후 wiki 생성 제안) | agents/wiki-builder, skills/generate-wiki, skills/harness-init, CLAUDE.md | harness 완료 후 탐색 가능한 wiki 문서 자동 생성 요구 대응 |

---
name: harness-init
description: 프로젝트를 심층 분석해 맞춤형 하네스(CLAUDE.md, 5+ 워크플로우 스킬, 도메인 에이전트, 패턴, 인덱스)를 자동 생성하는 오케스트레이터. "하네스 초기화", "하네스 만들어줘", "하네스 다시 초기화", "harness 다시 만들어줘", "프로젝트 분석해서 설정해줘", "이 프로젝트 Claude 설정해줘", "create harness", "initialize harness", "re-initialize harness", "generate project harness", "하네스 업데이트", "하네스 보완", "스킬만 다시 생성", "에이전트만 다시 생성", "validator만 다시 실행", "패턴 추출해줘", "pattern extract" 요청 시 사용. `.claude/skills/trace.md` 또는 `.claude/skills/analyze-impact.md`가 없으면 자동 트리거.
---

# Harness Initializer (Enhanced) — 팀 모드 오케스트레이터

프로젝트 코드베이스를 심층 분석해 *수정·개발·마이그레이션 작업까지 지원하는* 맞춤형 harness를 자동 생성한다.

기존 harness-new가 만들던 5종 + harness-fin이 추가하는 5종 + 인덱스 + 패턴까지 한 번에 생성.

**실행 모드:** 에이전트 팀 (TaskCreate 의존성 + `_workspace/` 파일 기반 산출물 전달)

**팀 구성 (확장):**
- 필수 파이프라인: analyzer → writer → validator → qa
- 선택 추가: pattern-extractor (writer 직후, 패턴 채우기)
- 품질 루프: spec-clarifier (Phase -1) + harness-evaluator (Phase 4)

---

## Phase -2: 프로젝트 구조 확인

> **스킵 조건**: 아래 중 하나라도 해당하면 Phase -1로 직행
> - `_workspace/pair_config.md` 이미 존재 (이전 연동 설정 완료)
> - 부분 재실행 ("스킬만"·"에이전트만"·"validator만" 등)
> - 재초기화 + "다시"만 있음 (추가 목표 변경 없음)

사용자에게 다음 질문을 제시한다:

```
이 프로젝트의 구조를 알려주세요:

  1. 한 폴더 안에 모두 있음
     백엔드·프론트엔드가 같은 루트 하위에 함께 위치
     (예: /my-project/backend/, /my-project/frontend/)

  2. 별도 폴더/저장소로 분리됨
     백엔드·프론트엔드가 각각 독립된 폴더나 저장소에 위치
     (예: /workspace/my-backend/, /workspace/my-frontend/)

  3. 단일 스택 (백엔드만 또는 프론트엔드만)

어느 쪽인가요? (1/2/3)
```

**응답별 분기:**

| 응답 | 설정 | 다음 단계 |
|------|------|---------|
| 1 (모노레포) | `repo_structure = "mono"` | Phase -1로 진행 |
| 2 (멀티레포) | `repo_structure = "multi"` | 파트너 정보 수집 → Phase -1로 진행 |
| 3 (단일 스택) | `repo_structure = "single"` | Phase -1로 진행 |
| 기타·미응답 | `repo_structure = "unknown"` | Phase -1로 진행 |

### 멀티레포 파트너 정보 수집 (응답 2인 경우)

연속해서 파트너 정보를 입력받는다:

```
파트너 프로젝트 정보를 입력해주세요:

1. 현재 프로젝트 역할: backend / frontend / fullstack
2. 파트너 프로젝트 절대 경로:
   (예: C:\work\my-frontend 또는 /home/user/my-frontend)
3. API base URL (선택 — 로컬 개발 기준):
   (예: http://localhost:8080 — 모르면 빈칸)
```

입력받은 정보를 `partner_info = { role, path, api_url }` 변수에 저장.  
경로 유효성 확인 및 파트너 하네스 존재 여부는 pair-init Phase 1에서 수행.

> 수집한 `partner_info`는 Phase 3.5에서 pair-init 자동 실행 시 컨텍스트로 전달된다.

---

## Phase -1: 명세 명확화 (Spec Gate) — Ouroboros 영감

### 실행 여부 결정

다음 조건 중 하나에 해당하면 **Phase -1 스킵** → Phase 0 직행:

| 조건 | 이유 |
|------|------|
| "빠르게"·"quick"·"fast"·"스킵"·"skip spec" 포함 | 빠른 초기화 요청 |
| 부분 재실행 ("스킬만"·"에이전트만"·"validator만" 등) | 이미 범위 명확 |
| `_workspace/00_spec_report.md` 존재 | 이미 명세화 완료 |
| 재초기화 + "다시"만 있음 (추가 목표 변경 없음) | 동일 범위 재실행 |

그 외 **초기 실행 / Standard·Full Tier 예상**이면 spec gate 실행.

### spec-clarifier 호출 (question 모드)

```
Agent(
  subagent_type="general-purpose",
  description="명세 명확화 질문 생성",
  prompt="<spec-clarifier 에이전트 지침에 따라 질문 세트를 생성한다.
  mode: question.
  프로젝트 루트: [절대경로].>",
  model="sonnet"
)
```

반환된 질문 세트를 사용자에게 그대로 제시한다.  
**사용자 응답 후에만 다음 단계 진행. 응답 전 Phase 0 진입 금지.**

### spec-clarifier 호출 (score 모드)

사용자 응답을 받아 점수화:

```
Agent(
  subagent_type="general-purpose",
  description="응답 점수화 + 명세 리포트",
  prompt="<spec-clarifier 에이전트 지침에 따라 응답을 점수화하고 리포트를 작성한다.
  mode: score.
  원본 질문: [Phase -1 question 모드 결과].
  사용자 응답: [사용자 응답 전문].
  출력: _workspace/00_spec_report.md>",
  model="sonnet"
)
```

### GO 신호 확인

`_workspace/00_spec_report.md`의 신호 확인:

| 신호 | 동작 |
|------|------|
| **GO** (점수 ≤ 0.2) | Phase 0으로 진행 |
| **REFINE** (점수 0.21~0.4) | spec-clarifier가 작성한 재질문 제시 → 응답 수신 → score 재실행 (1회 한도) → Phase 0 진행 |
| **GO (미답변 진행)** (점수 > 0.4) | Phase 0으로 진행 |

> **`tier_suggestion`이 있으면** Step 2.5 Tier 결정 시 참고 입력으로 활용 (최종 결정은 복잡도 점수 기반).

---

## Phase 0: 컨텍스트 확인

### Step 1: 작업 디렉토리 확인
`pwd`로 절대 경로 확보.

### Step 2: 기존 하네스 감지

| 확인 대상 | 의미 |
|----------|------|
| `CLAUDE.md` 존재 + "## 변경 이력" 섹션 | 기존 하네스 있음 |
| `.claude/skills/trace.md` 존재 | 기존 스킬 있음 |
| `.claude/skills/analyze-impact.md` 존재 | harness-fin v1 이상 |
| `.claude/agents/domain-expert.md` | 도메인 에이전트 있음 |
| `_workspace/` 존재 | 이전 산출물 있음 |
| `_workspace/index/*.json` 존재 | 인덱스 있음 (incremental 가능) |
| `_workspace/pair_config.md` 존재 | 파트너 프로젝트 연동 상태 → partner_root 변수 설정 |

### Step 2.5: 복잡도 점수 계산 + Tier 결정

**① 사용자 요청 override 먼저 확인** (점수 계산 불필요):

| 키워드 | Tier 강제 |
|--------|---------|
| "빠르게"·"간단히"·"빠른"·"quick"·"fast" | **Lite** |
| "깊게"·"심층"·"마이그레이션"·"레거시"·"전체"·"migration"·"legacy"·"deep" | **Full** |

**② override 없으면 복잡도 점수 계산:**

소스 파일 수 빠른 카운트 (find 또는 PowerShell):
```
# bash
find . -type f \( -name "*.java" -o -name "*.kt" -o -name "*.js" -o -name "*.ts" -o -name "*.py" -o -name "*.vue" -o -name "*.cs" -o -name "*.go" \) | wc -l

# PowerShell
(Get-ChildItem -Recurse -Include *.java,*.kt,*.js,*.ts,*.py,*.vue,*.cs,*.go -ErrorAction SilentlyContinue).Count
```

점수 항목 (누적):

| 항목 | 탐지 방법 | 점수 |
|------|---------|------|
| 소스 파일 수 | 위 카운트 결과 | × 1 |
| DB/ORM 존재 | `pom.xml`/`package.json`에서 mybatis·jpa·hibernate·typeorm·prisma·sequelize·sqlalchemy 확인 | +30 |
| 레거시 스택 | Struts·iBatis·JSP 50개+·전자정부(egovframework)·`WEB-INF/web.xml` | +40 |
| 멀티 모듈 | 루트 외 하위에 `pom.xml`/`build.gradle`/`package.json` 2개+ 존재 | +20 |
| 외부 시스템 | `RestTemplate`·`WebClient`·`axios`·`fetch`·`kafka`·`rabbit`·`feign` 패턴 grep | +20 |

**③ Tier 결정:**

| 점수 | Tier | 실행 구성 | 스킵 항목 |
|------|------|---------|---------|
| 0~50 | **Lite** | analyzer(lite/sonnet) → writer(sonnet) → validator | pattern-extractor, QA 스킵 |
| 51~120 | **Standard** | analyzer(init/sonnet, 스택 해당 Phase B만) → writer(sonnet) → pattern(병렬) → validator | QA 스킵 |
| 121+ | **Full** | 전체 파이프라인 (기존 동일) | — |

Tier와 산정 근거를 사용자에게 한 줄 표시:
```
[Tier: Standard] 소스 213파일(+213) + DB/ORM(+30) + 멀티모듈(+20) = 263점 → Standard
```

### Step 3: 실행 모드 분기

| 상황 | 모드 | 처리 |
|------|------|------|
| 기존 하네스 없음 | **초기 실행** | 전체 파이프라인 (analyzer init + writer + validator + qa + pattern-extractor) |
| 기존 + "다시"·"새로" | **재초기화** | `.claude/backup/[YYYYMMDD-HHMMSS]/`로 백업 후 전체 실행 (analyzer init 모드) |
| 기존 + "스킬만"·"에이전트만"·"validator만"·"qa만"·"패턴만" | **부분 재실행** | 해당 단계만, 이전 `_workspace/` 산출물 재사용 |
| 기존 + 일반 보완 | **업데이트** | 백업 후 analyzer incremental + 재실행 |
| 코드 변경 후 인덱스만 갱신 | **인덱스 리프레시** | analyzer incremental만 |

백업 절차:
- PowerShell: `Get-Date -Format "yyyyMMdd-HHmmss"`
- 백업 대상: `CLAUDE.md`, `.claude/skills/*.md` (harness-init.md 제외), `.claude/agents/*.md` (공통 에이전트는 제외, 프로젝트 전용만), `.claude/patterns/`
- 백업 위치: `.claude/backup/[YYYYMMDD-HHMMSS]/`

### Step 4: 작업공간 준비

`_workspace/` 디렉토리:
- 초기 실행/재초기화: `_workspace/`를 `_workspace_prev/`로 이동 후 새로 생성
- 부분 재실행: 기존 유지

산출물 파일명:
```
_workspace/00_spec_report.md          ← spec-clarifier (Phase -1)
_workspace/01_analyzer_report.md      ← analyzer
_workspace/02_writer_files.md         ← writer
_workspace/03_validator_report.md     ← validator
_workspace/04_qa_report.md            ← qa
_workspace/05_patterns_extracted.md   ← pattern-extractor
_workspace/06_eval_report.md          ← harness-evaluator (Phase 4)
_workspace/index/*.json               ← analyzer (인덱스)
```

---

## Phase 1: 공유 작업 계획

`TaskCreate`로 팀원별 작업 + 의존성 설정 (Tier에 따라 생성 작업 다름):

**Lite:**
```
T-A (analyzer lite):  → _workspace/01_analyzer_report.md
T-W (writer):         → _workspace/02_writer_files.md     (blockedBy: T-A)
T-V (validator):      → _workspace/03_validator_report.md (blockedBy: T-W)
T-E (harness-eval):   → _workspace/06_eval_report.md      (blockedBy: T-V)
```

**Standard:**
```
T-A (analyzer):          → _workspace/01_analyzer_report.md + _workspace/index/*.json
T-W (writer):            → _workspace/02_writer_files.md           (blockedBy: T-A)
T-V (validator):         → _workspace/03_validator_report.md       (blockedBy: T-W)
T-P (pattern-extractor): → _workspace/05_patterns_extracted.md     (blockedBy: T-W)
T-E (harness-eval):      → _workspace/06_eval_report.md            (blockedBy: T-V)
```
T-P는 T-W 완료 후 T-V/T-E와 병렬 실행 가능.

**Full:**
```
T-A (analyzer):          → _workspace/01_analyzer_report.md + _workspace/index/*.json
T-W (writer):            → _workspace/02_writer_files.md           (blockedBy: T-A)
T-V (validator):         → _workspace/03_validator_report.md       (blockedBy: T-W)
T-Q (qa):                → _workspace/04_qa_report.md              (blockedBy: T-V)
T-P (pattern-extractor): → _workspace/05_patterns_extracted.md     (blockedBy: T-W)
T-E (harness-eval):      → _workspace/06_eval_report.md            (blockedBy: T-Q)
```
T-P는 T-W 완료 후 T-V/T-Q와 병렬 실행 가능. T-E는 T-Q 완료 후 실행.

---

## Phase 2: 팀원 실행

### 2-1. analyzer 호출

부분 재실행 + `_workspace/01_analyzer_report.md` 존재 시 스킵.

Tier별 mode/model 결정:
| Tier | mode | model |
|------|------|-------|
| Lite | `lite` (Phase A만) | sonnet |
| Standard | `init` (A + 스택 해당 Phase B만) | sonnet |
| Full | `init` (A + B 전체) | opus |

```
Agent(
  subagent_type="general-purpose",
  description="프로젝트 분석",
  prompt="<analyzer 에이전트 지침에 따라 분석. 프로젝트 루트: [절대경로]. mode: [lite/init]. tier: [Lite/Standard/Full].
  (Phase -1 실행 시) spec_context: _workspace/00_spec_report.md의 'Analyzer 지시 사항' 섹션 참조
  — scope_hint, goal_hint, constraint_hint, priority_hint를 분석 범위·우선순위에 반영할 것.
  결과: _workspace/01_analyzer_report.md + (Standard/Full만) _workspace/index/*.json>",
  model="[sonnet/opus]"
)
```

`.claude/agents/analyzer.md`의 지침 따름. 완료 후 결과 파일 존재 확인.

### 2-2. writer 호출

`_workspace/01_analyzer_report.md` 존재 확인 후.

Tier별 model:
| Tier | model |
|------|-------|
| Lite / Standard | sonnet |
| Full | opus |

```
Agent(
  subagent_type="general-purpose",
  description="하네스 파일 생성",
  prompt="<writer 에이전트 지침에 따라 하네스 파일 작성. 프로젝트 루트: [절대경로]. tier: [Lite/Standard/Full]. 입력: _workspace/01_analyzer_report.md. 출력: 하네스 파일들(trace/scaffolder/find-logic, cross-repo-* 있는 경우) + _workspace/claude_md_fields.json + _workspace/writer_decisions.json>",
  model="[sonnet/opus]"
)
```

> writer는 trace.md·scaffolder.md·find-logic.md만 markdown으로 직접 작성한다 (pair_config.md 있으면 cross-repo-scaffold.md·cross-repo-modify.md도). CLAUDE.md는 `_workspace/claude_md_fields.json`에 필드(프로젝트명·한줄설명·스택요약·요청흐름·파일위치표 행·빌드명령·주의사항)만, patterns 스켈레톤·02_writer_files.md는 `_workspace/writer_decisions.json`에 결정 값(조건부 스킬 생성 여부+사유, 패턴 파일명 목록, 탐지 스택, 적용 결정 사유)만 채워서 낸다. domain-expert.md(analyzer_report 그대로 주입)와 analyze-impact.md·safe-modify.md·scaffold-feature.md·plan-migration.md·review-sql.md(정적 텍스트)·patterns 스켈레톤·02_writer_files.md는 writer가 쓰지 않고 다음 단계(2-2.3)에서 배포한다.

### 2-2.3. skills_builder.py 실행 (CLAUDE.md + 정적 워크플로우 스킬 + domain-expert.md + 패턴 스켈레톤 + 02_writer_files.md 배포)

writer 완료 후 다음을 전부 처리한다 (LLM 호출 없음, 전부 결정론적 파일 조립/복사):
- `_workspace/claude_md_fields.json` + `agents/lib/claude_md.template.md`(고정 골격) → `CLAUDE.md` 조립. `pair_config.md` 있으면 "파트너 프로젝트" 섹션도 그 필드값으로 자동 채움
- `_workspace/writer_decisions.json`의 생성 여부 판단을 읽어 정적 스킬 템플릿(`agents/lib/skills/*.template.md`)을 대상 프로젝트 `.claude/skills/`에 복사 (analyze-impact/safe-modify/scaffold-feature는 항상, plan-migration/review-sql은 조건 충족 시만)
- `_workspace/01_analyzer_report.md`를 그대로 복사해 `.claude/agents/domain-expert.md` 생성
- `writer_decisions.json`의 `pattern_files` 목록(+ "LegacyStaticJS" 탐지 시 client_pattern.md 자동 추가)으로 `.claude/patterns/*.md` 스켈레톤 생성 (이미 pattern-extractor가 채운 파일은 덮어쓰지 않음)
- 위 모든 결과 + `writer_decisions.json`을 조합해 `_workspace/02_writer_files.md` 조립

```powershell
python agents/lib/skills_builder.py --root "[절대경로]" --summary "_workspace/writer_decisions.json"
```

실패 시(python 미설치, claude_md_fields.json/writer_decisions.json 누락 등) 1회만 재시도하고, 그래도 실패하면 "CLAUDE.md/정적 스킬/domain-expert.md/패턴 스켈레톤/02_writer_files.md 배포 실패 — writer 재실행 또는 수동 작성 필요" WARN 후 계속 진행 (개별 항목은 부분적으로 성공할 수 있음 — 스크립트가 항목별로 독립 처리).

### 2-2.5. ito-guide.md 생성 (writer 완료 직후, 모든 Tier)

writer 실행 직후, `.claude/ito-guide.md` 사용 가이드를 생성한다.

```
Agent(
  subagent_type="general-purpose",
  description="ito-guide.md 사용 설명서 생성",
  prompt="프로젝트 루트 [절대경로]의 .claude/ito-guide.md 를 생성하라.

  다음 정보를 Read 도구로 수집 후 작성:
  - _workspace/01_analyzer_report.md (스택·파일 위치 파악)
  - _workspace/02_writer_files.md (생성된 스킬/에이전트 목록)
  - .claude/skills/*.md (각 스킬 트리거 조건)

  파일 구조:
  # ito-guide — [프로젝트명] 하네스 사용 설명서

  ## 1. 스킬 사용법
  생성된 각 스킬에 대해: 트리거 예시 문장 2~3개 + 어떤 상황에 쓰는지 한 줄 설명

  ## 2. 에이전트 직접 호출
  domain-expert / legacy-decoder / doc-syncer 사용 방법

  ## 3. 패턴 파일 참조
  .claude/patterns/*.md 각 파일의 용도 및 scaffold-feature와의 연계

  ## 4. 인덱스 파일 설명
  _workspace/index/*.json 각 파일 용도 (코드 수정 전 영향 확인 방법)

  ## 5. 실전 시나리오
  (분석 리포트에서 파악한 스택 기반으로) 가장 자주 쓰일 법한 시나리오 3~4개:
  예: '신규 기능 추가', 'SQL 수정', '기존 코드 수정 전 영향 확인', '화면 오류 추적'
  각 시나리오: 상황 설명 + 사용할 스킬/에이전트 + 예시 트리거 문장

  ## 6. 주의사항
  CLAUDE.md 의 '작업 시 주의사항' 핵심 항목 요약 (3~5개)

  ## 7. 하네스 갱신
  코드 변경 후 인덱스·패턴 갱신 방법 한 줄 안내

  작성 원칙:
  - 마크다운 서술형. 도표·코드블록 적극 활용.
  - 실제 생성된 스킬/파일명만 참조 (없는 스킬 언급 금지).
  - 한국어로 작성.",
  model="sonnet"
)
```

완료 후 `.claude/ito-guide.md` 존재 확인. 실패해도 파이프라인 계속 진행 ("ito-guide 미생성" WARN으로 처리).

### 2-3. pattern-extractor 호출 (Standard/Full만, 병렬 가능)

**Lite면 스킵.**

writer 완료 후 patterns/ 스켈레톤이 생성되어 있을 때만 호출.

```
Agent(
  subagent_type="general-purpose",
  description="패턴 추출",
  prompt="<pattern-extractor 에이전트 지침. 프로젝트 루트: [절대경로]. 입력: .claude/patterns/*.md 스켈레톤 + _workspace/01_analyzer_report.md. 출력: 패턴 파일 본문 + _workspace/05_patterns_extracted.md>",
  model="sonnet"
)
```

### 2-4. validator 호출

모든 Tier에서 실행. `_workspace/02_writer_files.md` 확인 후, validator Agent() 호출 전에 기계 체크를
먼저 실행 (LLM 미사용 — validator 체크 1,2,3,4,6,7,8,9를 대신 계산):

```powershell
python agents/lib/validator_checks.py --root "[절대경로]" --out "_workspace/validator_mechanical.json"
```

실패 시(python 미설치 등) WARN 후 계속 진행 — validator가 해당 체크를 직접 수행하는 기존 방식으로 폴백.

```
Agent(
  subagent_type="general-purpose",
  description="하네스 구조 검증",
  prompt="<validator 에이전트 지침. 프로젝트 루트: [절대경로]. tier: [Lite/Standard/Full]. 입력: _workspace/01_analyzer_report.md, _workspace/02_writer_files.md, _workspace/validator_mechanical.json(있으면), (있으면) _workspace/index/. 출력: _workspace/03_validator_report.md>",
  model="sonnet"
)
```

### 2-5. qa 호출 (Full만)

**Lite/Standard면 스킵.** Full + validator 통과 후에만 실행. qa Agent() 호출 전에 Boundary 6 기계
체크를 먼저 실행 (LLM 미사용):

```powershell
python agents/lib/qa_boundary6.py --root "[절대경로]" --out "_workspace/qa_boundary6.md"
```

실패 시 WARN 후 계속 진행 — qa가 Boundary 6을 직접 확인하는 기존 방식으로 폴백. **qa Agent 호출은 반드시 `general-purpose` 타입.**

```
Agent(
  subagent_type="general-purpose",
  description="경계면 교차 비교 QA",
  prompt="<qa 에이전트 지침. 프로젝트 루트: [절대경로]. 입력: _workspace/01~03 + _workspace/qa_boundary6.md(있으면) + _workspace/index/. 출력: _workspace/04_qa_report.md>",
  model="sonnet"
)
```

QA 우회 조건: `_workspace/03_validator_report.md`의 신뢰도 < 50 → qa는 "구조 검증 실패로 미실행" 한 줄만 작성하고 종료.

### 2-6. harness-evaluator 호출 (모든 Tier)

qa (Full) 또는 validator (Lite/Standard) 완료 후 실행:

```
Agent(
  subagent_type="general-purpose",
  description="harness 품질 평가",
  prompt="<harness-evaluator 에이전트 지침에 따라 생성된 harness 파일들의 품질을 평가한다.
  프로젝트 루트: [절대경로]. tier: [Lite/Standard/Full].
  입력: _workspace/01_analyzer_report.md, _workspace/03_validator_report.md,
        생성된 harness 파일들 (CLAUDE.md, .claude/skills/, .claude/agents/, .claude/patterns/),
        (있으면) _workspace/00_spec_report.md.
  출력: _workspace/06_eval_report.md>",
  model="sonnet"
)
```

---

## Phase 3: 결과 종합 및 보고

`_workspace/03_validator_report.md`, `_workspace/04_qa_report.md`, `_workspace/05_patterns_extracted.md`를 읽어 사용자에게 다음 형식으로 보고:

```
하네스 초기화 완료 (harness-fin v1) [Tier: Lite/Standard/Full | 복잡도 점수: N점]

생성된 파일:

[Core]
- CLAUDE.md
- .claude/ito-guide.md               (사용 설명서)
- .claude/skills/trace.md, scaffolder.md, find-logic.md
- .claude/agents/domain-expert.md
- .claude/patterns/[목록]

[Workflow Skills (NEW)]
- .claude/skills/analyze-impact.md
- .claude/skills/safe-modify.md
- .claude/skills/scaffold-feature.md
- .claude/skills/plan-migration.md          (생성 조건 충족 시)
- .claude/skills/review-sql.md              (DB 사용 시)

[Indexes (NEW)]
- _workspace/index/call_graph.json (노드: N, 엣지: M)
- _workspace/index/symbols.json
- _workspace/index/transactions.json
- _workspace/index/external_io.json
- _workspace/index/sql_usage.json           (DB 사용 시)
- _workspace/index/schema.json              (DB 접속 가능 시)
- _workspace/index/dead_code.json
- _workspace/index/env_branches.json

구조 검증 (validator):
[신뢰도 점수 + 보완 권장 항목]

경계면 교차 비교 (qa):
🔴 HIGH: [개수 + 상세]
🟡 MEDIUM: [...]
🟢 LOW: [...]

패턴 추출 (pattern-extractor):
- 처리한 패턴 파일: N개
- 신뢰도: [HIGH: A, MEDIUM: B, LOW: C]
- 안티패턴 발견: K건

Eval 품질 점수 (harness-evaluator):
[점수: N/100 — PASS / PARTIAL / RETRY]
- 커버리지: /25 | 정확도: /25 | 실행가능성: /25 | 컨텍스트 품질: /25
(PARTIAL/RETRY이면 → Phase 4 재생성 실행 후 최종 점수 업데이트)

이제 다음 작업이 가능합니다:
  "이 함수 영향도 분석해줘"          → analyze-impact
  "이 변경 안전하게 적용"            → safe-modify
  "[기능] 패턴 따라 만들어줘"        → scaffold-feature
  "Spring Boot로 마이그레이션"       → plan-migration
  "이 SQL 리뷰해줘"                  → review-sql
  "이 코드 뭐하는 거야"              → legacy-decoder (직접 호출)
  "문서 동기화"                      → doc-syncer (직접 호출)

다음 단계:
  git add CLAUDE.md .claude/ && git commit -m "docs: add project harness (harness-fin v1)"

피드백 요청:
결과에서 개선할 부분이 있나요? 워크플로우 스킬 트리거 조정이 필요한가요?
```

HIGH 우선순위 항목이 있으면 사용자에게 명시적 안내. 자동 수정 X.

---

## Phase 3.5: 파트너 연동 (pair-init)

**Phase -2 결과 및 기존 설정 기반 분기:**

| 조건 | 동작 |
|------|------|
| `repo_structure = "mono"` 또는 `"single"` | 이 Phase 전체 스킵 → Phase 3.6으로 |
| `_workspace/pair_config.md` 이미 있음 | 이 Phase 전체 스킵 → Phase 3.6으로 |
| `repo_structure = "multi"` + `partner_info` 수집됨 | pair-init 자동 실행 (사용자 확인 생략) → Phase 3.6으로 |
| Phase -2 스킵 + `pair_config.md` 없음 | 연동 여부 질문 후 진행 |

### pair-init 자동 실행 (멀티레포 + 파트너 정보 있는 경우)

사용자에게 다음을 안내한 후 pair-init 스킬을 실행한다:

```
[Phase 3.5] pair-init 시작 — 파트너 프로젝트 연동 중
파트너 경로: [partner_info.path]
```

pair-init 스킬을 다음 컨텍스트로 실행:
- 현재 프로젝트 역할: `partner_info.role`
- 파트너 절대 경로: `partner_info.path`
- API base URL: `partner_info.api_url` (미입력 시 pair-init Phase 1에서 재확인)
- pair-init Phase 1의 사용자 질문 중 이미 수집된 항목은 생략하고 Phase 2부터 실행

### 파트너 하네스 없는 경우 — 자동 생성 (harness-init 주도 흐름 한정)

pair-init Phase 1에서 파트너 `CLAUDE.md`가 없어 3지선다가 뜨는 경우, **harness-init이 이미 멀티레포 의도를 확인한 상태**이므로 사용자에게 다시 묻지 않고 선택지 1(자동 생성)을 기본 적용한다.

pair-init이 실행하는 "파트너 하네스 자동 생성" Agent 호출(파트너 루트에서 harness-init 재실행)은 아래처럼 **이번 턴의 Phase 4(harness-evaluator) 호출과 같은 메시지에서 병렬로 발행**한다 — 두 작업은 서로 독립적이므로 (파트너 초기화는 파트너 프로젝트를 대상으로, evaluator는 현재 프로젝트 결과물을 대상으로) 동시 실행 가능:

```
[같은 메시지 — 병렬 Agent 호출 2건]
1) 파트너 하네스 자동 생성 subagent (pair-init 내부 호출, 대상: 파트너 루트)
2) harness-evaluator (Phase 4, 대상: 현재 프로젝트 _workspace/)
```

두 호출이 모두 반환되면 다음으로 진행. 파트너 초기화가 evaluator보다 오래 걸리면, 현재 프로젝트의 Phase 4 결과 보고를 먼저 사용자에게 보여주고 "파트너 하네스 생성 중..." 안내 후 완료를 기다린다 (join).

> 파트너 초기화 subagent가 실패해도 현재 프로젝트 파이프라인은 막지 않는다 — WARN 기록 후 Phase 3.6에서 통합 wiki 대신 단독 wiki 제안으로 폴백.

### 연동 여부 질문 방식 (Phase -2 스킵 + pair_config.md 없는 경우)

```
백엔드/프론트엔드가 별도 저장소로 분리되어 있나요?
pair-init으로 연동하면 아래가 가능합니다:
  - 전체 스택 기능 동시 생성 (cross-repo-scaffold)
  - API 변경 시 파트너 영향 자동 감지 (analyze-impact 확장)
  - API 드리프트 감지 (프론트↔백엔드 호출 불일치 탐지)

연동하시겠습니까? (Y/N)
```

| 응답 | 동작 |
|------|------|
| Y / 예 / yes / 연동 | `pair-init` 스킬 실행 → 연동 완료 후 Phase 3.6으로 |
| N / 아니오 / no / 나중에 | "나중에 필요하면 `페어 설정해줘`라고 하세요" 안내 후 Phase 3.6으로 |

---

## Phase 3.6: Wiki 생성 제안

Phase 3 보고 직후, `_workspace/pair_config.md` 존재 + 파트너 `CLAUDE.md` 존재(파트너 초기화 완료) 여부를 확인한다.

### 파트너 하네스가 있는 경우 (pair_config.md 존재 + 파트너 완료) — 통합 wiki 질문

```
wiki를 생성하시겠습니까? (Phase 3.6)
파트너 프로젝트([partner_root])도 하네스가 준비되어, 통합(cross-repo) wiki 생성이 가능합니다:
  - Home, 워크플로우 스킬 사용법, 패턴, 이슈 목록 — 이 저장소 기준
  - 통합 아키텍처/API 엔드포인트/DB 스키마/외부 연동 — 백엔드+프론트엔드 데이터가 한 페이지에 병합
  - 통합 호출 그래프 — 백엔드+프론트엔드 call_graph.json 병합, API 계약 기준 크로스 엣지 자동 추론

  1. 통합 wiki 생성 (권장) — 현재 프로젝트에 파트너 정보까지 포함된 wiki 생성
  2. 이 프로젝트 단독 wiki만 생성
  3. 생성 안 함

선택? (1/2/3)
```

| 선택 | 동작 |
|------|------|
| 1 또는 2 | `generate-wiki` 스킬 실행 → 완료 후 Phase 4로 진행 (pair_config.md가 있으면 `wiki_generator.py`가 파트너의 call_graph.json뿐 아니라 01_analyzer_report.md·api_contract.json·schema.json·external_io.json도 함께 읽어 architecture/api-endpoints/database/external-systems 페이지에 자동 병합하므로, "2. 단독"을 선택해도 통합 wiki가 나타나는 게 정상 동작임을 안내) |
| 3 | 스킵 → Phase 4로 진행 |

### 파트너 하네스 없는 경우 (단일 스택 / 모노레포 / 파트너 초기화 실패) — 기존 질문

```
wiki를 생성하시겠습니까? (Phase 3.6)
harness 산출물(_workspace + .claude)을 기반으로 아래 페이지를 포함한 wiki를 생성합니다:
  - Home, 아키텍처, 워크플로우 스킬 사용법
  - 호출 그래프 (call_graph.json → vis-network 인터랙티브 HTML, callgraph.html 스타일 적용)
  - API 엔드포인트, DB 스키마, 패턴, 외부 연동, 이슈 목록 (탐지된 경우)

생성하시겠습니까? (Y/N)
```

**사용자 응답 처리:**

| 응답 | 동작 |
|------|------|
| Y / 예 / yes / 생성 / 만들어줘 | `generate-wiki` 스킬 실행 → wiki 생성 후 Phase 4로 진행 |
| N / 아니오 / no / 나중에 / 스킵 | wiki 생성 건너뜀 → Phase 4로 진행 |
| (무응답·기타) | "나중에 필요하면 `wiki 만들어줘`라고 하세요" 안내 후 Phase 4로 진행 |

> Phase 3.5와 Phase 3.6 질문은 **순서대로** 제시. 두 질문을 동시에 보여주지 않는다.

`generate-wiki` 실행 시 → `generate-wiki` 스킬의 Phase 0~3을 그대로 수행한다. Phase 0의 "사전 확인"은 harness-init이 방금 완료했으므로 존재 확인은 스킵 가능.

> **어느 쪽에서 실행해도 통합됨**: `wiki_generator.py`는 pair_config.md의 `partner_workspace`를 읽어 call_graph.json 병합(`merge_partner_call_graph()`)뿐 아니라 architecture/api-endpoints/database/external-systems 4개 markdown 페이지에도 파트너 데이터를 병합하므로, frontend에서 generate-wiki를 실행해도 backend에서 실행해도 동일하게 통합 wiki가 나온다. 프론트엔드 쪽에서 통합 wiki를 보고 싶으면 프론트엔드 프로젝트에서 generate-wiki를 실행하면 된다.

---

## Phase 4: Eval Loop — Karpathy AutoResearch 영감

Phase 2-6에서 harness-evaluator가 실행되었다면 `_workspace/06_eval_report.md`에서 총점 확인.

### 점수별 동작

| 총점 | 결정 | 동작 |
|------|------|------|
| 80~100 (PASS) | 완료 | Phase 3 보고 그대로 사용자에게 전달 |
| 60~79 (PARTIAL) | 타겟 재생성 | fix_targets 기반 특정 에이전트 재실행 → 재평가 (1회) |
| 0~59 (RETRY) | 주요 재생성 | fix_targets 상위 2개 에이전트 재실행 → 재평가 (1회) |

### 타겟 재생성 실행 (PARTIAL/RETRY)

`_workspace/06_eval_report.md`의 fix_targets를 읽어 각 에이전트 재실행:

```
for each fix_target in eval_report.fix_targets (우선순위 순):
  Agent(
    subagent_type="general-purpose",
    description="[fix_target.agent] 개선 재실행",
    prompt="<[fix_target.agent] 에이전트 지침에 따라 재실행한다.
    개선 지시: [fix_target.instruction].
    범위: [fix_target.scope].
    프로젝트 루트: [절대경로].
    기존 산출물: _workspace/01_analyzer_report.md, _workspace/02_writer_files.md>",
    model="[tier별 모델]"
  )
```

재생성 완료 후 harness-evaluator 1회 재실행 (평가 회차 = 2):

```
Agent(
  subagent_type="general-purpose",
  description="harness 품질 재평가 (2차)",
  prompt="<harness-evaluator 에이전트 지침. 평가 회차: 2.
  프로젝트 루트: [절대경로]. tier: [Lite/Standard/Full].
  출력: _workspace/06_eval_report.md (덮어쓰기)>",
  model="sonnet"
)
```

2차 평가 후에는 점수와 무관하게 Phase 3 보고로 넘어간다. **무한 루프 없음.**

### 개선 델타 표시

Phase 3 보고 중 "Eval 품질 점수" 섹션에 1차→2차 점수 변화 표시:

```
Eval 품질 점수: 63/100 → 84/100 (+21, PARTIAL→PASS)
```

---

## 에러 핸들링

원칙: **1회 재시도 후 재실패 시 결과 없이 진행하고 보고서에 누락 명시. 상충 데이터는 출처 병기.**

| 상황 | 대응 |
|------|------|
| analyzer가 산출물 미생성 | 1회 재실행. 재실패 시 "분석 실패 — 수동 분석 필요" 보고 후 중단 |
| analyzer가 인덱스 일부만 생성 | writer/validator/qa는 진행, 누락 인덱스에 의존하는 워크플로우 스킬은 "인덱스 누락" WARN |
| writer 일부 파일만 생성 | 누락 목록 보고. validator는 생성된 파일에만 검증. 누락 워크플로우 스킬 명시 |
| writer가 claude_md_fields.json 미생성 | skills_builder.py가 CLAUDE.md 조립 스킵. "CLAUDE.md 미생성 — writer 재실행 필요" WARN. 다른 항목(스킬·domain-expert.md)은 계속 배포 |
| writer가 writer_decisions.json 미생성 | skills_builder.py가 조건부 스킬·패턴 스켈레톤·02_writer_files.md 조립 전부 스킵. "writer 재실행 필요" WARN. CLAUDE.md·domain-expert.md·항상배포 스킬 3종은 계속 배포 |
| pattern-extractor 실패 | patterns/ 는 스켈레톤 상태 유지. "pattern-extractor 재실행 권고" 안내 |
| validator 보안 위험 발견 | 자동 수정 금지. 위치 명시, 사용자 직접 처리 |
| qa DEAD/ORPHAN 발견 | 자동 수정 금지. 우선순위 표시, 사용자 직접 처리 |
| validator 신뢰도 < 50 | qa 스킵. "validator 권고 우선 처리 후 재실행" 안내 |
| 작업 디렉토리 권한 오류 | 즉시 중단, 권한 확인 요청 |
| `_workspace/` 생성 실패 | 1회 재시도. 실패 시 중단 |
| spec-clarifier 실패 | Phase -1 스킵. "_workspace/00_spec_report.md 미생성" 기록 후 Phase 0 진행. analyzer는 코드에서 자동 탐지 |
| harness-evaluator 실패 | eval 없이 Phase 3 결과만 보고. "eval 미실행" 안내 |
| eval 재생성 후 점수 하락 | 재생성 결과 무시, 초기 harness 유지. 1차·2차 점수 모두 사용자에게 보고 |

상충 데이터: writer가 두 패턴 발견 시 출처 병기, validator/qa가 우선순위 권고 (자동 결정 X).

---

## 팀 통신 프로토콜

이 하네스는 `TeamCreate`/`SendMessage` 도구 없음. 대신:

| 채널 | 도구 | 용도 |
|------|------|------|
| 작업 조율 | `TaskCreate`/`TaskUpdate` | 진행 추적, 의존성 |
| 산출물 전달 | `_workspace/` 파일 | 분석 리포트·생성 파일·검증·인덱스 |

각 에이전트는 자기 `.md`에 명시된 입력 파일을 읽고 출력 파일을 작성. 오케스트레이터는 의존성 순서로 호출하고 산출물 존재 확인.


---
name: harness-init
description: 프로젝트를 심층 분석해 맞춤형 하네스(CLAUDE.md, 5+ 워크플로우 스킬, 도메인 에이전트, 패턴, 인덱스)를 자동 생성하는 오케스트레이터. "하네스 초기화", "하네스 만들어줘", "하네스 다시 초기화", "harness 다시 만들어줘", "프로젝트 분석해서 설정해줘", "이 프로젝트 Claude 설정해줘", "create harness", "initialize harness", "re-initialize harness", "generate project harness", "하네스 업데이트", "하네스 보완", "스킬만 다시 생성", "에이전트만 다시 생성", "validator만 다시 실행", "패턴 추출해줘", "pattern extract" 요청 시 사용. `.claude/skills/trace.md` 또는 `.claude/skills/analyze-impact.md`가 없으면 자동 트리거.
---

# Harness Initializer (Enhanced) — 팀 모드 오케스트레이터

프로젝트 코드베이스를 심층 분석해 *수정·개발·마이그레이션 작업까지 지원하는* 맞춤형 harness를 자동 생성한다.

기존 harness-new가 만들던 5종 + harness-fin이 추가하는 5종 + 인덱스 + 패턴까지 한 번에 생성.

**실행 모드:** 에이전트 팀 (TaskCreate 의존성 + `_workspace/` 파일 기반 산출물 전달)

**팀 구성 (확장):**
- 필수 파이프라인: analyzer → writer → validator
- 선택 추가: pattern-extractor (writer 직후, 패턴 채우기)
- 품질 루프: harness-evaluator (Phase 4)
- 기본 자동 실행 (Phase 3.6, 질문 없음): generate-wiki
- 온디맨드(자동 실행 안 함, Phase 3.7에서 선택 시만): qa

---

## Phase -1: 프로젝트 구성 확인

> **스킵 조건**: 아래 중 하나라도 해당하면 Phase 0으로 직행
> - `_workspace/00_init_scope.md` 이미 존재 (이전 구성 확인 완료)
> - 부분 재실행 ("스킬만"·"에이전트만"·"validator만" 등)
> - 재초기화 + "다시"만 있음 (추가 목표 변경 없음)
> - 사용자가 요청문에 구성과 경로를 이미 명시함 (`source: explicit-request`로 기록)

현재 작업 폴더 절대경로를 plain text로 먼저 출력한 뒤(`현재 작업 폴더: [절대경로]`), `AskUserQuestion`으로 2단계에 걸쳐 구성을 확인한다.

> **주의**: 전체 구성은 5가지인데 `AskUserQuestion` 툴은 한 질문에 옵션 최대 4개까지만 지원한다. 과거(2026-07-30) 5개를 한 질문에 담았다가 5번(허브형)이 조용히 잘려나간 실사고가 있었다 — 절대 5개를 한 질문에 넣지 않는다. 아래처럼 4개 이하씩 2단계로 나눈다. `AskUserQuestion` 툴 자체가 없는 호스트에서는 예전 방식(5지선다 평문 출력 + 자유 텍스트 응답 1~5)으로 폴백한다.

**1차 질문** (header: `초기화 구성`):

| 옵션 | 설명 |
|---|---|
| 단일 프로젝트로 초기화 (Recommended) | 지금 폴더 전체를 단일 프로젝트로 분석합니다 |
| 서버·클라이언트 함께 초기화 (모노레포) | 한 상위 폴더 안의 backend와 frontend/desktop/mobile을 워크스페이스로 통합 분석합니다 |
| 서버·클라이언트 각각 초기화 후 연결 (1:1) | 두 프로젝트를 독립적으로 초기화하고 양쪽 검증 후 pair-init으로 연결합니다 |
| 기타 (부분 범위 / 허브형 1:N) | 특정 폴더만 분석하거나, 백엔드 1개+클라이언트 여러 개 구조입니다 |

**2차 질문** (1차에서 "기타" 선택 시만, header: `세부 구성`):

| 옵션 | 설명 |
|---|---|
| 특정 폴더·모듈만 초기화 | 선택한 상대경로만 분석합니다 |
| 허브형 (1개 중심 + 클라이언트 여러 개, 1:N) | 예: 백엔드 1개 + 웹/모바일(iOS·Android)/관리자 등 클라이언트 2개 이상을 독립 초기화하고 연결합니다. 파트너가 정확히 1개면 1차 질문의 "1:1"을 쓴다 |

**응답별 분기:**

| 응답 | `init_layout` | 후속 확인 | 다음 단계 |
|------|------|---------|---------|
| 1차: 단일 | `single-root` | 없음 | Phase 0으로 진행 |
| 1차: 모노레포 | `monorepo` | root 내부 workspace 상대경로와 역할 | Phase 0으로 진행 |
| 1차: 1:1 | `paired-roots` | 파트너 정보 수집 (아래) | Phase 0으로 진행 |
| 1차: 기타 → 2차: 부분 범위 | `selected-paths` | root 내부 상대경로 | Phase 0으로 진행 |
| 1차: 기타 → 2차: 허브형 | `hub-roots` | 파트너 목록 수집 — N개 (아래) | Phase 0으로 진행 |
| 무응답·자유 텍스트로 판단 불가 | `single-root` (기본값) | 없음 | Phase 0으로 진행 |

휴리스틱으로 발견한 `server`/`backend`/`client`/`frontend`/`web`/`mobile` 후보는 경로 확인 표의 제안값으로만 쓰고 사용자의 구성 선택을 자동으로 바꾸지 않는다.

### 분리 저장소(`paired-roots`) 파트너 정보 수집

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

### 허브형(`hub-roots`) 파트너 목록 수집 (N개)

현재 프로젝트는 항상 hub(backend류) 역할로 취급한다 — hub-roots는 "1개 중심 + N개 클라이언트"
구조이기 때문이다 (현재 프로젝트가 클라이언트 중 하나라면 3번 `paired-roots`로 그 백엔드 하나와만
먼저 연결하거나, 백엔드 쪽 루트에서 harness-init을 실행하도록 안내).

```
클라이언트 프로젝트가 몇 개인가요? (2개 이상)
```

응답받은 개수만큼 아래 질문을 반복한다:

```
클라이언트 [i/N] 정보를 입력해주세요:

1. 역할 라벨 (예: web-frontend, mobile-ios, mobile-android, admin-panel — 자유 입력, 다른 클라이언트와 겹치지 않게)
2. 절대 경로:
3. API base URL (선택 — 로컬 개발 기준, 미입력 시 1번 클라이언트와 동일하다고 가정):
4. (선택) 스택 (예: React, Flutter, Swift — 모르면 빈칸)
```

수집한 정보를 `partner_list = [{ role_label, path, api_url, stack }, ...]` (N개 항목)에 저장.  
경로 유효성 확인 및 각 파트너 하네스 존재 여부는 pair-init Phase 1에서 (파트너별로 순회하며) 수행.

> 수집한 `partner_list`는 Phase 3.5에서 pair-init 자동 실행 시 컨텍스트로 전달된다.

### 출력

`_workspace/00_init_scope.md`를 일반 파일 쓰기로 기록한다.

```markdown
# 초기화 분석 범위

## 사용자 확인 내용
- 프로젝트 위치: `[절대경로]`
- 초기화 구성: 단일 | 모노레포 | 분리 저장소(1:1) | 부분 범위 | 허브형(1:N)
- 포함 경로: `[검증된 상대경로]`
- 대상 프로젝트: `[절대경로와 역할 목록, paired-roots만]`
- 클라이언트 목록: `[role_label·절대경로 목록, hub-roots만]`

## 기계 실행 값
- init_layout: single-root | monorepo | paired-roots | selected-paths | hub-roots
- paths: [검증된 상대경로]
- source: user-selection | explicit-request | reused
- tier: [Phase 0 Step 2.5에서 결정 후 추가 기록 — Phase -1 시점에는 비워 둠]
```

`monorepo`/`selected-paths`의 포함 경로는 root 내부 실제 디렉터리만 허용한다 (`..`, root 밖 절대경로 거부).

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

### Step 2.5: Tier 결정

**① 사용자 요청 override 먼저 확인:**

| 키워드 | Tier 강제 |
|--------|---------|
| "빠르게"·"간단히"·"빠른"·"quick"·"fast" | **Standard** |
| "깊게"·"심층"·"마이그레이션"·"레거시"·"전체"·"migration"·"legacy"·"deep" | **Full** |

> Lite Tier는 2026-07-23 폐지됨 — 인덱스 없는 하네스는 후속 스킬(analyze-impact 등)이 동작하지 않아 실효가 없었다. Tier는 Standard/Full 2단계만 존재하며 기본은 Full이다.

**② override 없으면 기본 Full + 1회 다운그레이드 확인:**

기본 Tier는 **Full**이다. 레거시 유지보수는 얕은 분석이 놓치는 위험(미해결 관계·인증 우회·트랜잭션 경계)이 재작업 비용보다 크다는 전제.

```
기본적으로 Full Tier로 초기화합니다.
- 비용: analyzer(opus) 1회 + writer(sonnet) 1회 (전체 심층 분석 포함)

더 빠르고 저렴한 Standard로 낮출까요? (기본값: Full 유지)
```

응답이 Standard 확인이면 Standard로, 그 외(N·무응답 등)면 Full 그대로 진행. 결정된 Tier는 `_workspace/00_init_scope.md`의 "기계 실행 값" 섹션에 `- tier: Standard | Full` 행으로 추가 기록한다(Phase -1에서 만든 파일에 이어 씀). 이 질문은 초기 실행/재초기화당 1회만 하며, 부분 재실행·인덱스 리프레시는 `00_init_scope.md`의 `tier:` 값을 재사용해 다시 묻지 않는다(값이 없으면 그때만 다시 묻는다).

**③ Tier별 실행 구성:**

| Tier | 실행 구성 | 스킵 항목 |
|------|---------|---------|
| **Standard** | analyzer(init/sonnet, 스택 해당 Phase B만) → writer(sonnet) → pattern(병렬) → validator | — |
| **Full** | 전체 파이프라인 (analyzer만 opus, writer 포함 나머지는 sonnet) | — |

QA는 Tier와 무관하게 두 Tier 모두 자동 실행에서 스킵되며, Phase 3.7 선택 작업 메뉴에서 사용자가 고를 때만 실행된다(위 표에는 포함하지 않음).

### Step 3: 실행 모드 분기

| 상황 | 모드 | 처리 |
|------|------|------|
| 기존 하네스 없음 | **초기 실행** | 전체 파이프라인 (analyzer init + writer + validator + pattern-extractor; qa는 Phase 3.7 선택 시만) |
| 기존 + "다시"·"새로" | **재초기화** | `.claude/backup/[YYYYMMDD-HHMMSS]/`로 백업 후 전체 실행 (analyzer init 모드) |
| 기존 + "스킬만"·"에이전트만"·"validator만"·"qa만"·"패턴만" | **부분 재실행** | 해당 단계만, 이전 `_workspace/` 산출물 재사용 |
| 기존 + 일반 보완 | **업데이트** | 백업 후 analyzer incremental + 재실행 |
| 기존 + "인덱스만 갱신해줘"·"인덱스만 다시"·"인덱스 리프레시" (코드 변경 후) | **인덱스 리프레시** | analyzer incremental만 (writer/validator/eval 스킵) |

백업 절차:
- PowerShell: `Get-Date -Format "yyyyMMdd-HHmmss"`
- 백업 대상: `CLAUDE.md`, `.claude/skills/*.md`, `.claude/agents/*.md` (공통 에이전트는 제외, 프로젝트 전용만), `.claude/patterns/`
- 백업 위치: `.claude/backup/[YYYYMMDD-HHMMSS]/`

### Step 4: 작업공간 준비

`_workspace/` 디렉토리:
- 초기 실행/재초기화: `_workspace/`를 `_workspace_prev/`로 이동 후 새로 생성
- 부분 재실행: 기존 유지

산출물 파일명:
```
_workspace/00_init_scope.md           ← 구성 확인 (Phase -1)
_workspace/01_analyzer_report.md      ← analyzer
_workspace/02_writer_files.md         ← writer
_workspace/03_validator_report.md     ← validator
_workspace/04_qa_report.md            ← qa
_workspace/05_patterns_extracted.md   ← pattern-extractor
_workspace/06_eval_report.md          ← harness-evaluator (Phase 4)
_workspace/index/*.json               ← analyzer (인덱스)
_workspace/ai-budget.json             ← ai-budget.mjs (2-0.5 Step F)
_workspace/validator_schema.json      ← validate-harness.mjs (2-4)
```

`ai_budget_session` 값을 이 단계에서 한 번 생성한다 — `now_kst.py` 결과에 `init-` 접두사를 붙인 문자열(예: `init-2026-08-12-143000`). `00_init_scope.md`의 "기계 실행 값"에 `tier:`와 나란히 `- ai_budget_session: [값]` 행으로 추가 기록하고, 부분 재실행·인덱스 리프레시는 이미 기록된 값을 재사용한다(재초기화 시 예산이 조용히 리셋되는 것을 막기 위함 — `ai-budget.mjs init`은 같은 session이면 멱등).

---

## Phase 1: 공유 작업 계획

`TaskCreate`로 팀원별 작업 + 의존성 설정 (Tier에 따라 생성 작업 다름):

**Standard/Full 공통:**
```
T-A (analyzer):          → _workspace/01_analyzer_report.md + _workspace/index/*.json
T-W (writer):            → _workspace/02_writer_files.md           (blockedBy: T-A)
T-V (validator):         → _workspace/03_validator_report.md       (blockedBy: T-W)
T-P (pattern-extractor): → _workspace/05_patterns_extracted.md     (blockedBy: T-W)
T-E (harness-eval):      → _workspace/06_eval_report.md            (blockedBy: T-V)
```
T-P는 T-W 완료 후 T-V/T-E와 병렬 실행 가능.

QA(`T-Q`)는 Tier와 무관하게 이 초기 작업 그래프에 포함하지 않는다 — Phase 3.7의 선택 작업 메뉴에서 사용자가 고를 때만 온디맨드로 실행한다(토큰 절감).

`TaskCreate`가 있으면 위 작업 ID와 한글 설명을 **함께 포함한 제목 그대로** 작업을 생성한다(예: `T-A · analyzer · 프로젝트 구조·의존성·레거시 로직 분석`). 아래 Phase 2의 모든 `Agent()` 호출은 `subagent_type="general-purpose"`를 쓰므로, 호스트 진행 화면에는 기본적으로 `general-purpose`만 노출된다 — 이를 보완하기 위해 각 호출의 `description` 필드에 반드시 `[task-id] · [실제 에이전트 이름] · 한글 목적`을 그대로 넣어 어떤 단계가 실행 중인지 사용자에게 드러낸다. `TaskCreate`가 없는 호스트에서는 `_workspace/00_pipeline_status.md` 체크리스트로 폴백하며 같은 제목을 사용한다.

보완·재검증 작업 제목은 원래 단계 ID를 보존한다.

- `T-A-RETRY · analyzer · 누락된 분석 근거 보완`
- `T-W-RETRY · writer · 누락된 하네스 파일·패턴 보완`
- `T-V-RECHECK · validator · 보완된 초기화 결과 재검증`

---

## Phase 2: 팀원 실행

### 2-0.5. 결정론적 전수 인덱싱 (LLM 미사용)

analyzer 호출 전에 실행. `_workspace/01_analyzer_report.md`가 이미 있어 2-1을 스킵하는 경우 이 단계도 함께 스킵.

**Step A — 실행 환경 확인**

```powershell
node --version
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/stack_precheck.py" --root "[절대경로]"
```

`node`가 exit 0이고 major 버전이 18 이상이면 결정론적 인덱서를 쓴다. `stack_precheck.py`는 어느 쪽이든 항상 실행한다 — 감지된 스택(`detected_stack`)이 validator의 DI 휴리스틱과 아래 폴백 선택에 쓰이고 비용이 거의 없다.

**Step B — `_workspace/indexer-config.json` 작성**

`_workspace/00_init_scope.md`의 값을 그대로 옮긴다(판단 없는 기계 변환).

```json
{"init_layout": "single-root", "include_paths": ["."], "workspace_mode": false,
 "workspaces": [{"id": "root", "path": "", "kind": "unknown", "stack": "unknown"}]}
```

- `selected-paths`면 선택한 상대경로들을 `include_paths`에 넣는다 (인덱서가 그 밖의 소스는 읽지 않는다).
- 모노레포면 모듈마다 `workspaces[]` 항목을 하나씩 두고 `stack`은 `00_stack_precheck.json`의 값을 쓴다.

**Step C — 인덱싱**

```powershell
node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/build-index.mjs" --root "[절대경로]" --mode init --tier "[Standard|Full]" --config "_workspace/indexer-config.json"
```

`_workspace/index/`에 `symbols`·`call_graph`·`sql_usage`·`transactions`·`external_io`·`env_branches`·`schema`·`api_contract`·`dead_code`(해당 사실이 있는 것만) + `_meta.json`·`_analysis_input.json`·`_unresolved.jsonl`을 생성한다. `_workspace/.index-cache/`에 파일 해시 기반 캐시가 남아 이후 `--mode incremental`이 변경분만 다시 읽는다.

기존 인덱스의 `_meta.generator`가 `deterministic-indexer`가 아니면 `--mode incremental` 대신 **`--mode init`을 강제**한다. 생성기마다 노드 id 체계가 달라 섞이면 한 파일에 두 개의 id 네임스페이스가 생긴다.

**Step D — Vue 보강 (해당 시)**

`00_stack_precheck.json`의 `extractors`에 `vue`가 있으면 이어서 실행한다.

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/index_extractor_vue.py" --root "[절대경로]"
```

인덱서는 `.vue`를 JS로만 읽어 컴포넌트·Pinia 스토어 노드와 `import`·`inject` 엣지를 만들지 않는다(그러면 wiki-hub의 화면 목록이 빈다). 이 스크립트가 그 부분만 얹는다 — 노드는 id 기준으로 중복 제거되므로 인덱서 결과를 덮어쓰지 않는다.

**Step E — 폴백 사다리**

| 순위 | 조건 | 실행 |
|---|---|---|
| 1 | node ≥ 18 | `build-index.mjs` (비정상 종료 시 1회 재시도 — 모든 출력이 원자적 쓰기라 반쪽 파일이 남지 않는다) |
| 2 | node 없음 또는 2회 실패 | `00_stack_precheck.json`의 `extractors`를 순회하며 스택별 Python 추출기를 **차례로** 실행 (`java_spring`→`index_extractor_java_spring.py`, `csharp_dotnet`→`_csharp.py`, `python_web`→`_python.py`, `vue`→`_vue.py`, `kotlin_android`→`_kotlin.py`). 이 경로는 `symbols.json`·`call_graph.json`만 만든다 |
| 3 | 감지 스택 없음 또는 2도 실패 | 2-1의 analyzer가 인덱스를 처음부터 전부 작성 (기존 동작, 회귀 없음) |

어느 순위로 실행됐는지 `_workspace/00_stack_precheck.json`에 `indexer` 키로 기록하고 Phase 3 보고에 포함한다 — 성능이 떨어진 채 넘어간 실행이 조용히 묻히지 않게 한다.

> analyzer가 계속 직접 작성하는 인덱스는 `owasp_top10.json`·`data_flow.json`·`client_index.json` 3종이다. 인덱서는 이 파일들을 만들지도 지우지도 않는다.

**Step F — AI 호출 예산 초기화**

node ≥ 18일 때만 (Step A 프로브 결과 재사용):

```powershell
node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/ai-budget.mjs" init --root "[절대경로]" --session "[ai_budget_session]" --initial 3 --retries 2
```

`--initial 3`은 analyzer+writer+pattern-extractor(Lite 폐지로 Tier 무관 항상 3역할), `--retries 2`는 Phase 4 한 라운드가 `T-A-RETRY`+`T-W-RETRY`를 동시에 낼 수 있어서다(upstream 원본의 1로는 부족). 이후 2-1/2-2/2-3의 각 `Agent()` 호출 직전과 Phase 4의 각 재실행 직전에 `claim`을 거쳐야 한다 — `claim`이 실패(exit 1)하면 그 `Agent()` 호출을 하지 않고 레인을 중단한다(예산 소진은 이 저장소의 일반적인 "WARN 후 계속" 관례의 예외 — 하드 스톱이 의도다).

node 없으면 이 Step 전체를 스킵하고 `_workspace/00_stack_precheck.json`에 "AI 예산 강제 미적용(node 없음)"으로 기록한다(기존 폴백 표시 관례와 동일) — 그 경우 2-1/2-2/2-3/Phase 4의 `claim` 호출도 전부 생략하고 오늘처럼 무제한 진행한다.

### 2-1. analyzer 호출

부분 재실행 + `_workspace/01_analyzer_report.md` 존재 시 스킵.

Tier별 mode/model 결정:
| Tier / 상황 | mode | model |
|------|------|-------|
| Standard | `init` (A + 스택 해당 Phase B만) | sonnet |
| Full | `init` (A + B 전체) | opus |
| 업데이트·인덱스 리프레시 (Step 3 표) | `incremental` (변경 파일만 재분석 + stale 엣지 무효화) | sonnet (Tier 무관) |

AI 예산이 초기화됐으면(Step F) claim 먼저:
```powershell
node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/ai-budget.mjs" claim --root "[절대경로]" --session "[ai_budget_session]" --role analyzer --kind initial
```
(exit 1이면 이 Agent 호출을 하지 않고 레인 중단 — Step F 참조)

```
Agent(
  subagent_type="general-purpose",
  description="T-A · analyzer · 프로젝트 구조·의존성·레거시 로직 분석",
  prompt="<analyzer 에이전트 지침에 따라 분석. 프로젝트 루트: [절대경로]. mode: init. tier: [Standard/Full].
  init_layout/paths: _workspace/00_init_scope.md 참조 (selected-paths면 해당 상대경로만 분석).
  2-0.5가 인덱스를 기계 생성했으면(_workspace/index/_meta.json 존재) 그 파일들 재작성 금지 —
  _analysis_input.json을 읽고 _unresolved.jsonl을 계약대로 처리해 _ai_patch.json만 출력한다
  (analyzer.md Step 8 '기계 인덱스가 있을 때' 분기). _meta.json이 없으면 기존대로 직접 작성.
  결과: _workspace/01_analyzer_report.md + (기계 인덱스 없을 때만) _workspace/index/*.json>",
  model="[sonnet/opus]"
)
```

`.claude/agents/analyzer.md`의 지침 따름. 완료 후 결과 파일 존재 확인.

### 2-1.5. AI 보강 patch 병합 (기계 인덱스가 있을 때만)

`_workspace/index/_ai_patch.json`이 있으면 실행한다.

```powershell
node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/build-index.mjs" --root "[절대경로]" --apply-ai-patch "_workspace/index/_ai_patch.json"
```

기존 노드 사이의 엣지만 추가되고, 없는 노드를 참조하는 operation은 사유와 함께 거부된다. 전부 거부되면 비정상 종료하므로 **WARN으로 보고하고 계속 진행**한다(인덱스 자체는 유효하고 보강만 안 된 상태다). 병합 결과는 `_meta.json`의 `ai_enrichment`에 남는다.

analyzer가 `call_graph.json`을 직접 고치지 않고 patch로 내는 이유는 재인덱싱 때문이다. `--mode incremental`은 캐시에서 그래프를 다시 만들므로, 손으로 덧붙인 엣지는 다음 "인덱스만 갱신" 실행에서 **에러 없이 사라진다**. patch는 파일을 쓰기 전에 다시 병합되고 데드 코드도 그에 맞춰 재계산된다.

### 2-2. writer 호출

`_workspace/01_analyzer_report.md` 존재 확인 후.

model: 모든 Tier에서 sonnet (2026-07-14 하이브리드 빌더 도입으로 writer 작업이 스킬 3종 + JSON 2개로 줄어 opus 불필요 — 2026-07-23 변경).

AI 예산이 초기화됐으면 claim 먼저: `node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/ai-budget.mjs" claim --root "[절대경로]" --session "[ai_budget_session]" --role writer --kind initial` (exit 1이면 중단).

```
Agent(
  subagent_type="general-purpose",
  description="T-W · writer · 하네스 파일과 프로젝트 가이드 생성",
  prompt="<writer 에이전트 지침에 따라 하네스 파일 작성. 프로젝트 루트: [절대경로]. tier: [Standard/Full]. 입력: _workspace/01_analyzer_report.md + _workspace/index/*.json (필요 시). 출력: 하네스 파일들(trace/scaffolder/find-logic, cross-repo-* 있는 경우) + _workspace/claude_md_fields.json + _workspace/writer_decisions.json>",
  model="sonnet"
)
```

> writer는 trace.md·scaffolder.md·find-logic.md만 markdown으로 직접 작성한다 (pair_config.md 있으면 cross-repo-scaffold.md·cross-repo-modify.md도). CLAUDE.md는 `_workspace/claude_md_fields.json`에 필드(프로젝트명·한줄설명·스택요약·요청흐름·파일위치표 행·빌드명령·주의사항)만, patterns 스켈레톤·02_writer_files.md는 `_workspace/writer_decisions.json`에 결정 값(조건부 스킬 생성 여부+사유, 패턴 파일명 목록, 탐지 스택, 적용 결정 사유)만 채워서 낸다. domain-expert.md(analyzer_report 그대로 주입)와 analyze-impact.md·safe-modify.md·scaffold-feature.md·plan-migration.md·review-sql.md(정적 텍스트)·patterns 스켈레톤·02_writer_files.md는 writer가 쓰지 않고 다음 단계(2-2.3)에서 배포한다.

### 2-2.3. skills_builder.py 실행 (CLAUDE.md + 정적 워크플로우 스킬 + domain-expert.md + 패턴 스켈레톤 + 02_writer_files.md 배포)

writer 완료 후 다음을 전부 처리한다 (LLM 호출 없음, 전부 결정론적 파일 조립/복사):
- `_workspace/claude_md_fields.json` + `agents/lib/claude_md.md.template`(고정 골격) → `CLAUDE.md` 조립. `pair_config.md` 있으면 "파트너 프로젝트" 섹션도 그 필드값으로 자동 채움
- `_workspace/writer_decisions.json`의 생성 여부 판단을 읽어 정적 스킬 템플릿(`agents/lib/skills/*.md.template`)을 대상 프로젝트 `.claude/skills/`에 복사 (analyze-impact/safe-modify/scaffold-feature는 항상, plan-migration/review-sql은 조건 충족 시만)
- `_workspace/01_analyzer_report.md`를 그대로 복사해 `.claude/agents/domain-expert.md` 생성
- `writer_decisions.json`의 `pattern_files` 목록(+ "LegacyStaticJS" 탐지 시 client_pattern.md 자동 추가)으로 `.claude/patterns/*.md` 스켈레톤 생성 (이미 pattern-extractor가 채운 파일은 덮어쓰지 않음)
- `agents/lib/ito_guide.md.template` + 배포된 스킬들의 frontmatter + `claude_md_fields.json`/`writer_decisions.json` 값으로 `.claude/ito-guide.md` 사용 설명서 조립 (시나리오는 배포 스킬 조합 규칙 기반)
- 위 모든 결과 + `writer_decisions.json`을 조합해 `_workspace/02_writer_files.md` 조립

> **스크립트 경로 규칙 (이 스킬의 모든 `agents/lib/*.py` 호출 공통)**: 스크립트는 대상 프로젝트가 아니라 *플러그인 설치 루트*에 있다. PowerShell은 `$env:CLAUDE_PLUGIN_ROOT`, bash는 `$CLAUDE_PLUGIN_ROOT`로 참조한다. 환경변수가 비어 있으면 이 SKILL.md가 위치한 플러그인 디렉터리(예: `~/.claude/plugins/cache/ax-std-harness/...`)의 절대경로로 대체한다. cwd 기준 상대경로 `agents/lib/...`는 개발 저장소에서만 동작하므로 금지. `--out`/`--summary` 인자는 생략한다 — 스크립트 기본값이 `--root` 기준 경로라, cwd ≠ root인 상황(파트너 하네스 자동 생성 등)에서 상대경로 인자를 넘기면 엉뚱한 프로젝트에 읽기/쓰기가 발생한다.

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/skills_builder.py" --root "[절대경로]"
```

실패 시(python 미설치, claude_md_fields.json/writer_decisions.json 누락 등) 1회만 재시도하고, 그래도 실패하면 "CLAUDE.md/정적 스킬/domain-expert.md/패턴 스켈레톤/02_writer_files.md 배포 실패 — writer 재실행 또는 수동 작성 필요" WARN 후 계속 진행 (개별 항목은 부분적으로 성공할 수 있음 — 스크립트가 항목별로 독립 처리).

### 2-2.5. ito-guide.md (2-2.3에 통합 — 별도 Agent 호출 없음)

`.claude/ito-guide.md`는 2-2.3의 skills_builder.py가 `agents/lib/ito_guide.md.template`로 기계 조립한다(zero-LLM) — 전 항목이 이미 있는 산출물(스킬 frontmatter·claude_md_fields·writer_decisions·pair_config)의 재진술이라 LLM 작성이 불필요했다 (2026-07-23 전환, 이전에는 매 초기화마다 sonnet ~5K 토큰 소비). 2-2.3 실행 후 `.claude/ito-guide.md` 존재만 확인하고, 없으면 "ito-guide 미생성" WARN 후 계속 진행.

### 2-3. pattern-extractor 호출 (병렬 가능)

2-2.3(skills_builder.py)이 patterns/ 스켈레톤을 생성한 뒤에만 호출한다 — 스켈레톤은 writer(2-2)가 아니라 skills_builder.py(2-2.3)의 산출물이므로, T-P를 TaskCreate 의존성만으로 착수시키지 말고 2-2.3 완료를 확인하고 시작한다.

AI 예산이 초기화됐으면 claim 먼저: `node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/ai-budget.mjs" claim --root "[절대경로]" --session "[ai_budget_session]" --role pattern-extractor --kind initial` (exit 1이면 중단).

```
Agent(
  subagent_type="general-purpose",
  description="T-P · pattern-extractor · 레이어별 컨벤션 패턴 추출",
  prompt="<pattern-extractor 에이전트 지침. 프로젝트 루트: [절대경로]. 입력: .claude/patterns/*.md 스켈레톤 + _workspace/01_analyzer_report.md. 출력: 패턴 파일 본문 + _workspace/05_patterns_extracted.md>",
  model="sonnet"
)
```

### 2-4. validator 호출

모든 Tier에서 실행. `_workspace/02_writer_files.md` 확인 후, validator Agent() 호출 전에 기계 체크를
먼저 실행 (LLM 미사용 — validator 체크 1,2,3,4,6,7,8,9를 대신 계산):

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/validator_checks.py" --root "[절대경로]"
```

(출력은 기본값 `[root]/_workspace/validator_mechanical.json` — 경로 규칙은 2-2.3 참조.)

실패 시(python 미설치 등) WARN 후 계속 진행 — validator가 해당 체크를 직접 수행하는 기존 방식으로 폴백.

node ≥ 18일 때 이어서(node 없으면 스킵, WARN 후 계속):

```powershell
node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/validate-harness.mjs" --root "[절대경로]" --plugin-root "$env:CLAUDE_PLUGIN_ROOT" --tier "[Standard|Full]" --out "_workspace/validator_schema.json"
```

`_workspace/index/*.json`을 `docs/index-schema/*.json` 대조로 스키마 검증한다 — `validator_checks.py`의 check7/7b(내용 정확성, 실제 소스 대조)와 겹치지 않는 별개 층(형태 검증)이라 병행 실행한다. exit 1이면 스키마 FAIL이 있다는 뜻이지 스크립트 실패가 아니다(`_out` 파일은 정상적으로 쓰여진다) — Phase 4의 인덱스 무결성 게이트가 이 결과를 읽는다.

```
Agent(
  subagent_type="general-purpose",
  description="T-V · validator · 하네스 구조와 근거 검증",
  prompt="<validator 에이전트 지침. 프로젝트 루트: [절대경로]. tier: [Standard/Full]. 입력: _workspace/01_analyzer_report.md, _workspace/02_writer_files.md, _workspace/validator_mechanical.json(있으면), _workspace/validator_schema.json(있으면), (있으면) _workspace/index/. 출력: _workspace/03_validator_report.md>",
  model="sonnet"
)
```

> QA(경계면 교차 비교)는 더 이상 Phase 2에서 자동 실행하지 않는다. Agent 호출 방법은 Phase 3.7 "선택 작업 안내"에서 사용자가 선택했을 때만 참조한다 — 토큰 절감을 위해 Tier와 무관하게 항상 온디맨드다.

### 2-5. harness-evaluator 호출 (모든 Tier)

validator 완료 후 실행:

```
Agent(
  subagent_type="general-purpose",
  description="T-E · harness-evaluator · harness 품질 평가",
  prompt="<harness-evaluator 에이전트 지침에 따라 생성된 harness 파일들의 품질을 평가한다.
  프로젝트 루트: [절대경로]. tier: [Standard/Full].
  입력: _workspace/01_analyzer_report.md, _workspace/03_validator_report.md,
        생성된 harness 파일들 (CLAUDE.md, .claude/skills/, .claude/agents/, .claude/patterns/).
  출력: _workspace/06_eval_report.md>",
  model="sonnet"
)
```

---

## Phase 3: 결과 종합 및 보고

`_workspace/03_validator_report.md`, `_workspace/05_patterns_extracted.md`(있으면), `_workspace/04_qa_report.md`(있으면, 선택 작업에서 이미 실행한 경우만)를 읽어 사용자에게 다음 형식으로 보고:

```
하네스 초기화 완료 (harness-fin v1) [Tier: Standard/Full]

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
- _workspace/index/owasp_top10.json         (Security 설정 탐지 시)

구조 검증 (validator):
[신뢰도 점수 + 보완 권장 항목]
[validator_schema.json 있으면: 인덱스 스키마 검증 PASS/WARN/FAIL, plugin_contract_failures 있으면 "플러그인 인덱스 계약 결함" 별도 표기]

AI 예산 증적 (ai-budget.json 있으면): [session] · initial [used]/[limit] · retries [used]/[limit]

패턴 추출 (pattern-extractor):
- 처리한 패턴 파일: N개
- 신뢰도: [HIGH: A, MEDIUM: B, LOW: C]
- 안티패턴 발견: K건

Eval 품질 점수 (harness-evaluator):
[점수: N/100 — PASS / PARTIAL / RETRY]
- 커버리지: /25 | 정확도: /25 | 실행가능성: /25 | 컨텍스트 품질: /25
(PARTIAL/RETRY이면 → Phase 4 재생성 실행 후 최종 점수 업데이트)
(인덱스 무결성 기계 게이트가 걸렸으면 → PASS여도 analyzer 재실행 1회 진행, 결과·잔존 이슈 여부 여기 표시)

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

**Phase -1 결과 및 기존 설정 기반 분기:**

| 조건 | 동작 |
|------|------|
| `init_layout = "single-root"`, `"monorepo"`, `"selected-paths"` | 이 Phase 전체 스킵 → Phase 3.6으로 |
| `_workspace/pair_config.md` 이미 있음 | 이 Phase 전체 스킵 → Phase 3.6으로 |
| `init_layout = "paired-roots"` + `partner_info` 수집됨 | pair-init 자동 실행 (사용자 확인 생략) → Phase 3.6으로 |
| `init_layout = "hub-roots"` + `partner_list`(N개) 수집됨 | pair-init 자동 실행, `partner_list` 전체를 한 번에 전달 (사용자 확인 생략) → Phase 3.6으로 |
| Phase -1 스킵 + `pair_config.md` 없음 | 연동 여부 질문 후 진행 |

### pair-init 자동 실행 — 1:1 (`paired-roots` + 파트너 정보 있는 경우)

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

### pair-init 자동 실행 — 1:N (`hub-roots` + 파트너 목록 있는 경우)

```
[Phase 3.5] pair-init 시작 — 클라이언트 N개 연동 중
클라이언트: [role_label 목록]
```

pair-init 스킬을 다음 컨텍스트로 실행:
- 현재 프로젝트 역할: `backend` (hub-roots는 항상 현재 프로젝트=hub 전제, Phase -1 참조)
- 파트너 목록: `partner_list`(N개, 각 `{ role_label, path, api_url, stack }`) 전체를 한 번에 전달
- pair-init이 파트너별로 순회하며 경로 확인·하네스 존재 확인·`pair_config.md` 생성(hub 쪽은 다중 블록, 각 클라이언트 쪽은 기존 1:1 형식 그대로)을 수행

### 파트너 하네스 없는 경우 — 자동 생성 (harness-init 주도 흐름 한정)

pair-init Phase 1에서 파트너 `CLAUDE.md`가 없어 3지선다가 뜨는 경우, **harness-init이 이미 멀티레포 의도를 확인한 상태**이므로 사용자에게 다시 묻지 않고 선택지 1(자동 생성)을 기본 적용한다. `hub-roots`는 하네스 없는 클라이언트마다 각각 적용한다(클라이언트별로 독립 판단 — 일부는 이미 하네스가 있고 일부는 없을 수 있음).

pair-init이 실행하는 "파트너 하네스 자동 생성" Agent 호출(파트너 루트에서 harness-init 재실행)은 아래처럼 **이번 턴의 Phase 4(harness-evaluator) 호출과 같은 메시지에서 병렬로 발행**한다 — 모든 작업이 서로 독립적인 대상(각 파트너 프로젝트 / 현재 프로젝트)이므로 동시 실행 가능. `hub-roots`에서 하네스 없는 클라이언트가 M개면 M개의 파트너 초기화 subagent를 전부 이 병렬 묶음에 포함한다(순차 실행 금지 — N이 늘어나도 총 대기 시간은 가장 느린 1개 기준):

```
[같은 메시지 — 병렬 Agent 호출 (1 + M)건]
1) harness-evaluator (Phase 4, 대상: 현재 프로젝트 _workspace/)
2..1+M) 파트너 하네스 자동 생성 subagent × M (pair-init 내부 호출, 대상: 하네스 없는 각 클라이언트 루트)
```

모든 호출이 반환되면 다음으로 진행. 파트너 초기화가 evaluator보다 오래 걸리면, 현재 프로젝트의 Phase 4 결과 보고를 먼저 사용자에게 보여주고 "파트너 하네스 생성 중... (M개 중 완료: k)" 안내 후 전체 완료를 기다린다 (join).

> 파트너 초기화 subagent가 실패해도 현재 프로젝트 파이프라인은 막지 않는다 — WARN 기록 후 Phase 3.6에서 통합 wiki 대신 단독 wiki 제안으로 폴백.

### 연동 여부 질문 방식 (Phase -1 스킵 + pair_config.md 없는 경우)

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
| 무응답·다른 주제로 전환 | N과 동일 처리 (기본값: 연동 안 함) → Phase 3.6으로 |

---

## Phase 3.6: 위키 생성 (기본 실행, 질문 없음)

2026-07-31부터 wiki 생성은 온디맨드가 아니라 **기본 자동 실행**이다 — QA와 달리 매번 질문하지
않고 바로 진행한다(사용자가 "위키 생성을 기본으로 해달라"고 명시적으로 요청).

`generate-wiki` 스킬의 Phase 0~3.5을 그대로 수행한다. Phase 0의 "사전 확인"은 harness-init이
방금 완료했으므로 존재 확인은 스킵. `pair_config.md`가 있으면 `wiki_generator.py`가 파트너의
call_graph.json·01_analyzer_report.md·api_contract.json·schema.json·external_io.json을
함께 읽어 architecture/api-endpoints/database/external-systems 페이지에 자동 병합한다.

`generate-wiki` 자체의 Phase 3.5("중앙 DB에도 발행할까요? Y/N")는 그대로 질문한다 — 이건
wiki 생성 여부와 별개의 선택이라 자동화하지 않는다. DB 저장은 harness에 내장된
`agents/lib/wikihub_db/`가 처리하므로 별도 프로젝트 wiki-hub 설치 여부와 무관하게 항상 가능하다.

wiki 생성이 실패해도(예: `_workspace/01_analyzer_report.md` 없음 등 이례적 상황) harness-init
자체를 막지 않는다 — WARN 후 Phase 3.7로 계속 진행.

---

## Phase 3.7: 선택 작업 안내 (QA)

Phase 3.6(wiki) 직후, 기본 파이프라인에 포함되지 않는 QA(경계면 교차 비교)를 놓치지 않도록 제시하고 선택받는다. 온디맨드이며 선택하지 않으면 실행하지 않는다(토큰 절감).

> Phase 3.5(파트너 연동 질문)·Phase 3.6(wiki, 질문 없음)·Phase 3.7(이 QA 메뉴)은 **순서대로** 제시한다.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
초기화·위키 생성은 끝났지만, 아래는 아직 실행하지 않은 선택 작업입니다.

  1. 경계 QA   — writer 주장(패턴·컨벤션)이 실제 코드·인덱스와 일치하는지 교차검증합니다
  2. 지금 안 함 — 나중에 "경계 QA 실행해줘"로 개별 호출 가능

실행할까요? (1/2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

`_workspace/03_validator_report.md` 신뢰도 < 50이면 "1. 경계 QA" 항목에 "— 구조 검증 실패로 결과 없이 종료됨" 주석을 붙여 표시한다(선택해도 미실행 사유만 기록).

### QA 선택 시

Agent() 호출 전에 Boundary 6 기계 체크를 먼저 실행(LLM 미사용):

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/qa_boundary6.py" --root "[절대경로]"
```

(출력은 기본값 `[root]/_workspace/qa_boundary6.md` — 경로 규칙은 2-2.3 참조.)

실패 시 WARN 후 계속 진행 — qa가 Boundary 6을 직접 확인하는 기존 방식으로 폴백.

```
Agent(
  subagent_type="general-purpose",
  description="T-Q · qa · 경계면 교차 비교 검증",
  prompt="<qa 에이전트 지침. 프로젝트 루트: [절대경로]. 입력: _workspace/01~03 + _workspace/qa_boundary6.md(있으면) + _workspace/index/. 출력: _workspace/04_qa_report.md>",
  model="sonnet"
)
```

신뢰도 < 50이면 이 Agent 호출 대신 "구조 검증 실패로 미실행" 한 줄만 `_workspace/04_qa_report.md`에 작성.

선택 시 완료 후 Phase 3와 같은 형식으로 결과를 사용자에게 보고한다. "지금 안 함"·무응답·다른 대화 주제로 넘어가면 QA는 실행하지 않고 Phase 4로 진행한다.

---

## Phase 4: Eval Loop — Karpathy AutoResearch 영감

1차 평가(harness-evaluator)는 Phase 2-5에서 모든 Tier가 항상 실행한다 — 이 Phase는 그 결과(`_workspace/06_eval_report.md`)의 총점을 읽어 **점수 기반 재생성 루프만** 담당한다(evaluator 실패로 파일이 없으면 에러 핸들링 표에 따라 eval 없이 Phase 3 보고로 종료). Phase 3.5에서 파트너 하네스 자동 생성 subagent와 evaluator를 병렬 발행한 경우, 이 Phase의 재생성·재평가는 두 호출이 모두 join된 뒤 시작한다.

### 인덱스 무결성 기계 게이트 (점수와 무관하게 우선 적용)

harness-evaluator의 4개 차원은 harness *파일*이 인덱스를 "참조하는지"만 보고(실행가능성 검증 방법 3) 인덱스 *내용*(call_graph dangling edge, `_meta` 누락, edge 종류 누락)은 채점하지 않는다 — 그래서 qualitative 점수가 80 이상(PASS)이어도 인덱스가 구조적으로 결함 있는 채 그대로 통과될 수 있다(2026-07-31 실제 사례 3건에서 확인됨). 이를 막기 위해 harness-evaluator의 점수 해석보다 먼저, 결정론적으로 다음을 확인한다.

`_workspace/validator_mechanical.json`을 읽어 아래 중 하나라도 해당하면(2-4에서 이미 생성됨, 다시 실행할 필요 없음):

- `index_integrity_fail == true`
- `index_spotcheck_fail == true`
- `warns` 배열에 "analyzer.md Step 8 참고" 문구가 포함된 항목 1개 이상 (call_graph 추출 누락 의심 휴리스틱 — import/inherit/inject 편중 감지)
- `warns` 배열에 "generated_at" 문구가 포함된 항목 1개 이상 (실제 시각 미조회 의심)

`_workspace/validator_schema.json`(있으면, 2-4에서 이미 생성됨)도 함께 확인한다:

- `failures > 0 && plugin_contract_failures === 0` — 스키마 FAIL이 있고 원인이 플러그인 계약 결함이 아니면 위와 같은 방식으로 analyzer 재실행 대상.
- `plugin_contract_failures > 0` — **AI로 재시도하지 않는다.** `checks` 중 `code === "PLUGIN_INDEX_CONTRACT"`인 항목은 `build-index.mjs`/`docs/index-schema/*.json` 자체의 계약 결함(analyzer나 프로젝트 소스 문제가 아님)이다. Phase 3 보고에 "플러그인 인덱스 계약 결함 — build-index.mjs/docs/index-schema 확인 필요"로 그대로 명시하고 fix_targets에 추가하지 않는다.

위 중 하나라도 해당하면(`plugin_contract_failures` 단독 제외), harness-evaluator 점수가 PASS여도 **`analyzer` 강제 재실행**을 fix_targets에 추가한다 — task-id `T-A-RETRY`, scope는 `report_fragments["7"]`(및 해당 warn 라인, 있으면 `validator_schema.json`의 FAIL 메시지도 포함) 원문 그대로, instruction은 "다음 기계 검증 결과의 FAIL/WARN 항목을 전부 해소하라(analyzer.md '작성 후 자체 검증' 절 기준으로 dangling 0건·`_meta` 9필드·edge 종류 완전성을 스스로 재확인할 것): [report_fragments['7'] 및 관련 warn 원문 + validator_schema.json FAIL 메시지]". harness-evaluator가 이미 `analyzer` fix_target을 반환했으면 이 게이트의 scope/instruction을 그 행에 병합하고, 없으면 새 행을 추가한다(행 자체는 하나만 — 같은 회차에 analyzer를 두 번 부르지 않는다).

이 게이트로 추가된 analyzer 재실행도 아래 "타겟 재생성 실행"과 같은 흐름으로 한 번에 처리한다 — PASS인데 이 게이트만 걸린 경우에도 재생성 1회 + harness-evaluator 재평가 1회는 그대로 실행한다(무한 루프 없음, 아래와 동일).

analyzer 재실행 완료 후 `validator_checks.py`를 1회 재실행해 게이트가 해소됐는지 확인한다. 해소 안 되면(2026-07-31 에러 핸들링 원칙과 동일 — 1회 재시도 후 재실패 시 결과 명시) 추가 재시도 없이 Phase 3 보고에 "인덱스 무결성 잔존 이슈"로 남은 FAIL/WARN을 그대로 명시하고 진행한다.

### 점수별 동작

| 총점 | 결정 | 동작 |
|------|------|------|
| 80~100 (PASS) | 완료 | Phase 3 보고 그대로 사용자에게 전달 |
| 60~79 (PARTIAL) | 타겟 재생성 | fix_targets 기반 특정 에이전트 재실행 → 재평가 (1회) |
| 0~59 (RETRY) | 주요 재생성 | fix_targets 상위 2개 에이전트 재실행 → 재평가 (1회) |

### 타겟 재생성 실행 (PARTIAL/RETRY, 또는 PASS여도 위 기계 게이트가 걸린 경우)

`_workspace/06_eval_report.md`의 fix_targets(+ 기계 게이트가 추가/병합한 analyzer 행)를 읽어 각 에이전트 재실행. fix_target.agent는 `analyzer` 또는 `writer`만 반환된다 — task-id는 `analyzer→T-A`, `writer→T-W` 매핑을 따른다:

AI 예산이 초기화됐으면 각 fix_target마다 재실행 전 claim(exit 1이면 그 fix_target은 건너뛰고 Phase 3 보고에 "예산 소진으로 미실행" 명시, 다른 fix_target은 계속 진행):
```powershell
node "$env:CLAUDE_PLUGIN_ROOT/agents/lib/ai-budget.mjs" claim --root "[절대경로]" --session "[ai_budget_session]" --role "[fix_target.agent]" --kind retry --reason "[fix_target.instruction, 100자로 트림]"
```

```
for each fix_target in eval_report.fix_targets (우선순위 순):
  Agent(
    subagent_type="general-purpose",
    description="[fix_target.agent에 대응하는 task-id]-RETRY · [fix_target.agent] · 개선 재실행",
    prompt="<[fix_target.agent] 에이전트 지침에 따라 재실행한다.
    개선 지시: [fix_target.instruction].
    범위: [fix_target.scope].
    프로젝트 루트: [절대경로].
    기존 산출물: _workspace/01_analyzer_report.md, _workspace/02_writer_files.md>",
    model="[아래 규칙]"
  )
```

재실행 model 규칙 (2-1/2-2와 동일 — "tier별 모델"로 뭉뚱그리지 않는다):
- `analyzer` 재실행: Full이면 opus, Standard면 sonnet
- `writer` 재실행: 모든 Tier에서 sonnet (2026-07-23 결정)

writer 재실행 후에는 2-2.3(skills_builder.py)을 다시 실행해 CLAUDE.md·02_writer_files.md 등을 재조립한다.

재생성 완료 후 harness-evaluator 1회 재실행 (평가 회차 = 2):

```
Agent(
  subagent_type="general-purpose",
  description="T-E-RECHECK · harness-evaluator · harness 품질 재평가 (2차)",
  prompt="<harness-evaluator 에이전트 지침. 평가 회차: 2.
  프로젝트 루트: [절대경로]. tier: [Standard/Full].
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
| validator 신뢰도 < 50 | Phase 3.7 메뉴의 QA 선택 시 실행 대신 "구조 검증 실패로 미실행" 한 줄만 작성. "validator 권고 우선 처리 후 재실행" 안내 |
| 작업 디렉토리 권한 오류 | 즉시 중단, 권한 확인 요청 |
| `_workspace/` 생성 실패 | 1회 재시도. 실패 시 중단 |
| harness-evaluator 실패 | eval 없이 Phase 3 결과만 보고. "eval 미실행" 안내 |
| eval 재생성 후 점수 하락 | 재생성 결과 무시, 초기 harness 유지. 1차·2차 점수 모두 사용자에게 보고 |
| 인덱스 무결성 기계 게이트가 analyzer 재실행 후에도 미해소 | 추가 재시도 없음. Phase 3 보고에 "인덱스 무결성 잔존 이슈"로 남은 FAIL/WARN 그대로 명시 |
| AI 예산 claim 실패(exit 1) | 해당 Agent 호출을 하지 않고 레인 중단(2-1/2-2/2-3) 또는 그 fix_target만 건너뜀(Phase 4) — 다른 예외처럼 WARN 후 계속하지 않는다, 하드 스톱이 의도 |
| `validate-harness.mjs` 실행 자체 실패(node 없음/python 미설치급 환경 문제) | WARN 후 계속 진행 — 스키마 검증 없이 validator_checks.py/validator Agent만으로 진행(기존 방식) |
| `validator_schema.json`의 `plugin_contract_failures > 0` | AI 재시도하지 않음. Phase 3 보고에 "플러그인 인덱스 계약 결함"으로 명시 |

상충 데이터: writer가 두 패턴 발견 시 출처 병기, validator/qa가 우선순위 권고 (자동 결정 X).

---

## 팀 통신 프로토콜

이 하네스는 `TeamCreate`/`SendMessage` 도구 없음. 대신:

| 채널 | 도구 | 용도 |
|------|------|------|
| 작업 조율 | `TaskCreate`/`TaskUpdate` | 진행 추적, 의존성 |
| 산출물 전달 | `_workspace/` 파일 | 분석 리포트·생성 파일·검증·인덱스 |

각 에이전트는 자기 `.md`에 명시된 입력 파일을 읽고 출력 파일을 작성. 오케스트레이터는 의존성 순서로 호출하고 산출물 존재 확인.


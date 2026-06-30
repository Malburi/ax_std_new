---
name: pair-init
description: 별도 저장소로 분리된 백엔드·프론트엔드 프로젝트를 연동한다. "백엔드 프론트엔드 연결해줘", "페어 설정", "pair init", "두 프로젝트 연동", "백엔드랑 프론트 같이 분석해줘", "API 계약 추출해줘", "크로스리포 설정", "파트너 프로젝트 등록" 요청 시 트리거.
---

# Pair Init (오케스트레이터)

분리된 두 저장소를 하네스 레벨에서 연동해 *교차 참조·전체 스택 스캐폴딩·API 드리프트 감지*를 활성화한다.

연동 후 두 프로젝트 어디서나 `cross-repo-scaffold`로 백엔드+프론트엔드 기능을 동시 생성하고,
`analyze-impact`가 API 계약 변경 시 파트너 영향을 자동으로 포함한다.

---

## Phase 0: 사전 확인

### 현재 프로젝트 확인

`pwd`로 현재 루트 파악. `_workspace/pair_config.md` 존재 확인:
- 이미 있으면 현재 설정 내용 보여주고 재설정 여부 사용자 확인.

### 하네스 존재 확인

`CLAUDE.md` + `.claude/` 존재 확인:
- 없으면 → "먼저 `harness-init`으로 현재 프로젝트 하네스를 생성한 뒤 실행하세요" 안내 후 중단.

---

## Phase 1: 프로젝트 쌍 정보 수집

사용자에게 다음 질문 (한 번에 묻기):

```
페어 설정에 필요한 정보를 입력해주세요:

1. 현재 프로젝트 역할: backend / frontend
2. 파트너 프로젝트 절대 경로:
   (예: C:\work\my-frontend 또는 /home/user/my-frontend)
3. API base URL (로컬 개발 기준):
   (예: http://localhost:8080)
4. (선택) 파트너 스택: (예: Vue 3, React, Angular — 모르면 빈칸)
```

### 파트너 경로 유효성 확인

PowerShell: `Test-Path "[파트너 경로]"` 또는 bash: `[ -d "[파트너 경로]" ]`

- 경로 없음 → "경로를 확인해주세요" 안내 후 재입력 요청.
- 파트너에 `CLAUDE.md` 없음 → WARN: "파트너 하네스가 없습니다. 먼저 파트너 프로젝트에서 `harness-init` 실행을 권장합니다. 없이 진행할까요? (Y/N)"
  - Y → API 계약 추출만 하고 validate 스킵.
  - N → 중단.

---

## Phase 2: pair_config.md 생성

### 현재 프로젝트에 생성

`_workspace/` 없으면 생성 후 `_workspace/pair_config.md` 작성:

```markdown
# Pair Configuration

project_type: [backend/frontend]
partner_type: [frontend/backend]
partner_root: [절대경로]
partner_workspace: [절대경로/_workspace]
partner_stack: [프론트엔드/백엔드 스택 — 미입력 시 unknown]
api_base_url: [http://localhost:8080]
api_contract_path: _workspace/index/api_contract.json
partner_api_contract: [파트너 절대경로]/_workspace/index/api_contract.json
linked_at: [YYYY-MM-DD]
```

### 파트너 프로젝트에도 생성 (역방향)

파트너 `_workspace/` 없으면 생성 후 역방향 내용으로 `pair_config.md` 작성.  
파트너 접근 불가 시 WARN 후 스킵 (현재 프로젝트 설정만 진행).

---

## Phase 3: API 계약 추출 (백엔드 프로젝트)

백엔드 루트(현재 또는 파트너)에서 `api-bridge`를 `extract` 모드로 실행:

```
Agent(
  subagent_type="general-purpose",
  description="백엔드 API 계약 추출",
  prompt="api-bridge 에이전트 지침에 따라 실행.
  mode: extract.
  프로젝트 루트: [백엔드 절대경로].
  출력: [백엔드 절대경로]/_workspace/index/api_contract.json.

  _workspace/index/ 폴더가 없으면 생성 후 작성.",
  model="sonnet"
)
```

완료 후 `api_contract.json` 존재 확인. 생성 실패 시 → "API 계약 추출 실패 — 수동으로 `api-bridge extract` 호출 가능" WARN 후 계속.

---

## Phase 4: API 드리프트 검증 (프론트엔드 하네스 있는 경우)

파트너 `CLAUDE.md`가 있고 Phase 3이 성공한 경우에만 실행:

```
Agent(
  subagent_type="general-purpose",
  description="프론트엔드 API 드리프트 검증",
  prompt="api-bridge 에이전트 지침에 따라 실행.
  mode: validate.
  프론트엔드 루트: [프론트엔드 절대경로].
  파트너 api_contract: [백엔드 절대경로]/_workspace/index/api_contract.json.
  출력: [프론트엔드 절대경로]/_workspace/api_drift_report.md.",
  model="sonnet"
)
```

파트너 하네스 없으면 Phase 4 스킵 (Phase 5로 직행).

---

## Phase 5: CLAUDE.md 파트너 섹션 추가

양쪽 프로젝트의 `CLAUDE.md`에 "## 파트너 프로젝트" 섹션을 추가/갱신한다.

### 백엔드 CLAUDE.md에 추가

```markdown
## 파트너 프로젝트 (프론트엔드)

- 파트너 경로: [절대경로]
- 스택: [프론트엔드 스택]
- API 계약: `_workspace/index/api_contract.json` ([엔드포인트 수]개)
- 연동일: [YYYY-MM-DD]

### 크로스 리포 워크플로우
| 상황 | 명령 |
|------|------|
| 전체 스택 기능 동시 생성 | "전체 스택 기능 만들어줘" → cross-repo-scaffold |
| API 변경 전 프론트 영향 확인 | "영향도 분석해줘" → analyze-impact (파트너 영향 자동 포함) |
| 프론트 서비스 스텁만 생성 | "프론트 스텁 만들어줘" → api-bridge generate-stub |
| API 드리프트 재확인 | "API 드리프트 확인해줘" → pair-init 재실행 |
| API 계약 갱신 | 코드 변경 후 "API 계약 갱신해줘" → api-bridge extract |
```

### 프론트엔드 CLAUDE.md에 추가

```markdown
## 파트너 프로젝트 (백엔드)

- 파트너 경로: [절대경로]
- 스택: [백엔드 스택]
- API 계약 위치: `[백엔드 절대경로]/_workspace/index/api_contract.json`
- 연동일: [YYYY-MM-DD]

### 크로스 리포 워크플로우
| 상황 | 명령 |
|------|------|
| 전체 스택 기능 동시 생성 | "전체 스택 기능 만들어줘" → cross-repo-scaffold |
| 사용 가능한 API 목록 확인 | "API 목록 보여줘" → api-bridge extract (재읽기) |
| 드리프트 감지 | "API 드리프트 확인해줘" → pair-init 재실행 |
```

---

## Phase 6: 결과 보고

```
페어 설정 완료

백엔드:    [경로] ([스택])
프론트엔드: [경로] ([스택])
API base:  [url]

API 계약 추출: [성공/실패]
  엔드포인트: N개 (공개 A개 | 인증 B개)
  저장: [백엔드]/_workspace/index/api_contract.json

API 드리프트 검증: [실행됨/스킵]
  🔴 MISSING: N건
  🟡 MISMATCH: N건
  🟢 UNUSED: N건
  상세: [프론트엔드]/_workspace/api_drift_report.md

이제 가능한 작업:
  "주문 취소 기능 전체 만들어줘"  →  cross-repo-scaffold (백엔드+프론트 동시)
  "이 API 수정 영향 분석해줘"      →  analyze-impact (파트너 영향 자동 포함)
  "API 드리프트 다시 확인"          →  pair-init 재실행

양쪽 프로젝트 어디서나 "전체 스택 기능 만들어줘"로 cross-repo-scaffold를 실행할 수 있습니다.
```

HIGH 드리프트가 있으면 "즉시 수정 권장" 항목 명시.

---

## 에러 핸들링

| 상황 | 대응 |
|------|------|
| 파트너 경로 접근 불가 | 현재 프로젝트 설정만 저장, 드리프트 검증 스킵 |
| api-bridge extract 실패 | WARN 기록, 나머지 Phase 계속 진행 |
| 파트너 CLAUDE.md 수정 권한 없음 | 현재 프로젝트 CLAUDE.md만 수정, 파트너는 수동 안내 |
| pair_config.md 이미 있음 | 덮어쓰기 전 사용자 확인 |

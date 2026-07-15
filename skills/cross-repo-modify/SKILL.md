---
name: cross-repo-modify
description: 페어 연동된 백엔드·프론트엔드 중 한쪽에서 지시한 기존 기능 개선/수정을, 필요 시 양쪽 저장소에 함께 반영한다. "이 기능 개선해줘", "API 필드 추가해줘", "이거 고쳐야 하는데 프론트도 같이", "양쪽 다 수정해줘", "cross-repo modify", "풀스택 수정", "백엔드 프론트 둘 다 고쳐줘", "이 API 바꾸는데 프론트 영향 있으면 같이 처리해줘" 요청 시 트리거.
---

# Cross-Repo Modify (오케스트레이터)

`pair-init`으로 연동된 백엔드·프론트엔드 중 **한쪽에서 시작한 기존 기능 개선/수정**이 API 계약에
영향을 주는 경우, 파트너 저장소까지 함께 안전하게 반영한다.

`cross-repo-scaffold`(신규 기능 동시 생성)와 달리 이 스킬은 **이미 존재하는 기능의 변경**을 다룬다.
`safe-modify`의 사전 영향 분석 → 적용 → 사후 안전성 흐름을 그대로 따르되, 각 단계에 파트너 저장소
분기를 추가한 것.

---

## Phase 0: 사전 조건 확인

### 페어 설정 확인

`_workspace/pair_config.md` 존재 확인:
- 없으면 → "파트너 연동이 없습니다. 이 프로젝트만 수정하려면 `safe-modify`를 사용하세요. 양쪽 연동은 `pair-init`으로 먼저 설정하세요." 안내 후 중단.

pair_config에서 `project_type`(현재 역할), `partner_type`, `partner_root`, `partner_workspace`,
`api_contract_path`, `partner_api_contract` 로드. `initiating_root` = 현재 프로젝트 루트.

`wiki/architecture.md`(통합본, `generate-wiki`로 생성된 경우)가 있으면 먼저 훑어 시스템 전체 구조를
빠르게 파악하는 데 참고할 수 있다 — 단, 생성 시점 스냅샷이라 최신성이 보장되지 않으므로 실제 영향
분석·드리프트 검증은 반드시 아래 Phase 1/2/6의 라이브 재분석(`impact-analyzer`/`api-bridge`)으로 수행한다.

### 운영 모드 키워드 감지

safe-modify Phase 0과 동일한 키워드 표 적용 (`production`/`hotfix`/`legacy`/`customer_facing`/`normal`).
이후 양쪽 change-safety 호출 모두에 동일 mode 전달.

---

## Phase 1: 시작 측 영향 분석

변경 대상이 명확하면 → `impact-analyzer`를 `initiating_root`에서 실행 (analyze-impact와 동일):
- 변경 대상 정규화 → 영향 리포트 `_workspace/impact_<slug>.md`

리포트에서 변경 대상이 **API 엔드포인트/컨트롤러/DTO/서비스 계층 중 파트너 노출 대상**인지 판별:
- 해당하면 → Phase 2로.
- 순수 내부 로직(파트너 계약과 무관, 예: 프론트 전용 UI 스타일, 백엔드 전용 배치 잡)이면 → 파트너 영향 없음으로 판단, `safe-modify`와 동일하게 단독 진행 (Phase 4로 직행, Phase 2/3/5 스킵).

---

## Phase 2: 파트너 영향 확인

`api-bridge`를 `check-impact` 모드로 실행:

```
Agent(
  subagent_type="general-purpose",
  description="파트너 영향 확인 — [변경 대상]",
  prompt="api-bridge 에이전트 지침에 따라 실행.
  mode: check-impact.
  변경 엔드포인트/대상: [Phase 1에서 식별된 method+path 또는 DTO/함수].
  백엔드 루트: [backend_root]. 프론트엔드 루트: [frontend_root].
  출력: 콘솔 요약 (파트너 호출 위치·영향받는 컴포넌트 목록).",
  model="sonnet"
)
```

파트너 영향 없음(호출 위치 0건) → 단독 진행 안내 후 Phase 4로.
파트너 영향 있음 → Phase 3으로.

---

## Phase 3: 파트너 반영 확인 게이트

파트너 저장소는 **별도 git/배포/리뷰 프로세스**를 가질 수 있으므로, 자동으로 파일을 고치기 전에 반드시 확인받는다:

```
이 변경은 파트너 프로젝트([partner_root])에도 영향을 줍니다:
  영향받는 파일/함수: N개
  - [파일:라인] — [함수명]

진행 옵션:
1. 양쪽 모두 반영 (파트너 저장소 파일도 함께 수정 — 커밋은 하지 않음, 검토 후 각자 커밋)
2. 이 프로젝트만 수정 (파트너는 수동 안내만 출력)
3. 중단

선택? (1/2/3)
```

- 옵션 1 선택 시에도 **양쪽 저장소 모두 git commit은 절대 자동 실행하지 않는다** (기존 정책 그대로 — 파일 작성까지만).
- CRITICAL 등급(Phase 1 impact 결과)이면 옵션 1 선택 시 추가로 "운영 영향도가 높습니다. 정말 진행할까요?" 재확인.

---

## Phase 4: 시작 측 변경 적용

`safe-modify` Phase 2와 동일:
- 사용자가 직접 작성하거나, 자연어 설명 → 어시스턴트가 Edit/Write로 적용.
- 적용 후 변경 파일 목록 수집.

변경이 API 계약 형태(엔드포인트 경로/메서드/DTO 필드)를 바꾸면, 적용 후 `api-bridge extract`로
`[backend_root]/_workspace/index/api_contract.json` 갱신 (신규 필드만 append, 전체 재추출 불필요).

---

## Phase 5: 파트너 측 변경 적용 (Phase 3에서 옵션 1 선택 시만)

```
Agent(
  subagent_type="general-purpose",
  description="파트너 저장소 반영 — [변경 대상]",
  prompt="safe-modify 스킬의 Phase 2(변경 적용) 지침만 수행한다 (사전/사후 안전성 평가는 이 오케스트레이터의
  Phase 6에서 통합 실행하므로 생략).

  프로젝트 루트: [partner_root]
  변경 배경: [initiating_root]에서 [변경 대상]이 다음과 같이 바뀜: [Phase 4 변경 요약]
  갱신된 API 계약: [backend_root]/_workspace/index/api_contract.json
  영향받는 파트너 파일: [Phase 2 check-impact 결과 목록]
  패턴 파일: [partner_root]/.claude/patterns/ (있으면 참조)

  변경 방식:
  - 백엔드 계약 변경(필드 추가/제거, 경로 변경)에 맞춰 프론트엔드 서비스 함수·타입 정의 수정, 또는
  - 프론트엔드 요구사항 변경에 맞춰 백엔드 컨트롤러/서비스/DTO 수정
  - TODO로 남길 부분은 명시적으로 // TODO 표기 (cross-repo-scaffold 원칙과 동일)
  - git commit 금지 — 파일 작성까지만

  결과를 [partner_root]/_workspace/cross_modify_partner.md에 저장.",
  model="sonnet"
)
```

완료 후 `[partner_root]/_workspace/cross_modify_partner.md` 존재 확인.

---

## Phase 6: 통합 안전성 평가 + 드리프트 재검증

### 양쪽 change-safety

시작 측:
```
Agent(
  subagent_type="general-purpose",
  description="변경 안전성 평가 (시작 측)",
  prompt="<change-safety 에이전트 지침. 변경 파일: [Phase 4 목록]. mode: [Phase 0 감지 모드]. impact 리포트: _workspace/impact_<slug>.md. 출력: _workspace/safety_<slug>.md>",
  model="opus"
)
```

파트너 측(Phase 5 실행된 경우만), 같은 메시지에서 병렬 호출 가능(서로 독립적인 평가 대상):
```
Agent(
  subagent_type="general-purpose",
  description="변경 안전성 평가 (파트너 측)",
  prompt="<change-safety 에이전트 지침. 프로젝트 루트: [partner_root]. 변경 파일: [partner_root]/_workspace/cross_modify_partner.md 목록. mode: [Phase 0 감지 모드]. 출력: [partner_root]/_workspace/safety_<slug>.md>",
  model="opus"
)
```

### API 드리프트 재검증 (Phase 5 실행된 경우만)

```
Agent(
  subagent_type="general-purpose",
  description="크로스 리포 드리프트 재검증",
  prompt="api-bridge 에이전트 지침에 따라 실행.
  mode: validate.
  프론트엔드 루트: [frontend_root].
  파트너 api_contract: [backend_root]/_workspace/index/api_contract.json.
  검증 범위: 방금 수정된 파일만.
  출력: 콘솔 요약.",
  model="sonnet"
)
```

---

## Phase 7: 결과 보고

```
크로스 리포 수정 완료: [변경 대상]

━━━ [initiating_root 역할] ([initiating_root]) ━━━
  변경 파일: [목록]
  안전성: [GO/HOLD/STOP] (종합 X/10)

━━━ [partner_type] ([partner_root]) ━━━ (Phase 5 실행된 경우만)
  변경 파일: [목록]
  안전성: [GO/HOLD/STOP] (종합 X/10)
  ⚠️ TODO: [cross_modify_partner.md에 명시된 항목]

━━━ API 계약 ━━━
  드리프트 재검증: [✓ 일치 / N건 발견]

결정: [GO / HOLD / STOP] (둘 중 낮은 등급 기준)

[GO]
다음 단계:
  [initiating 측] → 영향 테스트 실행 → commit
  [partner 측]    → TODO 완성 → 자체 리뷰 → commit
  (양쪽 저장소이므로 각자 별도 PR/커밋 필요 — 이 스킬은 파일만 준비함)

[HOLD/STOP]
보완 필요 항목: [safety report 요약]
```

---

## 원칙

### 파트너 저장소는 남의 저장소다

Phase 3 확인 없이 파트너 파일을 고치지 않는다. 커밋도 절대 자동으로 하지 않는다 — 별도 git/배포
프로세스라는 전제(사용자가 명시한 구조) 때문에, 파트너 팀의 리뷰 흐름을 우회해서는 안 된다.

### 계약 우선, 추측 금지

파트너 측 변경은 항상 `api_contract.json` 갱신 이후, 갱신된 계약 기준으로 생성한다.

### 단독 실행 경로

파트너 영향이 없거나 사용자가 "이 프로젝트만"을 선택하면 사실상 `safe-modify`와 동일하게 동작한다 —
이 스킬은 safe-modify 위에 파트너 분기를 얹은 것이지 대체하는 것이 아니다.

### pair_config.md 없이 실행 불가

`cross-repo-scaffold`와 동일하게 페어 연동이 전제 조건이다.

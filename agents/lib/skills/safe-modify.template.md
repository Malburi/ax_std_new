---
name: safe-modify
description: 코드 변경을 안전하게 수행하는 워크플로우. "이거 안전하게 수정해줘", "회귀 위험 없이 변경", "safe modify", "이 변경 안전한가?", "변경 전 체크", "이 패치 적용해도 돼?" 요청 시 트리거.
---

# Safe Modify (오케스트레이터)

변경을 적용하기 전후로 영향도·안전성 평가를 자동 수행한다.

## 단계
1. **사전 분석** — analyze-impact 호출
2. **변경 적용** — 사용자 확인 후 코드 수정 진행
3. **사후 검증** — `change-safety` 에이전트 호출:
   - 입력: git diff, impact 리포트
   - 출력: `_workspace/safety_<slug>.md` (GO/HOLD/STOP 권고)
4. **테스트 권고** — 영향받는 테스트 목록 + 신규 회귀 테스트가 필요한 위치 표시

상세 로직은 `.claude/agents/change-safety.md` 참조 (harness-fin 공통).

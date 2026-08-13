---
name: trace-logic
description: 특정 기능·API·화면의 처리 흐름을 진입점부터 DB까지 추적한다. "주문 취소 로직 어디 있어?", "이 API 어떻게 처리돼?", "결제 흐름 보여줘", "로그인 로직 따라가줘", "이 화면 저장 버튼 누르면 뭐가 실행돼?", "처리 흐름 알려줘", "실행 흐름", "로직 흐름", "trace logic", "flow of", "흐름 추적", "어떻게 동작해?", "동작 방식", "내부 구조" 요청 시 트리거.
---

# Trace Logic (오케스트레이터)

추적 대상을 받아 `logic-tracer` 에이전트를 호출하고 결과를 사용자에게 전달한다.

---

## Phase 0: 입력 파악

사용자 표현에서 추적 대상 추출:

| 사용자 표현 | 추출 |
|-----------|------|
| "주문 취소 로직 추적" | 기능명: "주문 취소" |
| "POST /api/orders/{id}/cancel 흐름" | API: `POST /api/orders/{id}/cancel` |
| "OrderCancelController 어떻게 돼?" | 클래스: `OrderCancelController` |
| "결제 화면 확인 버튼 누르면" | UI 이벤트: "결제 화면 확인 버튼" |

모호하면 1회 확인 ("어떤 기능/API/화면의 흐름을 추적할까요?").

---

## Phase 1: 인덱스 준비

`_workspace/index/` 확인:
- `symbols.json`, `call_graph.json`, `sql_usage.json` 있으면 → logic-tracer에 전달
- 없으면 → logic-tracer가 grep 탐색으로 대체 (속도 저하 안내)

---

## Phase 2: logic-tracer 호출

```
Agent(
  subagent_type="general-purpose",
  description="로직 흐름 추적",
  prompt="<logic-tracer 에이전트 지침. 추적 대상: [추출된 대상]. 프로젝트 루트: [절대경로]. 출력: _workspace/reports/trace_<slug>.md>",
  model="sonnet"
)
```

slug: 추적 대상의 안전한 파일명 형태 (예: `order_cancel`, `payment_confirm`).

---

## Phase 3: 결과 전달

`_workspace/reports/trace_<slug>.md` 읽어 사용자에게 출력.

결과 끝에 다음 단계 안내:
- 변경 계획이 있으면 → "analyze-impact로 영향도 확인 권고"
- 레거시 코드가 포함되어 있으면 → "legacy-decoder로 상세 해석 권고"
- 특정 SQL이 궁금하면 → "review-sql로 SQL 리뷰 권고"

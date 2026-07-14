---
name: analyze-impact
description: 변경 대상(파일/함수/클래스/SQL/엔드포인트)의 영향도를 분석한다. "이거 수정하면 어디 영향?", "영향도 분석", "impact analysis", "이 함수 수정해도 돼?", "이 SQL 바꿨을 때 어디 영향?", "이 컬럼 추가했을 때 영향" 등 요청 시 트리거.
---

# Analyze Impact (오케스트레이터)

변경 대상이 주어지면 `impact-analyzer` 에이전트를 호출해 직간접 영향과 위험도를 평가한다.

## 입력
사용자가 자연어로 변경 대상을 명시 ("OrderService.cancel 수정 예정", "TBL_ORDER에 STATUS 컬럼 추가").

## 실행
1. `_workspace/index/` 인덱스 존재 확인. 없으면 → analyzer를 `feature-scoped` 모드로 호출해 최소 인덱스 생성.
2. impact-analyzer 에이전트 호출 (general-purpose, opus):
   - 입력: 변경 대상, 인덱스 경로
   - 출력: `_workspace/impact_<slug>.md`
3. 결과를 사용자에게 보고 (1~10 위험도, 영향받는 파일/테스트/외부 시스템).

상세 로직은 `.claude/agents/impact-analyzer.md` 참조 (harness-fin 공통).

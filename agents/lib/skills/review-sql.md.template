---
name: review-sql
description: SQL 영향도·성능·보안을 리뷰한다. "이 SQL 리뷰해줘", "쿼리 점검", "SQL review", "N+1 확인", "이 쿼리 성능", "인덱스 잘 쓰고 있어?" 요청 시 트리거.
---

# Review SQL (오케스트레이터)

`sql-reviewer` 에이전트를 호출해 SQL 텍스트 또는 변경 diff를 리뷰한다.

## 검사 항목
- 사용처 역추적 (어디서 호출되나)
- 인덱스 활용 가능성
- N+1 패턴
- SQL 인젝션 위험
- 트랜잭션 적정성
- DB 스키마 영향 (DDL인 경우)

상세 로직은 `.claude/agents/sql-reviewer.md` 참조 (harness-fin 공통).

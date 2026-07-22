---
name: scaffold-feature
description: 추출된 프로젝트 컨벤션에 따라 신규 기능을 스캐폴딩한다. "[기능명] 기능 추가", "주문 취소 기능 만들어줘", "scaffold feature", "신규 모듈 생성 (컨벤션 준수)", "패턴대로 만들어줘" 요청 시 트리거.
---

# Scaffold Feature (오케스트레이터)

`.claude/patterns/` 에 추출된 컨벤션 파일들을 로드한 뒤 신규 파일을 생성한다.

## 단계
1. `.claude/patterns/*.md` 모두 로드 (없으면 pattern-extractor 먼저 호출)
2. 사용자에게 기능명·범위 확인 (1~2회 질문)
3. 영향받을 레이어 식별 (Controller→Service→DAO→Table 등)
4. 각 레이어에 컨벤션 준수 보일러플레이트 생성
5. 테스트 골격 생성
6. 사전 영향도 체크 (analyze-impact 호출, 기존 코드와 충돌 여부)

기본 scaffolder.md와의 차이: scaffolder는 *체크리스트만* 제공, scaffold-feature는 *실제 파일 생성*까지 수행.

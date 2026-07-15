---
name: scaffold-feature
description: 추출된 프로젝트 컨벤션에 따라 신규 기능을 스캐폴딩한다(Controller/Service/DAO/DTO/테스트까지). "[기능명] 기능 추가", "주문 취소 기능 만들어줘", "신규 모듈 생성 컨벤션", "scaffold feature", "패턴대로 만들어줘", "프로젝트 스타일로 새 기능", "보일러플레이트 생성", "새 API 만들어줘 컨벤션 따라" 요청 시 트리거.
---

# Scaffold Feature (오케스트레이터)

`.claude/patterns/`에 추출된 컨벤션을 따라 *전체 레이어*의 신규 파일을 생성한다.

기본 `scaffolder` 스킬과 차이: `scaffolder`는 *체크리스트만* 제공, `scaffold-feature`는 *실제 파일 생성*까지 수행하며 *컨벤션 100% 준수*.

---

## Phase 0: 사전 조건 확인

### pair_config 확인 (Type B 지원)

`_workspace/pair_config.md` 존재 확인:
- **있고** `partner_root` 경로가 유효하면 → `pair_linked = true`
  - Phase 1에서 "프론트엔드도 함께 생성할까요?" 질문 추가
- **없으면** → `pair_linked = false` (단일 레포 스캐폴딩 진행)

### 패턴 로드

`.claude/patterns/*.md` 확인:
- 스켈레톤 상태 (pattern-extractor 미실행) → "패턴 추출 먼저 필요" 안내 후 pattern-extractor 호출
- 본문 채워짐 → 계속 진행

### 분석 리포트 로드

`_workspace/01_analyzer_report.md`에서:
- 아키텍처 레이어 목록
- 빌드/실행 명령
- 모듈 분류 방식 (기능별/레이어별/혼합)

---

## Phase 1: 기능 명세 수집

사용자에게 다음 확인 (1~2회):

| 질문 | 예시 답 |
|------|--------|
| 기능명 | "주문 취소" |
| 영향 레이어 | "Controller, Service, DAO, DTO, 테스트" (기본 전체) |
| 기존 유사 모듈 | "OrderRefund 비슷하게" (있으면 참조) |
| API 엔드포인트 | "POST /api/orders/{id}/cancel" |
| DB 테이블 영향 | "TBL_ORDER.STATUS 업데이트" |
| (pair_linked=true) 프론트엔드도 함께? | Y → cross-repo-scaffold로 위임 / N → 백엔드만 진행 |

추가 정보:
- 기존 유사 모듈을 명시하면 → 그 모듈 코드를 더 적극 참조
- DB 영향이 있으면 → review-sql 사전 호출 권고
- pair_linked=true에서 "Y (프론트도 함께)" → 즉시 `cross-repo-scaffold`로 위임하고 scaffold-feature 종료
  (cross-repo-scaffold가 백엔드+프론트엔드 양쪽 모두 처리)

---

## Phase 2: 사전 영향 체크 (선택)

기능명·테이블 영향이 있으면 → `analyze-impact`로 *충돌 가능성* 사전 점검:
- 같은 엔드포인트가 이미 있는지
- 같은 SQL ID가 이미 있는지
- 같은 클래스/메서드명 충돌

충돌 발견 시 → 사용자에게 알리고 명명 조정 권고.

---

## Phase 3: 파일 생성

각 레이어별로 컨벤션 적용:

### 3-1. Controller / Action / Router 레이어

`.claude/patterns/controller_pattern.md` (또는 `action_pattern.md`) 본문 로드 → 권장 패턴 추출:
- 클래스 명명 패턴
- 매핑 어노테이션 패턴
- 매개변수 처리
- 응답 형식
- 예외 처리

생성:
```java
// 예: Spring Boot
@RestController
@RequestMapping("/api/orders")
public class OrderCancelController {

    private final OrderCancelService orderCancelService;

    public OrderCancelController(OrderCancelService orderCancelService) {
        this.orderCancelService = orderCancelService;
    }

    @PostMapping("/{id}/cancel")
    public ResponseEntity<CancelResponse> cancel(
        @PathVariable Long id,
        @Valid @RequestBody CancelRequest request
    ) {
        // TODO: 비즈니스 로직 호출
        return ResponseEntity.ok(orderCancelService.cancel(id, request));
    }
}
```

생성 위치: 분석 리포트의 "아키텍처 레이어" 경로 패턴 그대로.

### 3-2. Service 레이어

`.claude/patterns/service_pattern.md` 본문 기반.

### 3-3. DAO / Repository / Mapper 레이어

`.claude/patterns/dao_pattern.md` 본문 기반.  
SQL ID는 분석 리포트의 명명 규칙 (`MODULE_FEATURE_S01` 등) 따름.

### 3-4. DTO / Entity 레이어

`.claude/patterns/dto_pattern.md` (있으면) 또는 entity 패턴 기반.

### 3-5. Test 레이어

`test-generator` 에이전트 호출:
```
Agent(
  subagent_type="general-purpose",
  description="신규 기능 테스트 생성",
  prompt="<test-generator 지침. 대상: [생성된 파일 목록]. 컨벤션: .claude/patterns/test_pattern.md.>",
  model="sonnet"
)
```

테스트는 *작성 대상 코드의 골격*만 생성하고 *비즈니스 검증은 TODO*로 남긴다 (test-generator 원칙).

### 3-6. 설정 / 라우팅 등록

스택별로 필요한 설정 파일에 등록 항목 추가:
- Struts: `struts-*.xml`에 `<action>` 추가
- Spring XML: `applicationContext-*.xml`에 Bean 등록
- web.xml의 servlet/filter 패턴 (필요 시)
- frontend route 등록 (Next.js, Vue Router 등)

---

## Phase 4: 사후 안전성 평가

`change-safety` 호출 (자동) — 생성된 파일들에 대해 컨벤션 일치도 + 보안 위험 점검.

결과:
- GO → 진행
- HOLD → 보완 필요 항목 표시
- STOP → 거의 발생 안 함 (보안 위험 자동 도입 시만)

---

## Phase 5: 결과 보고

```
신규 기능 스캐폴딩 완료: [기능명]

생성된 파일:
- [Controller] [경로]
- [Service] [경로]
- [DAO/Mapper] [경로]
- [DTO/Entity] [경로]
- [Test] [경로]
- (설정 변경) [파일]: [추가 항목]

컨벤션 일치도: X% (change-safety 평가)

⚠️ TODO 항목 (수동 완성 필요):
- [위치]: [완성할 부분]

영향도 사전 체크: [충돌 없음 / 충돌 발견 — 보완]

다음 단계:
- 비즈니스 로직 구현 (TODO 채우기)
- 테스트 assertion 보완
- 빌드/실행: [명령어]
- 통과 후 commit
```

---

## 원칙

### 컨벤션 100% 준수

`.claude/patterns/`의 권장 패턴과 다르게 생성하지 않는다. 패턴이 모호하거나 충돌하면 *생성 중단* 후 사용자에게 결정 요청.

### TODO 정직 표기

자동 생성된 *비즈니스 로직*은 비어 있다. TODO로 명시. 가짜 구현(예: 무조건 success 반환)으로 채우지 않는다.

### 충돌 자동 회피

기존 파일/메서드/SQL ID와 충돌하면 *덮어쓰지 않고* 사용자에게 조정 요청.

### 패턴 부재 시 거부

`.claude/patterns/`가 비어 있거나 스켈레톤이면 → pattern-extractor 먼저 실행 권고. 컨벤션 없이 스캐폴딩하면 *추측에 기반한 잘못된 표준*을 도입할 위험.

---
name: api-bridge
description: 백엔드 REST API 계약 추출 + 프론트엔드 서비스 호출 정합성 검증. 백엔드에서 api_contract.json 생성, 프론트엔드에서 계약 위반·드리프트 탐지, 신규 엔드포인트의 프론트엔드 서비스 스텁 생성. pair-init·cross-repo-scaffold·impact-analyzer에서 호출.
model: sonnet
---

# API Bridge Agent

백엔드↔프론트엔드 API 계약을 추출·검증·생성한다.  
별도 저장소(Type B) 구조에서 두 프로젝트가 서로의 API 표면을 파악하도록 연결한다.

---

## 팀 통신 프로토콜

| 항목 | 내용 |
|------|------|
| **수신** | `mode` + 프로젝트 루트 절대 경로 (+ 파트너 경로, 모드에 따라) |
| **발신** | mode별 산출물 (아래 각 섹션 참조) |
| **작업 범위** | 읽기·추출·생성만. 기존 코드 수정 금지 |

---

## 실행 모드

| mode | 동작 | 호출처 |
|------|------|--------|
| `extract` | 백엔드 코드 → `api_contract.json` 생성 | pair-init, harness-init(analyzer Step 16), cross-repo-scaffold Phase 4 |
| `validate` | 프론트엔드 호출 vs 파트너 계약 비교 → drift 리포트 | pair-init |
| `generate-stub` | 신규 엔드포인트의 프론트엔드 서비스 스텁 생성 | cross-repo-scaffold Phase 5 |
| `check-impact` | API 변경 시 파트너 프론트엔드 영향 확인 | impact-analyzer Step 8.5 |

---

## Mode: extract (백엔드 → api_contract.json)

### Step 1: 스택별 컨트롤러 파일 수집

| 스택 | 탐지 패턴 |
|------|---------|
| Spring Boot (Java/Kotlin) | `@RestController`, `@Controller` 어노테이션이 있는 `.java`/`.kt` 파일 |
| Spring MVC (XML) | `struts-*.xml`의 `<action>` 매핑 |
| Express.js | `router.get/post/put/delete/patch`, `app.get/post/...` 정의 파일 |
| NestJS | `@Controller` 데코레이터 파일 |
| FastAPI | `@app.route`, `@router.get/post/...` 파일 |
| Flask | `@app.route`, Blueprint 등록 파일 |
| Django REST | ViewSet + `router.register`, `@api_view` 파일 |
| ASP.NET Core | `[ApiController]` + `[Route]` 어노테이션 파일 |

grep 명령 예 (Spring Boot):
```
grep -rn "@RestController\|@Controller" src/ --include="*.java" -l
```

### Step 2: 엔드포인트 상세 추출

각 컨트롤러 파일을 Read로 읽어 엔드포인트별 추출:

```json
{
  "method": "POST",
  "path": "/api/orders/{id}/cancel",
  "controller_file": "src/main/java/.../OrderCancelController.java",
  "controller_class": "OrderCancelController",
  "handler": "cancel",
  "path_variables": ["id"],
  "query_params": [],
  "request_body_type": "CancelRequest",
  "response_type": "ResponseEntity<CancelResponse>",
  "auth_required": true,
  "roles": ["USER"],
  "deprecated": false
}
```

**인증 탐지:**
- Spring Security: `@PreAuthorize`, `@Secured`, SecurityConfig `permitAll()` vs `authenticated()`
- 미들웨어: Express auth middleware 체인 순서 확인
- 공개 경로: `/api/public/**`, `/auth/**`, `/actuator/**` 등 패턴

**경로 변수 탐지:**
- `{id}`, `:id`, `<int:id>` 등 스택별 패턴 정규화

### Step 3: DTO/모델 추출 (추론 가능한 경우)

Request/Response 타입에 대해 실제 클래스/인터페이스 파일 읽어 필드 추출:

```json
{
  "CancelRequest": {
    "fields": [
      {"name": "reason", "type": "String", "required": true, "constraints": ["@NotBlank"]},
      {"name": "canceledAt", "type": "LocalDateTime", "required": false}
    ]
  }
}
```

DTO 파일 탐지가 어려운 경우 (레거시, 복잡한 상속) → 필드 목록 `"fields": "TODO: 수동 확인 필요"` 로 표기.

### Step 4: api_contract.json 출력

저장: `[백엔드 루트]/_workspace/index/api_contract.json`

```json
{
  "generated_at": "[ISO-8601]",
  "project_type": "backend",
  "stack": "[감지된 스택]",
  "base_path": "/api",
  "endpoints": [
    {
      "method": "GET",
      "path": "/api/orders",
      "controller_file": "...",
      "handler": "list",
      "path_variables": [],
      "query_params": ["status", "page", "size"],
      "request_body_type": null,
      "response_type": "Page<OrderDto>",
      "auth_required": true,
      "roles": ["USER", "ADMIN"],
      "deprecated": false
    }
  ],
  "models": {
    "OrderDto": { "fields": [...] },
    "CancelRequest": { "fields": [...] }
  },
  "total_endpoints": 24,
  "public_endpoints": 3,
  "auth_endpoints": 21
}
```

용량 한도: 엔드포인트 200개+ 이면 핵심 도메인 모듈 우선, 나머지는 경로·메서드만 표기.

---

## Mode: validate (프론트엔드 서비스 호출 vs 계약 검증)

### Step 1: 파트너 api_contract.json 로드

`partner_api_contract` 경로(pair_config.md에서 읽음)에서 로드.  
없으면 → "api_contract.json 없음. pair-init 또는 api-bridge extract 먼저 실행" 안내 후 중단.

### Step 2: 프론트엔드 API 호출 수집

| 스택 | 탐지 패턴 |
|------|---------|
| Axios (Vue/React) | `axios.get/post/put/delete/patch(url`, `instance.get/post/...` |
| fetch API | `fetch(url, { method:` |
| Angular HttpClient | `this.http.get/post/put/delete/patch(` |
| 서비스 레이어 | `services/`, `api/`, `src/api/` 폴더의 함수 정의 우선 탐색 |

각 호출에서 추출: HTTP 메서드 + URL 문자열/템플릿 + 파일 경로 + 라인 번호

URL 정규화: `` `/api/orders/${id}/cancel` `` → `/api/orders/{id}/cancel`

### Step 3: 계약 vs 실제 비교

| 불일치 유형 | 설명 | 심각도 |
|-----------|------|--------|
| `MISSING_ENDPOINT` | 프론트에서 호출하는데 백엔드에 없음 | 🔴 HIGH |
| `METHOD_MISMATCH` | 같은 경로인데 HTTP 메서드 다름 | 🔴 HIGH |
| `PATH_MISMATCH` | 유사 경로인데 변수 패턴 다름 | 🟡 MEDIUM |
| `STALE_CALL` | 백엔드에서 deprecated된 엔드포인트 호출 | 🟡 MEDIUM |
| `UNUSED_ENDPOINT` | 백엔드에 있는데 프론트 호출 없음 | 🟢 LOW |

### Step 4: drift 리포트 출력

`[프론트엔드 루트]/_workspace/api_drift_report.md`:

```
=== API DRIFT REPORT ===

검증 시각: [ISO-8601]
백엔드 엔드포인트: N개 | 프론트엔드 호출: M개

🔴 MISSING_ENDPOINT (N건)
  - [파일:라인] → [METHOD /path] (백엔드에 없음)
  권고: 백엔드에 엔드포인트 추가 또는 프론트 URL 수정

🔴 METHOD_MISMATCH (N건)
  - [프론트] GET /api/orders → [백엔드] POST /api/orders
  권고: 프론트 HTTP 메서드 수정

🟡 PATH_MISMATCH (N건)
  - [프론트] /api/order/:id vs [백엔드] /api/orders/{id}
  권고: 경로 일치 확인

🟢 UNUSED_ENDPOINT (N건)
  - [백엔드] DELETE /api/orders/{id} — 프론트 호출 없음
  (정보성 — 미사용이지만 오류는 아님)

총 드리프트: N건 (HIGH: A, MEDIUM: B, LOW: C)
권고: [즉시 수정 필요 / 검토 권장 / 양호]
=== END ===
```

---

## Mode: generate-stub (프론트엔드 서비스 스텁 생성)

### 입력
- 대상 엔드포인트 정보 (api_contract.json의 항목 1개 이상)
- 프론트엔드 루트 + 서비스 폴더 경로 (pair_config.md 또는 _workspace/01_analyzer_report.md에서 확인)
- 프론트엔드 스택 (pair_config.md의 frontend_stack 또는 프론트 analyzer_report에서 확인)

### 스택별 스텁 생성

#### Vue 3 + Axios (TypeScript)

기존 서비스 파일 있으면 함수 추가, 없으면 신규 생성.

```typescript
// [서비스폴더]/orderService.ts

import type { AxiosResponse } from 'axios'
import apiClient from '@/api/client'  // 프로젝트 axios 인스턴스 (경로는 패턴에서 확인)

// TODO: 백엔드 DTO 필드 확인 후 정확한 타입으로 교체
export interface CancelRequest {
  reason: string
}

export interface CancelResponse {
  success: boolean
  message?: string
}

export const cancelOrder = async (id: number, data: CancelRequest): Promise<CancelResponse> => {
  const response: AxiosResponse<CancelResponse> = await apiClient.post(
    `/api/orders/${id}/cancel`,
    data
  )
  return response.data
}
```

#### Vue 2 + axios (JavaScript, Options API)

```javascript
// [서비스폴더]/order.js
import request from '@/utils/request'  // 프로젝트 axios 인스턴스

export function cancelOrder(id, data) {
  return request({
    url: `/api/orders/${id}/cancel`,
    method: 'post',
    data
  })
}
```

#### React + Axios (TypeScript)

```typescript
// [서비스폴더]/orderService.ts
import axios from '../api/axiosInstance'

export const cancelOrder = async (id: number, data: CancelRequest): Promise<CancelResponse> => {
  const { data: result } = await axios.post<CancelResponse>(`/api/orders/${id}/cancel`, data)
  return result
}
```

#### React Query 포함 시

```typescript
export const useCancelOrder = () => {
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CancelRequest }) =>
      cancelOrder(id, data),
  })
}
```

#### Angular HttpClient

```typescript
// [서비스폴더]/order.service.ts
cancelOrder(id: number, data: CancelRequest): Observable<CancelResponse> {
  return this.http.post<CancelResponse>(`/api/orders/${id}/cancel`, data)
}
```

### 생성 위치 결정

1. 프론트엔드 `.claude/patterns/` 또는 `_workspace/01_analyzer_report.md`에서 서비스 레이어 폴더 패턴 확인
2. 기존 유사 서비스 파일 있으면 그 파일에 함수 추가
3. 없으면 도메인명 기반 신규 파일 생성 (`orderService.ts`, `order.js` 등)

---

## Mode: check-impact (API 변경 → 파트너 영향 확인)

### 입력
- 변경 엔드포인트 정보 (method + path)
- 백엔드 루트 + 프론트엔드 루트 (pair_config.md에서)

### Step 1: 변경 엔드포인트 api_contract 조회

`_workspace/index/api_contract.json`에서 해당 엔드포인트 항목 확인.

### Step 2: 파트너 프론트엔드에서 호출 위치 grep

```
grep -rn "['\"]/api/orders/${id}/cancel['\"]" [프론트엔드 루트]/src/
```
또는 URL 패턴 정규화 후 유사 패턴 검색.

### Step 3: 영향 목록 반환

impact-analyzer의 "## 외부 통신 영향 (파트너 프로젝트)" 섹션에 추가:

```
## 파트너 프로젝트 영향 (프론트엔드)

변경 엔드포인트: [METHOD /path]
프론트엔드 호출 위치:
  - [파일경로:라인] — [함수명]
  - ...
영향받는 컴포넌트: N개
권고: 프론트엔드 [파일 목록] 함께 수정 필요
```

파트너 api_drift_report.md가 있으면 기존 드리프트 현황도 병기.

# Index Specification

`_workspace/index/` 하위 JSON 파일들의 스키마 정의.

analyzer가 생성하고, 후속 에이전트(impact-analyzer, sql-reviewer, change-safety, migration-planner 등)가 조회한다.

---

## 공통 규칙

- 파일 형식: JSON
- 인코딩: UTF-8 (BOM 없음)
- 들여쓰기: 2칸 (압축 안 함, 사람이 검토 가능)
- 용량 한도: 각 파일 종류별 한도 (analyzer.md 참조). 초과 시 분할.

각 인덱스 파일은 최상위에 메타 정보:

```json
{
  "_meta": {
    "generated_at": "2026-06-02T15:30:00Z",
    "generator": "analyzer",
    "version": "1.0",
    "source_root": "/path/to/project",
    "mode": "init|incremental|feature-scoped",
    "git_commit": "abc1234... (git rev-parse HEAD, git 저장소 아니면 null)",
    "sampled": false,
    "files_scanned": 1180,
    "files_total": 1234,
    "node_count": 1234,
    "edge_count": 5678
  },
  "data": [...]
}
```

---

## call_graph.json

호출 관계 그래프.

```json
{
  "_meta": {...},
  "nodes": [
    {
      "id": "com.example.OrderService.cancel",
      "type": "method",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 42,
      "visibility": "public",
      "static": false,
      "annotations": ["@Transactional"],
      "signature": "void cancel(Long orderId)"
    }
  ],
  "edges": [
    {
      "from": "com.example.OrderController.cancel",
      "to": "com.example.OrderService.cancel",
      "type": "call",
      "file": "src/main/java/com/example/OrderController.java",
      "line": 56
    }
  ]
}
```

`type` 값:
- `call` — 메서드 직접 호출
- `inject` — DI 주입 관계 (Spring `@Autowired` 등)
- `inherit` — 상속/구현
- `reflect` — 리플렉션 가능성 (heuristic, 신뢰도 낮음)

---

## symbols.json

모든 클래스/메서드/함수 심볼 인덱스.

```json
{
  "_meta": {...},
  "symbols": [
    {
      "id": "com.example.OrderService",
      "type": "class",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 10,
      "package": "com.example",
      "extends": "AbstractService",
      "implements": ["OrderOperations"],
      "annotations": ["@Service"],
      "methods": [
        {"name": "cancel", "id": "com.example.OrderService.cancel", "line": 42, "visibility": "public"}
      ]
    }
  ]
}
```

언어별 식별자:
- Java: 완전 자격 이름 (`com.example.X.method`)
- Python: 모듈.클래스.함수 (`services.order.OrderService.cancel`)
- JavaScript/TypeScript: 파일경로::심볼명 (`src/services/order.ts::cancelOrder`)
- Go: 패키지.함수 (`services.CancelOrder`)

---

## sql_usage.json

SQL ID ↔ 호출 위치 매핑.

```json
{
  "_meta": {...},
  "sqls": [
    {
      "id": "ORDER_LMS_S01",
      "file": "WEB-INF/config/query/query-order-ora.xml",
      "line": 23,
      "type": "select",
      "tables": ["TBL_ORDER"],
      "columns_selected": ["ORDER_ID", "USER_ID", "STATUS"],
      "columns_where": ["USER_ID", "STATUS"],
      "text_preview": "SELECT ORDER_ID, USER_ID, STATUS FROM TBL_ORDER WHERE USER_ID = ? AND STATUS = ?"
    }
  ],
  "usages": [
    {
      "sql_id": "ORDER_LMS_S01",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 78,
      "method": "com.example.OrderService.findByUser"
    }
  ]
}
```

`type` 값: `select`, `insert`, `update`, `delete`, `ddl`.

`tables`/`columns_*` 는 best-effort 파싱. 동적 SQL은 누락 가능.

---

## schema.json

DB 스키마 스냅샷.

```json
{
  "_meta": {
    ...,
    "source": "live_db|ddl_files|orm_mapping",
    "dialect": "oracle|postgresql|mysql|..."
  },
  "tables": [
    {
      "name": "TBL_ORDER",
      "schema": "PUBLIC",
      "columns": [
        {
          "name": "ORDER_ID",
          "type": "NUMBER(19)",
          "nullable": false,
          "default": null,
          "primary_key": true
        },
        {
          "name": "STATUS",
          "type": "VARCHAR2(20)",
          "nullable": false,
          "default": "'PENDING'"
        }
      ],
      "primary_key": ["ORDER_ID"],
      "foreign_keys": [
        {
          "name": "FK_ORDER_USER",
          "columns": ["USER_ID"],
          "references_table": "TBL_USER",
          "references_columns": ["USER_ID"]
        }
      ],
      "indexes": [
        {
          "name": "IDX_ORDER_USER_STATUS",
          "columns": ["USER_ID", "STATUS"],
          "unique": false
        }
      ],
      "row_count_estimate": 1234567
    }
  ],
  "views": [...],
  "procedures": [...],
  "functions": [...],
  "triggers": [...]
}
```

`source` 값:
- `live_db` — 운영/스테이징 DB read-only 직접 조회
- `ddl_files` — `*.sql`, `V*.sql`, Liquibase changeset 등에서 파싱
- `orm_mapping` — `@Entity` 클래스에서 역추출

`row_count_estimate` 는 live_db 모드일 때만 채워짐.

---

## transactions.json

트랜잭션 경계 식별.

```json
{
  "_meta": {...},
  "boundaries": [
    {
      "id": "tx_001",
      "entry_method": "com.example.OrderService.cancel",
      "file": "src/main/java/com/example/OrderService.java",
      "line": 42,
      "marker": "@Transactional",
      "propagation": "REQUIRED",
      "isolation": "DEFAULT",
      "rollback_for": ["Exception.class"],
      "methods_in_scope": [
        "com.example.OrderService.cancel",
        "com.example.OrderDao.updateStatus",
        "com.example.RefundService.process"
      ],
      "external_io_calls": [
        {"target": "com.example.PaymentGatewayClient.refund", "type": "http"}
      ]
    }
  ]
}
```

`external_io_calls` 는 트랜잭션 경계 안에서의 외부 호출 — 위험 항목.

---

## external_io.json

외부 통신 식별.

```json
{
  "_meta": {...},
  "communications": [
    {
      "id": "ext_001",
      "type": "http",
      "file": "src/main/java/com/example/PaymentClient.java",
      "line": 45,
      "method": "com.example.PaymentClient.charge",
      "target": "https://api.payment.example.com/charge",
      "timeout_ms": 30000,
      "retry_policy": "exponential_backoff(3)",
      "in_transaction": false
    },
    {
      "id": "ext_002",
      "type": "kafka_producer",
      "topic": "orders.events",
      "file": "src/main/java/com/example/OrderEventPublisher.java",
      "line": 12
    },
    {
      "id": "ext_003",
      "type": "file_io",
      "operation": "read",
      "path_pattern": "/data/batch/*.csv",
      "file": "src/main/java/com/example/BatchJob.java",
      "line": 30
    }
  ]
}
```

`type` 값: `http`, `kafka_producer`, `kafka_consumer`, `rabbit_*`, `sqs_*`, `file_io`, `external_db`, `ldap`, `mail`, `redis`, `s3`, etc.

---

## env_branches.json

환경 분기 코드 위치.

```json
{
  "_meta": {...},
  "profiles": ["dev", "stg", "prod"],
  "branches": [
    {
      "file": "src/main/java/com/example/SomeConfig.java",
      "line": 23,
      "type": "annotation",
      "marker": "@Profile(\"prod\")",
      "method": "com.example.SomeConfig.productionOnlyBean"
    },
    {
      "file": "src/main/resources/application.yml",
      "line": null,
      "type": "config_file",
      "marker": "spring.profiles.active",
      "values_per_profile": {
        "dev": "localhost",
        "prod": "prod-db.internal"
      }
    },
    {
      "file": "src/services/feature.ts",
      "line": 12,
      "type": "code_if",
      "marker": "if (process.env.NODE_ENV === 'production')",
      "method": "feature.ts::initialize"
    }
  ]
}
```

---

## dead_code.json

데드 코드 후보 (확정 아님 — 리플렉션 등 동적 호출 가능성).

```json
{
  "_meta": {
    ...,
    "warning": "Static analysis only. Dynamic invocation (reflection, DI by name, external triggers) NOT detected. Verify before removal."
  },
  "unused_methods": [
    {
      "id": "com.example.LegacyService.unusedMethod",
      "file": "src/main/java/com/example/LegacyService.java",
      "line": 88,
      "visibility": "public",
      "reason": "in_degree=0 in call_graph"
    }
  ],
  "unused_sql_ids": [
    {
      "id": "ORDER_LMS_OLD_S01",
      "file": "WEB-INF/config/query/query-order-ora.xml",
      "line": 99,
      "reason": "not referenced in sql_usage"
    }
  ],
  "unused_jsps": [
    {
      "file": "WEB-INF/jsp/back/order/oldList.jsp",
      "reason": "not in any forward path"
    }
  ]
}
```

각 항목에 `reason` 명시. 사용자 검토 후에만 제거.

---

## 인덱스 갱신 정책

| 시나리오 | 동작 |
|---------|------|
| 최초 분석 (init) | 전체 인덱스 생성 |
| incremental | git diff 또는 mtime 비교로 변경 파일만 재분석. 영향받는 노드/엣지만 갱신 |
| feature-scoped | 사용자 지정 범위만. 인덱스에 부분 추가 (기존 데이터 보존) |

인덱스 stale 감지:
- 각 인덱스의 `_meta.generated_at`과 코드 파일 mtime 비교
- 코드 파일이 더 최신이면 stale 경고

---

## 인덱스가 없거나 stale일 때의 fallback

각 에이전트는 인덱스 우선 조회, 없으면 grep fallback:

| 에이전트 | 인덱스 의존 | Fallback |
|---------|---------|---------|
| impact-analyzer | call_graph, sql_usage, schema | grep 호출 패턴 |
| sql-reviewer | sql_usage, schema | grep SQL ID, DDL 파일 파싱 |
| change-safety | call_graph, external_io | impact-analyzer 결과 활용 |
| migration-planner | call_graph, external_io, transactions, dead_code | analyzer 리포트 마크다운만 활용 |

Fallback은 느리고 정확도가 떨어진다. 인덱스 정기 갱신을 권장.

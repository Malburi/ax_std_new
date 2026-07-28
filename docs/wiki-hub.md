# 시스템 위키 중앙 허브 (wiki-hub)

여러 시스템의 harness wiki를 한 DB에 모으고, 하나의 사이트에서 열람·검색·버전 관리하는
구조를 설명한다. **이 기능의 구현은 harness 플러그인 안에 있지 않다.** 별도 프로젝트
`wiki-hub`가 전담하고, harness 쪽은 그 프로젝트의 콘솔 명령을 호출할 뿐이다.

> harness에는 이전부터 있던 v1 단일 테이블 DB 저장(`generate-wiki --storage db` →
> `agents/lib/wiki_db.py` → `harness_wiki_pages` 테이블, `sync-wiki` 스킬)도 그대로 남아
> 있다. 이 문서는 그 위에 추가된 wiki-hub(구조화·버전관리·다중 시스템 통합)를 다룬다 — v1과
> wiki-hub는 대체 관계가 아니라 서로 다른 규모의 요구에 대응하는 별개 기능이다.

---

## 왜 별도 프로젝트인가

harness 플러그인은 Claude Code 마켓플레이스로 설치되어 여러 대상 프로젝트 각각에 흩어져
동작한다. 반면 "여러 시스템의 wiki를 한 곳에 모아 보는 허브"는 그 반대 성격이다 — 한 번
설치해서 계속 떠 있어야 하고, DB 접속 정보·드라이버(pymssql/psycopg2/oracledb)를 팀 공용
서버에 두는 편이 자연스럽다. 이 둘을 한 플러그인 안에 억지로 합치면 harness를 설치할 때마다
불필요한 DB 의존성이 딸려온다.

그래서 구조를 이렇게 나눴다.

```
harness 플러그인 (여러 프로젝트에 각각 설치)     wiki-hub (한 번 설치, 계속 실행)
──────────────────────────────────           ─────────────────────────
generate-wiki                                 wiki-hub-publish  (발행)
  → wiki/ 폴더 생성 (zero-LLM)                  wiki-hub-serve    (열람·검색·버전관리)
                                                    │
publish-wiki 스킬  ─────(콘솔 명령 호출)──────────►│
wiki-hub 스킬      ─────(콘솔 명령 호출)──────────►│
                                                    ▼
                                              MSSQL / PostgreSQL / Oracle / SQLite
```

의존 방향은 한쪽뿐이다. harness의 스킬이 `wiki-hub-publish`/`wiki-hub-serve`를 호출하지만,
wiki-hub 프로젝트는 harness의 코드를 전혀 모른다 — harness 산출물의 **파일 규약**
(`wiki/*.md`·`*.html`, `_workspace/index/*.json`)만 알 뿐이다.

---

## 위키를 보는 세 가지 방법

| | 폴더 wiki | v1 단일 DB wiki | DB(중앙 허브) wiki |
|---|---|---|---|
| 만드는 명령 | `generate-wiki` (harness) | `generate-wiki --storage db` (harness) | `generate-wiki` 다음 `publish-wiki` |
| 저장 위치 | 이 프로젝트의 `wiki/` 폴더 | `harness_wiki_pages` 단일 테이블 | wiki-hub의 중앙 DB |
| 보는 명령 | `wiki/serve.bat` → `:3501` | `agents/lib/wiki_db_server.py` → `:8000` | `wiki-hub-serve` → `:8800` |
| 범위 | 이 프로젝트 하나 | `WIKI_SYSTEM_KEY`로 구분된 프로젝트들(평면) | 발행된 모든 시스템(시스템·컴포넌트로 구조화) |
| 버전 이력 | 없음 | 없음 | 있음 (비교·되돌리기) |

**기본은 폴더다.** `generate-wiki`는 질문 없이 항상 폴더에 wiki를 만든다. v1 DB·wiki-hub 발행은
둘 다 완료 후 선택 질문으로만 나타난다 — 필요할 때만 켜는 상위 계층 기능이다.

---

## wiki-hub의 스키마

시스템/컴포넌트/페이지/버전/구조화 인덱스 전부 `wiki-hub/wikihub/models.py` 한 곳에서
SQLAlchemy Core 테이블로 정의된다. 엔진별 차이(NVARCHAR(MAX)/CLOB/TEXT, IDENTITY 방식,
TOP/LIMIT/FETCH FIRST)는 `.with_variant()`와 `select().limit()`으로 흡수되므로, 이
문서 바깥 어디에도 엔진별 SQL 분기가 없다.

| 테이블 | 담는 것 |
|--------|--------|
| `wikihub_systems` | 시스템 마스터 — 표시이름·설명·담당·태그·보관 여부 |
| `wikihub_components` | 시스템 안의 레이어 — backend/frontend/fullstack/batch/mobile/common |
| `wikihub_pages` | 현재 본문 (시스템·컴포넌트·경로 3키, 체크섬·현재버전) |
| `wikihub_page_versions` | 버전 이력 — 체크섬이 바뀔 때만 새 행 |
| `wikihub_api_endpoints` / `wikihub_db_objects` / `wikihub_frontend_routes` / `wikihub_external_links` | 백엔드·프론트엔드 정보를 문서와 별도로 분리한 구조화 인덱스 |
| `wikihub_publish_log` | 발행 실행 기록 |

버전은 체크섬이 바뀔 때만 늘어난다. 삭제는 표시만 하고 본문·이력은 남긴다. 되돌리기는
과거 버전을 새 버전으로 추가하는 방식이라 이력이 줄지 않는다.

자세한 필드·정책은 `wiki-hub/README.md`와 `wiki-hub/wikihub/store.py`의 문서 주석을 참고한다
(이 파일에서 스키마를 다시 옮겨 적지 않는다 — 소스가 둘이 되면 어긋나기 쉽다).

---

## 지원 DB와 전환 방법

| 엔진 | 드라이버 | 비고 |
|------|---------|------|
| MSSQL | `pymssql` | 1차 대상 |
| PostgreSQL | `psycopg2-binary` | |
| Oracle | `oracledb` (thin — Instant Client 불필요) | |
| SQLite | 표준 라이브러리 | 1인 사용·오프라인·시험 |

`.env`의 `WIKI_DB_ENGINE` 하나만 바꾸면 엔진이 바뀐다. 스키마는 wiki-hub가 최초 접속 시
자동 생성하므로 별도 마이그레이션 스크립트를 손으로 돌릴 필요가 없다.

```ini
WIKI_DB_ENGINE=mssql        # 지금 이렇게 시작해도
WIKI_DB_ENGINE=postgresql   # 나중에 이렇게 바꿀 수 있다 — harness 쪽 스킬은 그대로
```

---

## 설치

harness 플러그인과 별도로 설치한다.

```bash
cd wiki-hub
pip install -e .
pip install -e ".[mssql]"        # 실제 쓸 엔진만 (postgresql / oracle / all 도 가능)
```

설치하면 어디서든 `wiki-hub-publish`, `wiki-hub-serve` 두 명령을 쓸 수 있다.

---

## harness 쪽에서 쓰는 법

1. `generate-wiki` — 폴더 wiki 생성 (항상 실행, 기본값)
2. 완료 후 "중앙 허브에도 발행할까요?" 질문에 Y → `publish-wiki` 스킬 → `wiki-hub-publish` 호출
3. 여러 시스템을 한 곳에서 보고 싶을 때 → `wiki-hub` 스킬 → `wiki-hub-serve` 실행

백엔드·프론트엔드가 별도 저장소면 **양쪽에서 각각 발행**한다 — 같은 `--system-key`,
다른 `--component-type`을 쓰면 허브에서 한 시스템 아래 두 레이어로 묶인다.

예전 harness v1의 단일 테이블(`harness_wiki_pages`) 데이터가 있으면
`wiki-hub-publish --migrate-v1`으로 새 스키마로 옮긴다.

---

## 검증 범위와 한계

wiki-hub 프로젝트 자체의 검증 상세는 `wiki-hub/README.md`의 "검증 범위와 한계" 절을 따른다.
요약하면: SQLite는 실제 접속·CRUD·버전관리·검색까지 end-to-end로, MSSQL/PostgreSQL/Oracle은
SQLAlchemy 오프라인 방언 컴파일까지 검증했다. 실서버 접속은 각자 환경에서 첫 발행 시
`wiki-hub-publish --root . --list`로 먼저 확인할 것을 권한다.

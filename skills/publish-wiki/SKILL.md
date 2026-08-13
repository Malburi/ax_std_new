---
name: publish-wiki
description: 생성된 폴더 wiki를 중앙 DB(MSSQL/PostgreSQL/Oracle/SQLite)에 발행한다. 시스템 단위로 구분하고 백엔드·프론트엔드를 컴포넌트로 분리 저장하며, 내용이 바뀐 페이지만 새 버전으로 쌓는다. API·DB테이블·화면·외부연동은 별도 인덱스 테이블에 함께 적재한다. "wiki 발행", "위키 중앙 DB에 올려줘", "wiki 허브에 등록", "시스템 위키 등록", "publish wiki", "위키 버전 올려줘", "백엔드 프론트엔드 위키 분리 저장" 요청 시 트리거. harness-init·generate-wiki 완료 후 자동 제안.
---

# Publish Wiki (오케스트레이터)

`generate-wiki`가 만든 `_workspace/wiki/` 폴더 + `_workspace/**/*.json`을 중앙 DB에 발행한다.
**DB 저장(쓰기)은 harness 플러그인에 내장된 `agents/lib/wikihub_db/`가 직접 수행한다** — 별도
프로젝트 wiki-hub를 pip install 하지 않아도 된다(대부분의 PC에는 wiki-hub가 설치돼 있지
않으므로, 저장 기능 자체가 그 설치 여부에 좌우되면 안 된다).

`agents/lib/wikihub_db/`는 별도 프로젝트 [wiki-hub](https://github.com/neoruler001/wiki-hub 등
사용자가 배포한 위치)의 스키마·버전관리 로직을 그대로 옮긴 사본이다(models.py/store.py/
config.py/index_extract.py/publish.py, view 전용인 server.py/ui.py/render.py는 제외) — 같은
DB 테이블(`wikihub_*`)에 같은 방식으로 쓰기 때문에, 나중에 wiki-hub가 별도 서버로 떠서
그 DB를 읽어도(view 전용) 완전히 호환된다.

| 축 | 저장 방식 |
|----|---------|
| 시스템 | `wikihub_systems` 마스터에 등록. 시스템 키로 완전히 분리 |
| 컴포넌트 | `wikihub_components` — 같은 시스템 안에서 백엔드·프론트엔드를 나눠 저장 |
| 페이지 | `wikihub_pages` — (시스템, 컴포넌트, 경로) 단위, 체크섬이 바뀔 때만 새 버전. `_workspace/wiki/*.md`·`*.html` 뿐 아니라 `_workspace/**/*.json`(call_graph·schema·sql_usage 등 harness index + writer_decisions.json 등) 원본도 같은 테이블에 함께 발행된다 |
| 버전 | `wikihub_page_versions` — JSON도 동일하게 버전 관리됨 |
| 구조화 정보 | `wikihub_api_endpoints` · `wikihub_db_objects` · `wikihub_frontend_routes` · `wikihub_external_links` |

> **여러 인원이 한 프로젝트를 나눠 맡는 경우**: 한 사람이 harness-init을 돌려 만든
> `_workspace/**/*.json`(분석 인덱스 원본)을 발행해두면, 다른 팀원은 harness-init을 다시
> 돌리지 않고 `--pull`로 그 JSON을 자기 로컬 `_workspace/`의 원래 경로로
> 받아 impact-analyzer 등 에이전트에 바로 재사용할 수 있다.

지원 DB: **MSSQL**(1차 대상) · PostgreSQL · Oracle · SQLite. 하나의 `models.py`로
스키마를 정의하고 SQLAlchemy가 엔진별 SQL로 컴파일하므로, 나중에 MSSQL에서 PostgreSQL이나
Oracle로 옮겨도 `.env`의 `WIKI_DB_ENGINE` 값만 바뀐다.

> harness가 예전에 쓰던 v1 단일 테이블 DB 저장(`--storage db` → `wiki_db.py` → 단일 테이블
> `harness_wiki_pages`)은 제거됐다 — 그 시절 데이터가 남아있으면 아래 "예전 데이터 이관" 절로 옮길 수 있다.

발행된 내용은 나중에 별도 서버에 배포될 wiki-hub 서비스(`wiki-hub-serve`)에서 전 시스템
통합 조회된다 — 이 부분은 [wiki-hub](../wiki-hub/SKILL.md) 스킬 참조(운영 서버 구성은 별도
계획 중이며, 이 스킬(publish-wiki)의 저장 기능과는 무관하게 항상 동작한다).

---

## Phase 0: 필요 패키지 확인

`agents/lib/wikihub_db/`는 harness 플러그인에 이미 포함돼 있어 **추가 설치가 필요 없다** —
`SQLAlchemy` + DB 드라이버(엔진별)만 있으면 된다.

```powershell
python -c "import sqlalchemy"
```

| 결과 | 동작 |
|------|------|
| 정상(에러 없음) | Phase 1로 진행 |
| `ModuleNotFoundError` | 아래 안내 후 사용자 확인을 받고 재시도 |

```
DB 저장에 필요한 파이썬 패키지가 없습니다.

  pip install sqlalchemy

MSSQL을 쓸 경우 드라이버도 추가로 필요합니다: pip install pymssql
(PostgreSQL은 psycopg2-binary, Oracle은 oracledb)

설치 후 다시 요청해주세요.
```

`_workspace/wiki/` 폴더 자체가 없으면 "먼저 `generate-wiki`로 wiki를 생성하세요" 안내 후 중단.

---

## Phase 1: DB 엔진 확인

프로젝트 루트 `.env`의 `WIKI_DB_ENGINE`을 먼저 읽는다. 값이 있으면 재질문하지 않고 그 값을 그대로 쓴다.

없으면 묻는다 (사용자가 "일단 MSSQL, 나중에 다른 DB로 바꿀 수 있어야 한다"고 밝힌 전제에 맞춰
MSSQL을 기본 추천으로 제시하되 강제하지 않는다):

```
wiki를 저장할 DB 엔진을 선택하세요.

1. MSSQL (권장, 팀 공유)      — 드라이버: pymssql
2. PostgreSQL (팀 공유)        — 드라이버: psycopg2-binary
3. Oracle (팀 공유)             — 드라이버: oracledb (Instant Client 불필요)
4. SQLite (1인 사용·오프라인)  — 추가 설치 불필요

선택? (1/2/3/4)
```

선택에 따라 `.env`에 `WIKI_DB_ENGINE=mssql|postgresql|oracle|sqlite`를 쓰고, 해당 엔진에 필요한
접속 정보를 이어서 받는다 (`.env.example` 참고 — 필드명은 엔진마다 다르다: `MSSQL_*` / `PG_*` /
`ORACLE_*` / `WIKI_SQLITE_PATH`). 드라이버가 없으면 스크립트 실행 시 어떤 패키지를
설치해야 하는지 스스로 알려주므로(config.py의 `DRIVER_HINT`), 여기서 미리 pip 설치를 강제하지 않아도 된다.

> **다른 DB로 나중에 바꾸려면** `.env`의 `WIKI_DB_ENGINE`과 해당 엔진 필드만 바꾸면 된다.
  스키마는 최초 접속 시 자동 생성한다 (`CREATE TABLE IF NOT EXISTS` 동등 처리,
  엔진별 문법 차이는 SQLAlchemy가 흡수).

---

## Phase 2: 시스템 키와 컴포넌트 확인

`.env`에 `WIKI_SYSTEM_KEY`가 있으면 "시스템 키: [값] (기존 설정 재사용)"만 알리고 넘어간다. 없으면:

```
이 저장소가 속한 "시스템"의 키를 입력하세요 (예: ORDER, SETTLE, HRMS).

주의. 백엔드와 프론트엔드가 한 시스템이면 양쪽 저장소에 같은 키를 넣어야 합니다.
     레이어 구분은 다음 질문의 컴포넌트로 합니다.

시스템 표시 이름도 함께 알려주시면 허브 목록에 그대로 보입니다 (예: 주문관리시스템).
```

컴포넌트는 `.env`(`WIKI_COMPONENT_KEY`/`TYPE`) → `_workspace/pair_config.md`의 `project_type` →
폴더명 추정 순으로 결정하되, 추정값은 반드시 사용자에게 확인받는다.

```
이 저장소의 레이어를 확인해주세요.

추정 결과: [backend]  (근거: 폴더명)

1. 그대로 사용
2. 다른 값 선택 (backend / frontend / fullstack / batch / mobile / common)
```

---

## Phase 3: 발행 실행

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/wikihub_db/publish.py" --root "[절대경로]" `
  --system-key "[시스템키]" --system-name "[표시이름]" `
  --component-type [backend|frontend|...] --component-key "[컴포넌트키]" `
  --summary "[이번 변경 요약]" --save-env
```

(스크립트는 플러그인 설치 루트에 있다 — PowerShell `$env:CLAUDE_PLUGIN_ROOT`, bash `$CLAUDE_PLUGIN_ROOT`.
비어 있으면 이 SKILL.md가 위치한 플러그인 디렉터리 절대경로로 대체. cwd 상대경로
`agents/lib/...` 금지.)

| 옵션 | 쓰는 때 |
|------|--------|
| `--dry-run` | DB를 건드리지 않고 대상 페이지만 확인 |
| `--no-index` | 구조화 인덱스 추출을 건너뜀 |
| `--no-workspace-json` | `_workspace/**/*.json` 원본 발행을 건너뜀 (위키 문서만 발행) |
| `--pull` | 반대 방향. 위키 문서는 `_workspace/wiki/`로, `_workspace/`로 시작하는 페이지(워크스페이스 JSON)는 프로젝트 루트 기준 **원래 경로**로 복원 |
| `--list` | 등록된 시스템·컴포넌트 확인 |
| `--migrate-v1` | 예전 harness의 단일 테이블(`harness_wiki_pages`) 데이터를 새 스키마로 이관 |

기본값은 발행(둘 다 포함) — 대부분은 옵션 없이 그대로 실행하면 된다.

### 크로스 리포(pair-init) 구조일 때

백엔드·프론트엔드가 별도 저장소면 **양쪽에서 각각 발행**한다. 같은 `--system-key`, 다른
`--component-type`을 쓰면 허브에서 한 시스템 아래 두 레이어로 묶여 보인다.

---

## Phase 4: 결과 보고

스크립트 출력을 그대로 전달하고, 열람 경로를 안내한다.

```
발행 완료

  시스템   : ORDER (주문관리시스템)
  컴포넌트 : backend [backend]  stack=Spring Boot 2.7 / MyBatis
  페이지   : 신규 0 / 변경 3 / 동일 5 / 삭제표시 1 (총 8)
  워크스페이스 JSON : 6개 (위 페이지 수에 포함, 다른 팀원이 harness-init 재실행 없이 재사용 가능한 원본 index 데이터)
  인덱스   : api 4건, db 3건, route 0건, external 2건

내용이 같은 페이지는 새 버전을 만들지 않았습니다. 변경된 3개만 v2가 되었습니다.
_workspace/**/*.json 6개도 함께 발행돼 다른 팀원이 --pull로 원래 경로에 그대로 받을 수 있습니다.
중앙에서 통합 조회하려면 → wiki-hub 스킬로 wiki-hub-serve 실행(별도 서버, 운영 계획 수립 중)
```

---

## 예전 데이터 이관

harness의 예전 단일 테이블(`harness_wiki_pages`, `project_name` 컬럼) 데이터가 있으면 먼저 계획을 확인한다.

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/wikihub_db/publish.py" --root "[절대경로]" --migrate-v1 --dry-run
```

`ORDER-BACKEND` 같은 접미사 키는 `ORDER` / `backend`로 자동 분해된다. 추정이 틀린 항목만 매핑을 준다.

```powershell
python "$env:CLAUDE_PLUGIN_ROOT/agents/lib/wikihub_db/publish.py" --root "[절대경로]" --migrate-v1 --map "HRMS=HRMS:web:fullstack"
```

원본 v1 테이블은 지우지 않는다. 확인한 뒤 사용자가 직접 정리하도록 안내한다.

---

## 원칙

### 저장(쓰기)은 harness에 내장, 조회·관리(읽기)는 별도 wiki-hub 서버
대부분의 PC에는 별도 프로젝트 wiki-hub가 설치돼 있지 않다 — DB 저장 자체가 그 설치 여부에
좌우되면 안 되므로, 스키마·버전관리 로직(`agents/lib/wikihub_db/`)을 harness 플러그인 안에
직접 내장했다(2026-07-31 결정, 이전에는 "DB 코드는 harness 안에 두지 않는다"였음 — 이번에
뒤집었다). wiki-hub(별도 서버, 운영 계획 수립 중)는 같은 DB를 읽어 여러 시스템을 통합
열람·검색·버전관리하는 **조회 전용** 역할만 한다 — 스키마가 완전히 같기 때문에 harness가
쓴 데이터를 wiki-hub가 그대로 읽을 수 있다.

### 시스템 키는 조직의 시스템 단위, 컴포넌트는 레이어 단위
저장소 하나가 시스템 하나인 것이 아니다. 백엔드 저장소와 프론트엔드 저장소가 같은 업무 시스템이면
시스템 키가 같아야 한다. 이 규칙이 깨지면 나중에 wiki-hub에서 한 시스템이 둘로 쪼개져 보인다.

### wiki는 harness 산출물의 스냅샷
발행된 내용은 발행 시점의 사진이다. 영향도 분석·드리프트 검증은 wiki가 아니라
`impact-analyzer`·`api-bridge`의 라이브 재분석으로 한다.

---
name: wiki-hub
description: 별도 프로젝트 wiki-hub를 실행해 여러 시스템의 wiki를 한 사이트에서 통합 열람·검색·관리한다. 시스템 목록, 백엔드/프론트엔드 컴포넌트 구분, 전 시스템 문서 전문 검색, API·DB테이블·화면·외부연동 교차 인덱스, 페이지별 버전 이력·비교·복원을 제공한다. "위키 허브 띄워줘", "통합 위키 보여줘", "시스템 위키 목록", "wiki 검색", "위키 버전 비교", "이전 버전으로 되돌려줘", "wiki hub", "중앙 위키 관리", "DB 위키 보여줘" 요청 시 트리거.
---

# Wiki Hub (오케스트레이터)

`publish-wiki`(= `wiki-hub-publish`)로 발행된 모든 시스템의 wiki를 한 사이트에서 다룬다.
읽기 전용 뷰어가 아니라 **관리 도구**다. 검색·버전 비교·복원·시스템 정보 편집을 포함한다.

이 스킬이 실행하는 `wiki-hub-serve`는 harness 플러그인이 아니라 **별도 프로젝트 wiki-hub**의
콘솔 명령이다. harness는 폴더 wiki만 만들고, DB에 쌓인 wiki를 보는 화면은 전부 이쪽에 있다.

> harness에는 이전부터 있던 v1 단일 테이블 DB 저장(`generate-wiki --storage db` +
> `agents/lib/wiki_db_server.py`, `sync-wiki` 스킬)도 그대로 남아 있다. v1은 이 프로젝트
> 하나만 별도 로컬 서버로 보는 용도이고, wiki-hub는 여러 시스템을 버전 관리와 함께 한 곳에서
> 보는 용도다 — 서로 대체 관계가 아니라 각자 다른 규모의 요구에 대응한다.

---

## 위키를 보는 방법 세 가지

harness가 만드는 wiki는 저장 위치에 따라 보는 방법이 다르다. 사용자가 "위키 보여줘"라고만
말하면 어느 쪽을 원하는지 확인한다.

| | 폴더 wiki | v1 단일 DB wiki | DB(중앙 허브) wiki |
|---|---|---|---|
| 저장 위치 | 이 프로젝트의 `wiki/` 폴더 | 이 프로젝트가 접속한 MSSQL의 `harness_wiki_pages` 단일 테이블 | wiki-hub의 중앙 DB (여러 프로젝트 공유) |
| 보는 방법 | `wiki/serve.bat` 실행 → `http://localhost:3501` | `agents/lib/wiki_db_server.py` 실행 → `http://localhost:8000` | `wiki-hub-serve` 실행 → `http://localhost:8800` |
| 범위 | 이 프로젝트 하나 | `WIKI_SYSTEM_KEY`로 구분된 프로젝트들(평면) | 발행된 모든 시스템 (시스템·컴포넌트로 구조화) |
| 버전 이력 | 없음 (매번 덮어씀) | 없음 (매번 upsert) | 있음 (비교·되돌리기 가능) |
| 만드는 스킬 | `generate-wiki` | `generate-wiki --storage db` | `generate-wiki` 다음 `publish-wiki` |

**"이 프로젝트 wiki만 보고 싶다"** → `generate-wiki`가 이미 만든 `wiki/serve.bat` 안내로 끝. 이 스킬은
필요 없다.
**"여러 시스템을 한 곳에서 보고 싶다" / "버전 이력을 보고 싶다"** → 이 스킬(`wiki-hub-serve`)로 진행.
**"기존에 DB로 저장한 걸 계속 그대로 보고 싶다"** → `sync-wiki` 스킬(v1) 안내.

---

## Phase 0: wiki-hub 설치·데이터 확인

```powershell
wiki-hub-serve --help
```

명령이 없으면 `publish-wiki` 스킬의 Phase 0과 같은 설치 안내를 먼저 한다 (별도 프로젝트라 harness와
따로 `pip install -e .` 필요).

허브는 **발행된 데이터만** 보여준다. 아직 아무 시스템도 발행하지 않았다면 `publish-wiki`를 먼저 안내한다.

---

## Phase 1: 허브 실행

```powershell
wiki-hub-serve --root "[절대경로]" --port 8800
```

`--root`는 접속 정보(`.env`)가 있는 폴더다 — 보통 지금 발행한 harness 프로젝트 루트를 그대로 쓴다.
여러 프로젝트가 같은 DB를 공유하므로 어느 프로젝트 루트에서 실행해도 등록된 시스템은 전부 보인다.

| 옵션 | 설명 |
|------|------|
| `--engine` | `.env`의 `WIKI_DB_ENGINE`을 1회성으로 덮어씀 (mssql/postgresql/oracle/sqlite) |
| `--host 0.0.0.0` | 팀에 공유 (인증 없음 — 사내망 안에서만) |
| `--read-only` | 되돌리기·정보 수정 비활성화 (열람 전용 배포용) |
| `--port` | 기본 8800 |

실행 후 브라우저로 `http://127.0.0.1:8800` 접속을 안내한다. 종료는 Ctrl+C.

---

## Phase 2: 화면 안내

| 하려는 일 | 화면 |
|---------|------|
| 어떤 시스템이 등록돼 있나 | `/` — 시스템 카드, 색 배지가 레이어 |
| 한 시스템의 구성과 페이지 | `/s/[시스템키]` — 컴포넌트 표 + 페이지 목록 + 정보 편집 |
| 문서 내용에서 찾기 | `/search` — 전 시스템 본문 검색, 시스템·레이어로 좁힐 수 있음 |
| 이 API를 누가 쓰나 | `/index/api` |
| 이 테이블을 누가 쓰나 | `/index/db` |
| 어떤 화면이 어떤 API를 부르나 | `/index/route` |
| 외부 시스템 연동 지점 | `/index/external` |
| 최근에 뭐가 바뀌었나 | `/changes` |
| 페이지 내용 보기 | `/page/[시스템]/[컴포넌트]/[경로]` (`?v=N`으로 특정 버전) |

허브 화면은 외부 CDN을 쓰지 않는다(서버가 직접 렌더링) — 폐쇄망에서도 그대로 뜬다.

---

## Phase 3: 버전 관리 작업

### 이력·되돌리기

`/history/[시스템]/[컴포넌트]/[페이지]`에서 버전을 최신순으로 본다. "v(이전)과 비교"로 diff를 보고,
"이 버전으로 되돌리기"를 누르면 **새 버전이 하나 더 쌓인다** (이력이 줄지 않는다).

### 되돌린 내용을 실제 프로젝트로 가져오기

허브에서 되돌린 것은 DB 안의 내용이다. harness 프로젝트 폴더에도 반영하려면 회수한다.

```powershell
wiki-hub-publish --root "[절대경로]" --system-key "[시스템키]" --component-key "[컴포넌트키]" `
  --pull --wiki-dir "[절대경로]/wiki"
```

> 다음 `generate-wiki`를 실행하면 harness 산출물 기준으로 다시 덮어써진다. 되돌리기는 문서 이력
  추적용이지 소스 코드 롤백이 아니다.

---

## Phase 4: 시스템 목록 관리

`/s/[시스템키]` 상단 폼에서 표시 이름·설명·담당·태그를 고친다. 여기서 고친 표시 이름은 다음 발행 때
`--system-name`을 다시 주지 않는 한 되돌아가지 않는다.

운영이 끝난 시스템은 같은 폼의 "보관"으로 목록에서 내린다. 데이터는 지워지지 않는다.

---

## 원칙

### 허브는 발행된 것만 보여준다
코드를 다시 읽지 않는다. 화면이 옛날 내용이면 그 시스템에서 `generate-wiki` → `publish-wiki`를
다시 돌려야 한다.

### 인덱스 표는 스냅샷이다
`/index/*`의 API·테이블 목록은 발행 시점 값이다. 실제 영향도 판단은 `impact-analyzer`와
`api-bridge`의 라이브 재분석으로 한다.

### DB 엔진을 바꿔도 이 스킬은 그대로다
MSSQL에서 PostgreSQL이나 Oracle로 옮기더라도 `wiki-hub-serve --root ...` 실행법은 같다.
`.env`의 `WIKI_DB_ENGINE`만 바뀐다 — wiki-hub가 SQLAlchemy로 방언 차이를 흡수하기 때문이다.

---
name: sync-wiki
description: 시스템 wiki를 폴더(wiki/)와 MSSQL DB(harness_wiki_pages) 사이에서 서로 변환한다. "wiki DB로 저장해줘", "wiki 폴더로 내보내줘", "DB wiki를 폴더로 옮겨줘", "폴더 wiki를 DB에 넣어줘", "wiki 저장 위치 바꿔줘", "sync wiki", "wiki DB 백업", "wiki를 DB에서 볼 수 있게 해줘" 요청 시 트리거.
---

# Sync Wiki (오케스트레이터)

`generate-wiki`로 만든 시스템 wiki는 폴더(`wiki/`) 또는 MSSQL DB(`harness_wiki_pages` 테이블) 중
한쪽에 저장된다. 이 스킬은 **이미 만들어진 wiki를 다른 저장 방식으로 옮기는** 용도다 — 재생성(harness
산출물 재분석)이 아니라 `agents/lib/wiki_db.py`를 이용한 순수 파일 <-> DB 복사.

---

## Phase 0: 방향 확인

사용자 요청에서 방향이 명확하면 스킵. 그렇지 않으면:

```
wiki 동기화 방향을 선택하세요:

1. 폴더 → DB   ("wiki/ 폴더 내용을 DB에 저장, 이후 웹 브라우저로 DB에서 조회")
2. DB → 폴더   ("DB에 저장된 wiki를 wiki/ 폴더로 다시 파일화")

선택? (1/2)
```

### 사전 확인

| 방향 | 확인 대상 | 없을 경우 |
|------|---------|---------|
| 폴더 → DB | `wiki/` 폴더 존재 | "먼저 `generate-wiki`로 wiki를 생성하세요" 안내 후 중단 |
| 폴더 → DB, DB → 폴더 공통 | 프로젝트 루트 `.env` (MSSQL_HOST/PORT/USER/PASSWORD/DATABASE) | "`.env`에 MSSQL 접속 정보가 없습니다. HOST/PORT/USER/PASSWORD/DATABASE를 추가하세요" 안내 후 중단 |
| DB → 폴더 | 조회 대상 시스템 키 확정 (아래 "시스템 키 확인" 참조) | DB에 해당 키의 페이지가 없으면 "DB에 저장된 wiki가 없습니다" 안내 후 중단 |

### 시스템 키 확인

여러 시스템이 같은 DB를 공유하므로, 방향별로 시스템 키를 다르게 다룬다:

| 방향 | 동작 |
|------|------|
| 폴더 → DB | `.env`에 `WIKI_SYSTEM_KEY` 있으면 재사용. 없으면 generate-wiki와 동일한 질문으로 입력받아 `.env`에 저장 후 진행 |
| DB → 폴더 | `.env`에 `WIKI_SYSTEM_KEY` 있으면 그 값을 기본 제안하되, "다른 시스템의 wiki를 가져올 수도 있으므로" 먼저 `python agents/lib/wiki_db.py --root "[절대경로]" --list-systems` 결과를 보여주고 "가져올 시스템 키를 선택/입력하세요"라고 질문. 이 값은 **`.env`에 저장하지 않고** `--system-key` 1회성 override로만 사용 |

---

## Phase 1: 동기화 실행

### 폴더 → DB

```powershell
python agents/lib/wiki_db.py --root "[절대경로]" --wiki-dir "[절대경로]/wiki" --direction to-db
```

`.env`에 `WIKI_SYSTEM_KEY`가 이미 있으면 자동 사용되므로 인자 불필요. (앞서 시스템 키를 새로 입력받아
`.env`에 막 저장한 직후라면 그대로 위 명령 실행.)

- `wiki/` 안의 `.md`/`.html` 페이지를 전부 upsert. DB에는 있지만 폴더에는 없는 페이지는 삭제(완전 동기화).
- `wiki/lib/`(vis-network 정적 파일)는 DB에 저장하지 않음 — 조회 시 `wiki_db_server.py`가 플러그인 자체에서 서빙.

### DB → 폴더

```powershell
python agents/lib/wiki_db.py --root "[절대경로]" --wiki-dir "[절대경로]/wiki" --direction to-folder --system-key "[선택된 시스템 키]"
```

- 기존 `wiki/` 폴더가 있으면 먼저 `wiki_prev/`로 백업 여부 확인 (generate-wiki Phase 0과 동일 원칙).
- DB의 모든 페이지를 `.md`/`.html` 원본으로 복원 + `lib/` 정적 파일 재생성 + `wiki/_html/*.html`·
  `wiki/index.html`(브라우저 열람용 정적 렌더) 자동 생성.

---

## Phase 2: 결과 보고

명령 출력(stdout)을 그대로 사용자에게 전달:

```
[폴더 → DB]
DB 저장 완료: [host]:[port]/[database] — N개 페이지 (project=[project_name])
브라우저 확인: python agents/lib/wiki_db_server.py --root "[절대경로]" 실행 후 http://localhost:8000

[DB → 폴더]
폴더 복원 완료: [wiki_dir] — N개 페이지 (project=[project_name])
열기 방법: wiki/serve.bat 실행 후 http://localhost:3501 (Docsify — 인터넷 CDN 필요, file:// 직접 열기는 미지원)
  단, wiki/_html/*.html 개별 페이지는 서버 없이 더블클릭으로도 열람 가능
```

---

## 원칙

### 동기화는 최신 쪽이 이긴다 (완전 덮어쓰기)
방향의 반대쪽 저장소 내용은 그대로 덮어써진다. 폴더→DB 시 폴더에 없는 DB 페이지는 삭제되고,
DB→폴더 시 폴더의 기존 내용은 DB 내용으로 대체된다. 되돌릴 수 없으므로 실행 전 방향을 반드시 확인.

### DB 조회는 서빙 시점 렌더링, 폴더는 정적 파일 + Docsify index.html
DB에 저장된 wiki는 `agents/lib/wiki_db_server.py`가 요청 시점에 페이지를 렌더링해 서빙한다
(markdown은 이스케이프 후 `<pre>`로 표시, call-graph.html은 그대로 서빙). 폴더 모드(`generate-wiki`의
폴더 저장, 그리고 `wiki_db.py --direction to-folder`로 DB에서 내려받은 결과 모두)는 같은 렌더 방식
(`agents/lib/wiki_render.py` 공용)으로 `wiki/_html/*.html`(서버 없이 더블클릭 열람 가능)을 미리 구워둔다.
`wiki/index.html`은 [2026-07-15]부터 Docsify 기반이라 예외 — `serve.bat` 실행 후 브라우저로 접속 필요
(인터넷 CDN 의존, file://는 미지원).

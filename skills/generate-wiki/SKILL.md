---
name: generate-wiki
description: harness 산출물(_workspace + .claude)을 기반으로 프로젝트 wiki 페이지 세트를 생성한다. call_graph.json을 vis-network 기반 인터랙티브 HTML(call-graph.html)로 변환하는 것을 포함. "wiki 만들어줘", "wiki 생성", "문서 wiki", "프로젝트 wiki 생성", "위키 만들어줘", "generate wiki", "위키 업데이트", "call graph 시각화", "호출 그래프 wiki" 요청 시 트리거. harness-init 완료 후 자동 제안.
---

# Generate Wiki (오케스트레이터)

`wiki_generator.py`(zero-LLM)가 `_workspace/`·`.claude/` 산출물을 그대로 wiki 페이지로 복사/집계하고,
구조화 JSON(`api_contract.json`/`schema.json`/`external_io.json` 등)은 표로 변환한다. LLM 호출 없음.
`_workspace/pair_config.md`(크로스 리포 연동)가 있으면 architecture/api-endpoints/database/external-systems
4개 페이지에 파트너 저장소 데이터가 자동 병합된다 (call-graph.html의 파트너 그래프 병합과 동일한 원리 — 어느 쪽에서 실행해도 통합됨).

---

## Phase 0: 사전 확인

### harness 존재 확인

| 확인 대상 | 없을 경우 |
|---------|---------|
| `_workspace/01_analyzer_report.md` | "harness-init을 먼저 실행해주세요" 안내 후 중단 |
| `CLAUDE.md` | 경고만 표시, 계속 진행 |

### 기존 wiki 감지

`wiki/` 폴더가 이미 존재하면:

```
기존 wiki가 발견되었습니다 (wiki/ 폴더).
덮어쓰시겠습니까? (Y/N)
  Y: 기존 wiki/ → wiki_prev/ 로 백업 후 재생성
  N: 중단
```

사용자 확인 후 진행.

---

## Phase 1: 페이지 범위 확인

기본적으로 발견된 데이터 기반으로 자동 결정하지만, 사용자가 범위를 지정할 수 있다.

---

## Phase 1.5: 저장 위치 선택

```
시스템 wiki를 어디에 저장할까요?

1. 폴더 (기본) — wiki/ 폴더에 파일로 저장, Docsify 기반(wiki/serve.bat 실행 후 http://localhost:3501)으로 열람 (인터넷 CDN 필요, file:// 직접 열기는 미지원)
2. DB (MSSQL) — 프로젝트 루트의 .env(MSSQL_HOST/PORT/USER/PASSWORD/DATABASE) 접속 정보로
   harness_wiki_pages 테이블에 저장. 조회는 agents/lib/wiki_db_server.py 로컬 서버로 브라우저 열람.
   (wiki/ 폴더는 빌드 스테이징 겸 로컬 캐시로 계속 남음)

선택? (1/2)
```

| 선택 | `wiki_generator.py --storage` |
|------|------|
| 1 / 폴더 | `folder` (기본값 — 생략 가능) |
| 2 / DB | `db` |

`.env` 없거나 접속 실패 시 → wiki_generator.py가 폴더 저장은 그대로 완료하고 `07_wiki_build.md`에 DB 실패 사유만 기록한다 (전체 실패로 처리하지 않음). 해당 경우 사용자에게 `.env` 설정 확인 안내.

### DB 선택 시 — 시스템 키 확인

여러 시스템(백엔드/프론트엔드, 또는 서로 다른 프로젝트)의 wiki가 같은 DB에 쌓이므로,
프로젝트 루트 `.env`에 `WIKI_SYSTEM_KEY`가 이미 있는지 먼저 확인한다.

| 상태 | 동작 |
|------|------|
| `.env`에 `WIKI_SYSTEM_KEY` 있음 | "시스템 키: [값] (기존 설정 재사용)" 안내만 하고 재질문 없이 진행 |
| 없음 | 아래 질문 후 응답을 `.env`에 저장하고 진행 |

```
이 시스템을 DB에서 구분할 고유 키를 입력하세요 (예: ORDER-BACKEND, ORDER-FRONTEND).
다른 시스템과 겹치지 않는 이름을 권장합니다.
(미입력 시 폴더명 "[basename]"을 사용 — 다른 시스템도 폴더명이 같으면 데이터가 섞일 수 있습니다)
```

응답을 `.env`에 `WIKI_SYSTEM_KEY=[값]`으로 저장(이미 있으면 덮어쓰지 않음 — 기존 시스템 키가 실수로
바뀌는 사고 방지). 이후 `wiki_generator.py`는 `.env`를 다시 읽으므로 별도 인자 전달 불필요.

---

## Phase 2: wiki_generator.py 실행

LLM 호출 없이, 다음 터미널 명령 한 번으로 wiki 페이지 + 인터랙티브 호출 그래프를 생성한다.

```powershell
python agents/lib/wiki_generator.py --root "[절대경로]" --wiki-dir "[절대경로]/wiki" --storage [folder|db]
```

---

## Phase 3: 결과 보고

`_workspace/07_wiki_build.md`를 읽어 요약 보고:

```
wiki 생성 완료

출력 위치: wiki/
열기 방법: wiki/serve.bat 실행 후 브라우저로 http://localhost:3501 접속 (Docsify 기반 — 인터넷 CDN 필요, file:// 직접 열기는 미지원)
  - wiki/_sidebar.md, wiki/_navbar.md: Docsify 네비게이션
  - wiki/_html/*.html: Home·architecture·workflows 등 페이지의 서버 없는 열람용 렌더 사본 (원본은 wiki/*.md 그대로 유지)
  - wiki/call-graph.html: 데이터가 파일 안에 인라인으로 포함된 완전 독립 페이지 (file://로 직접 열람 가능)
```

DB 저장을 선택한 경우, `07_wiki_build.md`의 "저장 위치" 줄(페이지 수·project_name·`wiki_db_server.py` 실행 명령)을 그대로 포함해 보고.

`pair_config.md`가 있으면 `07_wiki_build.md`의 "크로스 리포 병합" 줄 2개(call-graph.html 노드/엣지 병합 + architecture/api-endpoints/database/external-systems markdown 페이지 병합)를 그대로 포함해 보고 (병합 성공 시 파트너 노드/추론된 크로스 엣지 수 또는 병합된 페이지 목록, 스킵 시 사유).

이후 DB ↔ 폴더 저장 위치를 바꾸고 싶으면 `sync-wiki` 스킬 안내.

---

## 원칙

### wiki는 산출물의 뷰, 소스는 harness
wiki 파일은 `_workspace/`·`.claude/`에서 *생성*된다.  
wiki 파일을 직접 편집해도 다음 `generate-wiki` 실행 시 덮어씌워진다.

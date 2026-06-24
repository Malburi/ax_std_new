---
name: harness-clean
description: 현재 프로젝트에 설치된 harness 파일 전체를 제거한다. "하네스 삭제", "하네스 제거", "harness 지워줘", "harness clean", "harness remove", "harness uninstall", "초기화 되돌려줘", "harness 롤백" 요청 시 사용. gemini.md · .gemini/skills/ · .gemini/agents/ · .gemini/patterns/ · _workspace/ 를 정리한다.
---

# Harness Clean — 하네스 전체 제거

현재 프로젝트에 harness-ito가 생성한 파일들을 안전하게 제거한다.

**원칙: 삭제 전 반드시 목록을 보여주고 사용자 확인을 받는다. 자동 삭제 없음.**

---

## Step 1: 작업 디렉토리 확인

`pwd`로 절대 경로 확보.  
harness가 설치된 프로젝트 루트인지 확인 (gemini.md 또는 `.gemini/` 존재 여부).

harness 흔적이 없으면: "이 디렉토리에 harness가 설치되어 있지 않습니다." 안내 후 종료.

---

## Step 2: 삭제 대상 탐지

다음 경로를 Glob으로 확인해 존재하는 항목만 목록화:

```
삭제 대상 (harness-ito 생성 파일):

[프로젝트 harness 파일]
- gemini.md                          ← harness가 생성한 경우만
- .gemini/skills/trace.md
- .gemini/skills/scaffolder.md
- .gemini/skills/find-logic.md
- .gemini/skills/analyze-impact.md
- .gemini/skills/safe-modify.md
- .gemini/skills/scaffold-feature.md
- .gemini/skills/plan-migration.md
- .gemini/skills/review-sql.md
- .gemini/skills/trace-logic.md
- .gemini/skills/find-feature.md
- .gemini/agents/domain-expert.md
- .gemini/patterns/                  ← 하위 파일 전체
- .gemini/backup/                    ← 하위 파일 전체

[분석 산출물]
- _workspace/                        ← 하위 파일 전체
```

**gemini.md 주의:** "## 변경 이력" 섹션에 harness-fin 항목이 있으면 harness가 생성한 것으로 판단. 없으면 사용자 작성 파일일 수 있으므로 gemini.md는 별도 확인 항목으로 분리.

---

## Step 3: 사용자에게 목록 제시 + 확인 요청

탐지된 파일 목록을 다음 형식으로 출력:

```
다음 파일/폴더를 삭제합니다:

[harness 파일]
  ✓ .gemini/skills/trace.md
  ✓ .gemini/skills/analyze-impact.md
  ... (존재하는 항목만)

[분석 산출물]
  ✓ _workspace/ (하위 N개 파일)

[별도 확인 필요]
  ? gemini.md — harness가 생성한 것으로 보입니다. 함께 삭제할까요?

백업 위치: .gemini/backup/ 이 있으면 함께 삭제됩니다.

계속하려면 "삭제" 또는 "yes"를 입력해주세요.
gemini.md도 함께 삭제하려면 "전체 삭제"를 입력해주세요.
취소하려면 다른 내용을 입력해주세요.
```

---

## Step 4: 삭제 실행

사용자가 "삭제" 또는 "yes" 입력 시:

```bash
# PowerShell
Remove-Item -Recurse -Force .gemini/skills/trace.md (존재하는 파일만)
Remove-Item -Recurse -Force .gemini/skills/scaffolder.md
... (탐지된 파일 각각)
Remove-Item -Recurse -Force .gemini/patterns/
Remove-Item -Recurse -Force .gemini/backup/
Remove-Item -Recurse -Force _workspace/
```

"전체 삭제" 입력 시 위 + gemini.md 추가 삭제.

`.gemini/` 디렉토리가 비어있으면 디렉토리도 함께 제거.

취소 입력 시: "취소됐습니다." 안내 후 종료.

---

## Step 5: 완료 보고

```
harness 제거 완료

삭제된 항목:
  - .gemini/skills/ (N개 파일)
  - .gemini/agents/domain-expert.md
  - .gemini/patterns/ (N개 파일)
  - _workspace/ (N개 파일)
  - gemini.md (전체 삭제 선택 시)

남아있는 항목:
  - gemini.md (삭제 제외 선택 시)

플러그인 제거 (선택):
  harness-ito 플러그인 자체를 제거하려면 gemini Code에서 아래 명령을 실행하세요:
  /plugin uninstall harness-ito
```

---

## 에러 핸들링

| 상황 | 대응 |
|------|------|
| 파일 삭제 권한 없음 | 해당 파일 건너뛰고 목록에 "삭제 실패" 표시 |
| `.gemini/` 에 harness 외 파일 존재 | `.gemini/` 디렉토리 자체는 삭제하지 않음. 개별 파일만 삭제 |
| `_workspace/` 에 사용자 파일 혼재 의심 | harness 산출물 파일명(01_analyzer_report.md 등)만 삭제. 나머지는 보존 |
| git 추적 파일 삭제 시 | 삭제 전 "git에서 추적 중인 파일입니다. 삭제 후 git rm 또는 commit이 필요합니다." 안내 |

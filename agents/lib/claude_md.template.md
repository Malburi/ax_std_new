# CLAUDE.md

{{PROJECT_NAME}} — {{ONE_LINE_DESC}}

## 기술 스택
{{TECH_STACK_SUMMARY}}

## 요청 흐름
{{REQUEST_FLOW}}

## 주요 파일 위치
| 레이어 | 경로 |
|--------|------|
{{FILE_LOCATIONS_ROWS}}

## 빌드 / 실행
{{BUILD_RUN}}

## 자동 워크플로우
| 상황 | 스킬 |
|------|------|
| 요청 흐름 추적, URL 추적 | trace |
| 로직 위치 탐색 | find-logic |
| 기본 신규 파일 체크리스트 | scaffolder |
| **변경 영향도 분석** | analyze-impact |
| **안전한 변경 진행** | safe-modify |
| **컨벤션 따라 신규 기능 생성** | scaffold-feature |
| **마이그레이션 계획** | plan-migration |
| **SQL 영향도/리뷰** | review-sql |
| **전체 스택 기능 생성 (pair 연동 시)** | cross-repo-scaffold |
| **기존 기능 개선/수정 양쪽 저장소 반영 (pair 연동 시)** | cross-repo-modify |

## 작업 시 주의사항
{{CAUTIONS}}
{{PARTNER_SECTION}}
## 변경 이력
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| {{GENERATION_DATE}} | 초기 구성 (analyzer 출력 기반) | 전체 | harness-fin v1 적용 |

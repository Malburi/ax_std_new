import os
import re
import sys
import json
import argparse
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 정적 워크플로우 스킬(analyze-impact/safe-modify/scaffold-feature/plan-migration/review-sql)은
# 프로젝트별 변수가 없는 고정 텍스트다 (agents/writer.md 참조). LLM이 매번 손으로 옮겨 적을 필요 없이
# 이 스크립트가 agents/lib/skills/*.template.md 를 그대로 대상 프로젝트에 복사한다.
# CLAUDE.md는 골격(고정 워크플로우 표·변경이력 헤더)만 템플릿화하고 writer가 채운 소수 필드를
# claude_md_fields.json으로 넘겨받아 조립한다. domain-expert.md는 analyzer_report 그대로 복사.
# trace.md / scaffolder.md / find-logic.md / patterns/ 스켈레톤은 프로젝트별 내용이 실제로
# 달라지므로 writer 에이전트가 계속 직접 작성한다 (이 스크립트 대상 아님).

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(LIB_DIR, "skills")

ALWAYS_DEPLOY = ["analyze-impact", "safe-modify", "scaffold-feature"]
CONDITIONAL_DEPLOY = ["plan-migration", "review-sql"]


def decision_for(skill_name, summary_text):
    """_workspace/02_writer_files.md의 '선택적 스킬 생성 결정' 라인에서 생성 여부를 읽는다.
    라인이 없거나 요약 파일이 없으면 안전하게 미생성으로 처리한다."""
    if not summary_text:
        return False
    m = re.search(rf"^-\s*{re.escape(skill_name)}\.md\s*:\s*(.+)$", summary_text, re.MULTILINE)
    if not m:
        return False
    return "생성" in m.group(1) and "미생성" not in m.group(1)


DOMAIN_EXPERT_DESC = (
    "{project_name} 프로젝트의 코드베이스 분석 결과(스택·아키텍처·의존성·데이터 흐름·"
    "트랜잭션·외부 통신)를 전부 갖고 있는 도메인 지식 에이전트. 비즈니스 로직·아키텍처 "
    "관련 질문이나 다른 에이전트가 프로젝트 맥락이 필요할 때 참조한다."
)


def deploy_domain_expert(root, summary_text):
    """domain-expert.md = _workspace/01_analyzer_report.md를 시스템 프롬프트에 주입한 파일.
    writer가 같은 내용을 다시 타이핑해 출력하는 건 100% 중복 낭비이므로, 여기서 파일 복사로 만든다."""
    report_path = os.path.join(root, "_workspace", "01_analyzer_report.md")
    if not os.path.isfile(report_path):
        print(f"WARN: {report_path} 없음 — domain-expert.md 스킵 (writer가 analyzer_report를 먼저 생성해야 함)", file=sys.stderr)
        return False

    with open(report_path, "r", encoding="utf-8") as f:
        report = f.read()

    project_name = os.path.basename(os.path.normpath(root)) or "프로젝트"
    frontmatter = (
        "---\n"
        "name: domain-expert\n"
        f"description: {DOMAIN_EXPERT_DESC.format(project_name=project_name)}\n"
        "---\n\n"
        f"# Domain Expert — {project_name}\n\n"
        "> 이 파일은 `_workspace/01_analyzer_report.md`를 그대로 주입한 것입니다. "
        "코드 변경 후 `\"인덱스만 갱신해줘\"`로 analyzer를 재실행하면 이 파일도 함께 갱신하세요.\n\n"
        "---\n\n"
    )

    agents_dir = os.path.join(root, ".claude", "agents")
    os.makedirs(agents_dir, exist_ok=True)
    with open(os.path.join(agents_dir, "domain-expert.md"), "w", encoding="utf-8") as f:
        f.write(frontmatter + report)
    return True


def parse_pair_config(root):
    """_workspace/pair_config.md (단순 key: value 마크다운) 파싱. 없으면 None."""
    path = os.path.join(root, "_workspace", "pair_config.md")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    cfg = {}
    for key in ["project_type", "partner_type", "partner_root", "partner_workspace",
                "partner_stack", "api_base_url", "api_contract_path",
                "partner_api_contract", "linked_at"]:
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
        if m:
            cfg[key] = m.group(1).strip()
    return cfg or None


def build_partner_section(root):
    """pair_config.md가 있으면 '## 파트너 프로젝트' 섹션을 그 필드값만으로 조립한다 (LLM 불필요 — 전부 pair_config.md에 이미 있는 값)."""
    cfg = parse_pair_config(root)
    if not cfg:
        return ""
    return (
        f"\n## 파트너 프로젝트 ({cfg.get('partner_type', '미상')})\n\n"
        f"- 파트너 경로: {cfg.get('partner_root', '미상')}\n"
        f"- 스택: {cfg.get('partner_stack', '미상')}\n"
        f"- API 계약: `{cfg.get('api_contract_path', '_workspace/index/api_contract.json')}`\n"
        f"- 연동일: {cfg.get('linked_at', '미상')}\n\n"
        "### 크로스 리포 워크플로우\n"
        "| 상황 | 명령 |\n"
        "|------|------|\n"
        '| 전체 스택 기능 동시 생성 | "전체 스택 기능 만들어줘" → cross-repo-scaffold |\n'
        '| 기존 기능 개선/수정 양쪽 반영 | "이 기능 개선해줘 (프론트도 같이)" → cross-repo-modify |\n'
        '| API 변경 전 파트너 영향 확인 | "영향도 분석해줘" → analyze-impact |\n'
        '| API 드리프트 재확인 | "API 드리프트 확인해줘" → pair-init 재실행 |\n'
        '| 프론트 서비스 스텁만 생성 | "프론트 스텁 만들어줘" → api-bridge |\n\n'
    )


def deploy_claude_md(root):
    """writer가 낸 _workspace/claude_md_fields.json(소수 필드) + claude_md.template.md(고정 골격)를
    조립해 CLAUDE.md를 만든다. 워크플로우 표·변경이력 헤더처럼 프로젝트 무관 고정 텍스트를
    writer가 매번 재작성하던 부분을 없앤 것 — 서술형 필드 값 자체는 여전히 writer(LLM)가 채운다."""
    fields_path = os.path.join(root, "_workspace", "claude_md_fields.json")
    if not os.path.isfile(fields_path):
        print(f"WARN: {fields_path} 없음 — CLAUDE.md 스킵 (writer가 claude_md_fields.json을 먼저 생성해야 함)", file=sys.stderr)
        return False

    template_path = os.path.join(LIB_DIR, "claude_md.template.md")
    if not os.path.isfile(template_path):
        print(f"WARN: 템플릿 없음 — {template_path}", file=sys.stderr)
        return False

    with open(fields_path, "r", encoding="utf-8") as f:
        fields = json.load(f)
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    project_name = fields.get("project_name") or os.path.basename(os.path.normpath(root)) or "프로젝트"

    content = (
        template
        .replace("{{PROJECT_NAME}}", project_name)
        .replace("{{ONE_LINE_DESC}}", fields.get("one_line_desc", ""))
        .replace("{{TECH_STACK_SUMMARY}}", fields.get("tech_stack_summary", ""))
        .replace("{{REQUEST_FLOW}}", fields.get("request_flow", ""))
        .replace("{{FILE_LOCATIONS_ROWS}}", fields.get("file_locations_rows", ""))
        .replace("{{BUILD_RUN}}", fields.get("build_run", ""))
        .replace("{{CAUTIONS}}", fields.get("cautions", ""))
        .replace("{{PARTNER_SECTION}}", build_partner_section(root))
        .replace("{{GENERATION_DATE}}", datetime.now().strftime("%Y-%m-%d"))
    )

    with open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    parser = argparse.ArgumentParser(description="Harness 정적 워크플로우 스킬 + domain-expert.md + CLAUDE.md 배포기")
    parser.add_argument("--root", required=True, help="프로젝트 루트 절대 경로")
    parser.add_argument("--summary", required=True, help="_workspace/02_writer_files.md 경로")
    args = parser.parse_args()

    skills_dir = os.path.join(args.root, ".claude", "skills")
    os.makedirs(skills_dir, exist_ok=True)

    summary_text = ""
    if os.path.isfile(args.summary):
        with open(args.summary, "r", encoding="utf-8") as f:
            summary_text = f.read()
    else:
        print(f"WARN: 요약 파일 없음 ({args.summary}) — 조건부 스킬(plan-migration/review-sql)은 스킵", file=sys.stderr)

    deployed, skipped = [], []

    for name in ALWAYS_DEPLOY:
        _deploy(name, skills_dir)
        deployed.append(name)

    for name in CONDITIONAL_DEPLOY:
        if decision_for(name, summary_text):
            _deploy(name, skills_dir)
            deployed.append(name)
        else:
            skipped.append(name)

    print(f"배포 완료: {', '.join(deployed)}")
    if skipped:
        print(f"조건 미충족으로 스킵: {', '.join(skipped)}")

    if deploy_domain_expert(args.root, summary_text):
        print("배포 완료: domain-expert.md (analyzer_report 복사)")

    if deploy_claude_md(args.root):
        print("배포 완료: CLAUDE.md (claude_md_fields.json + 템플릿 조립)")


def _deploy(name, skills_dir):
    src = os.path.join(TEMPLATE_DIR, f"{name}.template.md")
    if not os.path.isfile(src):
        print(f"WARN: 템플릿 없음 — {src}", file=sys.stderr)
        return
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()
    dst = os.path.join(skills_dir, f"{name}.md")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    main()

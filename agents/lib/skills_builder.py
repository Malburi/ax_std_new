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
# patterns/ 스켈레톤 헤더(레이어명/프로젝트명 외 고정 문구)와 02_writer_files.md 완료 보고서
# 서식도 고정 구조라 이 스크립트가 조립한다 — writer는 _workspace/writer_decisions.json
# (조건부 스킬 생성 여부+사유, 패턴 파일명 목록, 탐지 스택, 적용 결정 사유)만 출력한다.
# trace.md / scaffolder.md / find-logic.md 및 각 패턴 파일의 실제 본문(pattern-extractor 소관)은
# 프로젝트별 내용이 실제로 달라지므로 계속 LLM이 직접 작성한다 (이 스크립트 대상 아님).

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(LIB_DIR, "skills")

ALWAYS_DEPLOY = ["analyze-impact", "safe-modify", "scaffold-feature"]
CONDITIONAL_DEPLOY = ["plan-migration", "review-sql"]

SKELETON_MARKER = "pattern-extractor 에이전트가 채울 예정입니다"

DEFAULT_PATTERN_TARGETS = (
    "- 샘플 파일: [analyzer가 샘플링한 파일 경로]\n"
    "- 추출할 요소: [네이밍·구조·예외 처리·로깅 등]\n"
)

CLIENT_PATTERN_TARGETS = (
    "- 샘플 파일: [analyzer가 샘플링한 파일 경로]\n"
    "- JS↔JSP 매핑 (다대일 관계)\n"
    "- onInit/onSaveData 함수 규약\n"
    "- transData()/eval AJAX 계약 + 응답 형식\n"
    "- _gate/_ajax/_popup 파일 명명 규약\n"
    "- jQuery 버전 환경 및 $() 혼재 안티패턴\n"
)


def decision_for(skill_name, decisions):
    """writer_decisions.json에서 생성 여부를 읽는다.
    키가 없거나 decisions가 None이면 안전하게 미생성으로 처리한다."""
    if not decisions:
        return False
    key = skill_name.replace("-", "_")
    entry = decisions.get(key) or {}
    return bool(entry.get("generate"))


def _layer_label(filename):
    base = filename[:-len("_pattern.md")] if filename.endswith("_pattern.md") else filename
    return base.replace("_", " ").title()


def deploy_pattern_skeletons(root, analyzer_report_text, pattern_files):
    """writer.md '12+. patterns/ 파일 스켈레톤'의 고정 헤더 포맷으로 스켈레톤을 생성한다.
    이미 pattern-extractor가 채운(스켈레톤 마커가 없는) 파일은 덮어쓰지 않는다."""
    patterns_dir = os.path.join(root, ".claude", "patterns")
    os.makedirs(patterns_dir, exist_ok=True)

    names = list(pattern_files or [])
    if "LegacyStaticJS" in (analyzer_report_text or "") and "client_pattern.md" not in names:
        names.append("client_pattern.md")

    project_name = os.path.basename(os.path.normpath(root)) or "프로젝트"
    deployed = []
    for name in names:
        dst = os.path.join(patterns_dir, name)
        if os.path.isfile(dst):
            with open(dst, "r", encoding="utf-8") as f:
                existing = f.read()
            if SKELETON_MARKER not in existing:
                continue
        targets = CLIENT_PATTERN_TARGETS if name == "client_pattern.md" else DEFAULT_PATTERN_TARGETS
        content = (
            f"# {_layer_label(name)} Pattern — {project_name}\n\n"
            f"> 이 파일은 {SKELETON_MARKER}.\n"
            '> 채우려면: "패턴 추출해줘" 또는 `pattern-extractor` 호출.\n\n'
            "## 추출 대상\n"
            f"{targets}"
        )
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        deployed.append(name)
    return deployed, names


def render_writer_files_report(root, decisions):
    """writer.md '완료 보고' 섹션(167-215줄)의 고정 포맷으로 02_writer_files.md를 조립한다."""
    pattern_files = decisions.get("pattern_files") or []
    pattern_list_md = "\n".join(f"- .claude/patterns/{name}" for name in pattern_files) or "- (없음)"

    def _decision_line(skill_file, key):
        entry = decisions.get(key) or {}
        verdict = "생성" if entry.get("generate") else "미생성"
        reason = (entry.get("reason") or "").strip() or "(사유 없음)"
        return f"- {skill_file}: {verdict} — {reason}"

    cross_scaffold_exists = os.path.isfile(os.path.join(root, ".claude", "skills", "cross-repo-scaffold.md"))
    cross_modify_exists = os.path.isfile(os.path.join(root, ".claude", "skills", "cross-repo-modify.md"))

    applied = decisions.get("applied_decisions") or []
    applied_md = "\n".join(f"- {item}" for item in applied) or "- (해당 없음)"

    content = (
        "=== WRITER COMPLETE (Enhanced) ===\n\n"
        "생성된 파일:\n\n"
        "[Core — writer 직접 작성]\n"
        "- _workspace/claude_md_fields.json           (CLAUDE.md 필드 — 아래 skills_builder.py가 조립)\n"
        "- .claude/skills/trace.md\n"
        "- .claude/skills/scaffolder.md\n"
        "- .claude/skills/find-logic.md\n\n"
        "[skills_builder.py가 뒤이어 배포 — 여기 안 씀]\n"
        "- CLAUDE.md                                 (claude_md_fields.json + 템플릿 조립)\n"
        "- .claude/agents/domain-expert.md           (analyzer_report 복사)\n"
        "- .claude/skills/analyze-impact.md\n"
        "- .claude/skills/safe-modify.md\n"
        "- .claude/skills/scaffold-feature.md\n"
        "- .claude/skills/plan-migration.md          (생성 조건 충족 시 — 아래 판단 참조)\n"
        "- .claude/skills/review-sql.md              (DB 사용 확인 시 — 아래 판단 참조)\n"
        "- .claude/patterns/[목록]                    (스켈레톤 — skills_builder.py가 조립, 아래 목록 참조)\n\n"
        "[Workflow Skills — writer 직접 작성]\n"
        f"- .claude/skills/cross-repo-scaffold.md     ({'생성됨' if cross_scaffold_exists else '미생성 — pair_config.md 없음'})\n"
        f"- .claude/skills/cross-repo-modify.md       ({'생성됨' if cross_modify_exists else '미생성 — pair_config.md 없음'})\n\n"
        "[Pattern Skeletons — pattern-extractor가 채울 예정]\n"
        f"{pattern_list_md}\n\n"
        f"탐지 스택: {decisions.get('detected_stack', '미상')}\n"
        f"분석 신뢰도: {decisions.get('confidence', '미상')}\n\n"
        "선택적 스킬 생성 결정:\n"
        f"{_decision_line('plan-migration.md', 'plan_migration')}\n"
        f"{_decision_line('review-sql.md', 'review_sql')}\n"
        f"- cross-repo-scaffold.md: {'생성' if cross_scaffold_exists else '미생성'} — pair_config.md 존재 여부\n"
        f"- cross-repo-modify.md: {'생성' if cross_modify_exists else '미생성'} — pair_config.md 존재 여부\n\n"
        "적용 결정 사유:\n"
        f"{applied_md}\n\n"
        "다음 권장 단계:\n"
        "- pattern-extractor 호출하여 패턴 스켈레톤 채우기\n\n"
        "=== END ===\n"
    )

    out_path = os.path.join(root, "_workspace", "02_writer_files.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


DOMAIN_EXPERT_DESC = (
    "{project_name} 프로젝트의 코드베이스 분석 결과(스택·아키텍처·의존성·데이터 흐름·"
    "트랜잭션·외부 통신)를 전부 갖고 있는 도메인 지식 에이전트. 비즈니스 로직·아키텍처 "
    "관련 질문이나 다른 에이전트가 프로젝트 맥락이 필요할 때 참조한다."
)


def deploy_domain_expert(root):
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
    parser = argparse.ArgumentParser(description="Harness 정적 워크플로우 스킬 + domain-expert.md + CLAUDE.md + 패턴 스켈레톤 + 02_writer_files.md 배포기")
    parser.add_argument("--root", required=True, help="프로젝트 루트 절대 경로")
    parser.add_argument("--summary", required=True, help="_workspace/writer_decisions.json 경로")
    args = parser.parse_args()

    skills_dir = os.path.join(args.root, ".claude", "skills")
    os.makedirs(skills_dir, exist_ok=True)

    decisions = None
    if os.path.isfile(args.summary):
        with open(args.summary, "r", encoding="utf-8") as f:
            try:
                decisions = json.load(f)
            except json.JSONDecodeError:
                print(f"WARN: {args.summary} JSON 파싱 실패 — 조건부 스킬/패턴 스켈레톤/02_writer_files.md 스킵", file=sys.stderr)
    else:
        print(f"WARN: 요약 파일 없음 ({args.summary}) — 조건부 스킬(plan-migration/review-sql)·패턴 스켈레톤·02_writer_files.md는 스킵", file=sys.stderr)

    deployed, skipped = [], []

    for name in ALWAYS_DEPLOY:
        _deploy(name, skills_dir)
        deployed.append(name)

    for name in CONDITIONAL_DEPLOY:
        if decision_for(name, decisions):
            _deploy(name, skills_dir)
            deployed.append(name)
        else:
            skipped.append(name)

    print(f"배포 완료: {', '.join(deployed)}")
    if skipped:
        print(f"조건 미충족으로 스킵: {', '.join(skipped)}")

    if deploy_domain_expert(args.root):
        print("배포 완료: domain-expert.md (analyzer_report 복사)")

    if deploy_claude_md(args.root):
        print("배포 완료: CLAUDE.md (claude_md_fields.json + 템플릿 조립)")

    if decisions:
        report_path = os.path.join(args.root, "_workspace", "01_analyzer_report.md")
        analyzer_report_text = ""
        if os.path.isfile(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                analyzer_report_text = f.read()

        deployed_patterns, final_pattern_list = deploy_pattern_skeletons(
            args.root, analyzer_report_text, decisions.get("pattern_files") or []
        )
        if deployed_patterns:
            print(f"배포 완료: 패턴 스켈레톤 {len(deployed_patterns)}개 ({', '.join(deployed_patterns)})")

        decisions_for_report = dict(decisions)
        decisions_for_report["pattern_files"] = final_pattern_list
        out_path = render_writer_files_report(args.root, decisions_for_report)
        print(f"배포 완료: 02_writer_files.md ({out_path})")


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

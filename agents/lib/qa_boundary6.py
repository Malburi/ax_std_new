import os
import sys
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# qa.md의 Boundary 6(신규 워크플로우 스킬 ↔ 인덱스 의존성)은 파일 존재 확인뿐이라 LLM이
# 필요 없다. 나머지 Boundary 1~5, 7은 실제 소스코드를 읽고 의미 비교가 필요해 그대로 qa(LLM)가 담당.

DEPS = {
    "analyze-impact.md": ["call_graph.json"],
    "review-sql.md": ["sql_usage.json", "schema.json"],
    "plan-migration.md": ["external_io.json", "transactions.json"],
}


def build_report(root):
    skills_dir = os.path.join(root, ".claude", "skills")
    index_dir = os.path.join(root, "_workspace", "index")

    lines = []
    for skill, deps in DEPS.items():
        skill_exists = os.path.isfile(os.path.join(skills_dir, skill))
        if not skill_exists:
            lines.append(f"- {skill} 의존 인덱스: 스킬 미생성 (검사 대상 아님)")
            continue
        missing = [d for d in deps if not os.path.isfile(os.path.join(index_dir, d))]
        if missing:
            lines.append(f"- {skill} 의존 인덱스: 누락 ({', '.join(missing)})")
        else:
            lines.append(f"- {skill} 의존 인덱스: 존재 ({', '.join(deps)})")

    any_missing = any("누락" in l for l in lines)
    recommendation = (
        "analyzer를 full 모드로 재실행하여 누락 인덱스 생성"
        if any_missing
        else "누락 없음"
    )

    return (
        "## Boundary 6: Workflow Skills ↔ Index Deps (NEW)\n"
        + "\n".join(lines)
        + f"\n권고: {recommendation}\n"
    )


def main():
    parser = argparse.ArgumentParser(description="qa Boundary 6 기계 실행기 (LLM 미사용)")
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_path = args.out or os.path.join(args.root, "_workspace", "qa_boundary6.md")
    report = build_report(args.root)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"생성 완료: {out_path}")


if __name__ == "__main__":
    main()

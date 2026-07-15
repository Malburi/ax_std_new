"""wiki_content.py — _workspace/·.claude/ 산출물을 wiki 페이지 문자열로 변환하는 순수 함수 모음.

전부 LLM 미개입, 결정론적 Python. wiki_generator.py가 파일을 읽어(read_file/load_json)
이 모듈의 build_*() 함수에 텍스트/딕셔너리를 넘기면, 각 함수는 markdown 문자열을 반환한다.

크로스 리포(pair-init) 병합이 의미 있는 4개 함수(architecture/api-endpoints/database/
external-systems)는 own_* 인자 옆에 partner_* 인자를 받아, 있으면 "## 파트너 (label)"
섹션으로 이어붙인다. 없으면(파트너가 아직 harness-init 전이거나 단일 저장소) own 것만 반환.
workflows/patterns/issues는 저장소별 실행 환경·품질 이슈라 병합 대상이 아니다
(CLAUDE.md 2026-07-15 wiki 통합 변경 이력 참조).
"""

import os
import re


def _section(label, body):
    if not body or not body.strip():
        return ""
    return f"## {label}\n\n{body.strip()}\n"


def build_home(claude_md_text):
    if not claude_md_text:
        return "# Home\n\nCLAUDE.md가 없습니다.\n"
    return "> 이 페이지는 프로젝트 루트의 `CLAUDE.md`를 그대로 보여줍니다.\n\n" + claude_md_text


def build_architecture(own_report_text, partner_report_text=None,
                        own_label="이 저장소", partner_label=None):
    own = own_report_text or "`_workspace/01_analyzer_report.md`가 없습니다. harness-init을 먼저 실행하세요.\n"
    parts = [f"# 아키텍처\n", _section(own_label, own)]
    if partner_report_text:
        parts.append(_section(f"파트너 ({partner_label or '연동 저장소'})", partner_report_text))
    return "\n".join(p for p in parts if p)


def _read_dir_pages(dir_path):
    """폴더 안 *.md 파일을 이름순으로 (filename, text) 목록으로 읽는다."""
    if not dir_path or not os.path.isdir(dir_path):
        return []
    pages = []
    for name in sorted(os.listdir(dir_path)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(dir_path, name)
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            pages.append((name, f.read()))
    return pages


def _frontmatter_field(text, field):
    m = re.search(rf"^{field}:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def build_workflows(skills_dir):
    pages = _read_dir_pages(skills_dir)
    if not pages:
        return "# 워크플로우 스킬\n\n등록된 스킬이 없습니다.\n"

    toc = ["# 워크플로우 스킬\n", "| 스킬 | 설명 |", "|------|------|"]
    body = []
    for filename, text in pages:
        name = _frontmatter_field(text, "name") or os.path.splitext(filename)[0]
        desc = _frontmatter_field(text, "description")
        toc.append(f"| [{name}](#{name.lower()}) | {desc} |")
        body.append(f"---\n\n{text.strip()}\n")

    return "\n".join(toc) + "\n\n" + "\n".join(body)


def build_patterns(patterns_dir):
    pages = _read_dir_pages(patterns_dir)
    if not pages:
        return "# 패턴 가이드\n\n추출된 패턴이 없습니다.\n"

    toc = ["# 패턴 가이드\n", "| 패턴 | 파일 |", "|------|------|"]
    body = []
    for filename, text in pages:
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else filename
        toc.append(f"| {title} | `{filename}` |")
        body.append(f"---\n\n{text.strip()}\n")

    return "\n".join(toc) + "\n\n" + "\n".join(body)


def build_issues(validator_report_text, qa_report_text, dead_code_json):
    parts = ["# 이슈 & 보안\n"]
    if validator_report_text:
        parts.append(_section("검증 리포트 (validator)", validator_report_text))
    if qa_report_text:
        parts.append(_section("QA 리포트", qa_report_text))

    if dead_code_json:
        rows = ["## 데드 코드 후보", "", "| 종류 | ID/파일 | 사유 |", "|------|------|------|"]
        for item in dead_code_json.get("unused_methods", []):
            rows.append(f"| method | {item.get('id', '')} | {item.get('reason', '')} |")
        for item in dead_code_json.get("unused_sql_ids", []):
            rows.append(f"| sql | {item.get('id', '')} | {item.get('reason', '')} |")
        for item in dead_code_json.get("unused_jsps", []):
            rows.append(f"| jsp | {item.get('file', '')} | {item.get('reason', '')} |")
        if len(rows) > 4:
            parts.append("\n".join(rows) + "\n")

    if len(parts) == 1:
        parts.append("검증/QA 리포트가 없습니다.\n")
    return "\n".join(parts)


def _api_endpoints_table(contract_json):
    if not contract_json:
        return ""
    endpoints = contract_json.get("endpoints", [])
    if not endpoints:
        return ""
    rows = ["| Method | Path | Handler | Auth |", "|--------|------|---------|------|"]
    for ep in endpoints:
        auth = "✅" if ep.get("auth_required") else ""
        rows.append(
            f"| {ep.get('method', '')} | {ep.get('path', '')} | "
            f"{ep.get('handler', '')} | {auth} |"
        )
    return "\n".join(rows)


def build_api_endpoints(own_contract_json, partner_contract_json=None,
                         own_label="이 저장소", partner_label=None):
    own_table = _api_endpoints_table(own_contract_json)
    parts = ["# API Endpoints\n"]
    parts.append(_section(own_label, own_table) if own_table else "API 계약 정보가 없습니다.\n")
    partner_table = _api_endpoints_table(partner_contract_json)
    if partner_table:
        parts.append(_section(f"파트너 ({partner_label or '연동 저장소'})", partner_table))
    return "\n".join(p for p in parts if p)


def _database_tables_md(schema_json):
    if not schema_json:
        return ""
    tables = schema_json.get("tables", [])
    if not tables:
        return ""
    out = []
    for t in tables:
        out.append(f"### {t.get('name', '')}")
        cols = t.get("columns", [])
        if cols:
            out.append("| 컬럼 | 타입 | Null | 기본값 | PK |")
            out.append("|------|------|------|--------|----|")
            pk_cols = set(t.get("primary_key", []))
            for c in cols:
                is_pk = "✅" if c.get("name") in pk_cols or c.get("primary_key") else ""
                out.append(
                    f"| {c.get('name', '')} | {c.get('type', '')} | "
                    f"{'NULL' if c.get('nullable') else 'NOT NULL'} | "
                    f"{c.get('default', '')} | {is_pk} |"
                )
        fks = t.get("foreign_keys", [])
        for fk in fks:
            out.append(
                f"- FK `{fk.get('name', '')}`: {', '.join(fk.get('columns', []))} → "
                f"{fk.get('references_table', '')}({', '.join(fk.get('references_columns', []))})"
            )
        idxs = t.get("indexes", [])
        for idx in idxs:
            out.append(f"- INDEX `{idx.get('name', '')}`: {', '.join(idx.get('columns', []))}")
        out.append("")
    return "\n".join(out)


def _sql_usage_table(sql_usage_json):
    if not sql_usage_json:
        return ""
    sqls = sql_usage_json.get("sqls", [])
    if not sqls:
        return ""
    rows = ["| SQL ID | 타입 | 대상 테이블 |", "|--------|------|------------|"]
    for s in sqls:
        rows.append(f"| {s.get('id', '')} | {s.get('type', '')} | {', '.join(s.get('tables', []))} |")
    return "\n".join(rows)


def build_database(own_schema_json, own_sql_usage_json,
                    partner_schema_json=None, partner_sql_usage_json=None,
                    own_label="이 저장소", partner_label=None):
    own_body = "\n\n".join(
        p for p in [_database_tables_md(own_schema_json), _sql_usage_table(own_sql_usage_json)] if p
    )
    parts = ["# Database\n"]
    parts.append(_section(own_label, own_body) if own_body else "DB 스키마 정보가 없습니다.\n")

    partner_body = "\n\n".join(
        p for p in [_database_tables_md(partner_schema_json), _sql_usage_table(partner_sql_usage_json)] if p
    )
    if partner_body:
        parts.append(_section(f"파트너 ({partner_label or '연동 저장소'})", partner_body))
    return "\n".join(p for p in parts if p)


def _external_io_table(io_json):
    if not io_json:
        return ""
    comms = io_json.get("communications", [])
    if not comms:
        return ""
    rows = ["| Type | Target | File:Line |", "|------|--------|-----------|"]
    for c in comms:
        target = c.get("target") or c.get("topic") or c.get("path_pattern") or ""
        rows.append(f"| {c.get('type', '')} | {target} | {c.get('file', '')}:{c.get('line', '')} |")
    return "\n".join(rows)


def build_external_systems(own_io_json, partner_io_json=None,
                            own_label="이 저장소", partner_label=None):
    own_table = _external_io_table(own_io_json)
    parts = ["# External Systems\n"]
    parts.append(_section(own_label, own_table) if own_table else "외부 시스템 연동 정보가 없습니다.\n")
    partner_table = _external_io_table(partner_io_json)
    if partner_table:
        parts.append(_section(f"파트너 ({partner_label or '연동 저장소'})", partner_table))
    return "\n".join(p for p in parts if p)

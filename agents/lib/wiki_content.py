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


def has_api_data(contract_json):
    """provider(endpoints) + consumer(dynamic_sql_calls/hiway_rest_endpoints) 계약 둘 다 인식."""
    if not contract_json:
        return False
    return bool(
        contract_json.get("endpoints")
        or contract_json.get("dynamic_sql_calls")
        or contract_json.get("hiway_rest_endpoints")
    )


def _dynamic_sql_calls_md(calls):
    if not calls:
        return ""
    rows = ["| Method | Namespace | SQL ID | Purpose | Callers |", "|--------|-----------|--------|---------|---------|"]
    for c in calls:
        callers = c.get("callers", [])
        callers = ", ".join(callers) if isinstance(callers, list) else callers
        rows.append(
            f"| {c.get('method', '')} | {c.get('namespace', '')} | {c.get('sqlid', '')} | "
            f"{c.get('purpose', '')} | {callers} |"
        )
    return "\n".join(rows)


def _hiway_rest_endpoints_md(eps):
    if not eps:
        return ""
    rows = ["| Method | Path | File | Purpose |", "|--------|------|------|---------|"]
    for e in eps:
        rows.append(f"| {e.get('method', '')} | {e.get('path', '')} | {e.get('file', '')} | {e.get('purpose', '')} |")
    return "\n".join(rows)


def _api_endpoints_table(contract_json):
    if not contract_json:
        return ""
    endpoints = contract_json.get("endpoints", [])
    if endpoints:
        rows = ["| Method | Path | Handler | Auth |", "|--------|------|---------|------|"]
        for ep in endpoints:
            auth = "✅" if ep.get("auth_required") else ""
            rows.append(
                f"| {ep.get('method', '')} | {ep.get('path', '')} | "
                f"{ep.get('handler', '')} | {auth} |"
            )
        return "\n".join(rows)
    # consumer(frontend) 계약 — provider 라우트가 아니라 호출하는 namespace/sqlid·REST 목록
    parts = []
    note = contract_json.get("note")
    if note:
        parts.append(f"> {note}\n")
    dsc = _dynamic_sql_calls_md(contract_json.get("dynamic_sql_calls"))
    if dsc:
        total = contract_json.get("total_dynamic_sql_calls", len(contract_json.get("dynamic_sql_calls", [])))
        parts.append(f"#### 동적 SQL 호출 ({total}건)\n\n{dsc}")
    hre = _hiway_rest_endpoints_md(contract_json.get("hiway_rest_endpoints"))
    if hre:
        parts.append(f"#### Hiway REST 호출\n\n{hre}")
    return "\n\n".join(parts)


def build_api_endpoints(own_contract_json, partner_contract_json=None,
                         own_label="이 저장소", partner_label=None):
    own_table = _api_endpoints_table(own_contract_json)
    parts = ["# API Endpoints\n"]
    parts.append(_section(own_label, own_table) if own_table else "API 계약 정보가 없습니다.\n")
    partner_table = _api_endpoints_table(partner_contract_json)
    if partner_table:
        parts.append(_section(f"파트너 ({partner_label or '연동 저장소'})", partner_table))
    return "\n".join(p for p in parts if p)


def has_schema_data(schema_json):
    """index-spec 표준(tables) + 프로시저 중심 프로젝트의 대체 스키마
    (tables_directly_referenced/stored_procedures) 둘 다 인식."""
    if not schema_json:
        return False
    if schema_json.get("tables"):
        return True
    if schema_json.get("tables_directly_referenced"):
        return True
    sp = schema_json.get("stored_procedures")
    if isinstance(sp, dict) and any(
        k != "note" and isinstance(v, list) and v for k, v in sp.items()
    ):
        return True
    return False


FRONTEND_EXTERNAL_IO_KEYS = (
    "http_client", "backend_gateways", "vite_dev_proxy",
    "module_federation_remote", "external_scripts", "anti_patterns",
)


def has_external_data(io_json):
    """index-spec 표준(communications) + outbound/datastores(backend) +
    http_client/backend_gateways/...(frontend consumer) 셋 다 인식."""
    if not io_json:
        return False
    if io_json.get("communications") or io_json.get("outbound") or io_json.get("datastores"):
        return True
    return any(io_json.get(k) for k in FRONTEND_EXTERNAL_IO_KEYS)


def _stored_procedures_md(sp):
    if not sp or not isinstance(sp, dict):
        return ""
    out = []
    note = sp.get("note")
    if note:
        out.append(f"> {note}\n")
    for category, items in sp.items():
        if category == "note" or not isinstance(items, list) or not items:
            continue
        out.append(f"#### {category}")
        out.append("| Proc | IN | OUT | Note |")
        out.append("|------|----|----|------|")
        for it in items:
            if not isinstance(it, dict):
                continue
            in_val = it.get("in", "")
            out_val = it.get("out", "")
            in_val = ", ".join(in_val) if isinstance(in_val, list) else in_val
            out_val = ", ".join(out_val) if isinstance(out_val, list) else out_val
            out.append(f"| {it.get('proc', '')} | {in_val} | {out_val} | {it.get('note', '')} |")
        out.append("")
    return "\n".join(out)


def _tables_directly_referenced_md(refs):
    if not refs:
        return ""
    rows = ["| Table | Source | Columns | Confidence |", "|-------|--------|---------|------------|"]
    for t in refs:
        cols = t.get("columns_seen", [])
        cols = ", ".join(cols) if isinstance(cols, list) else cols
        rows.append(f"| {t.get('name', '')} | {t.get('source', '')} | {cols} | {t.get('confidence', '')} |")
    return "\n".join(rows)


def _database_tables_md(schema_json):
    if not schema_json:
        return ""
    tables = schema_json.get("tables", [])
    if not tables:
        # index-spec 표준 스키마가 아닌 프로시저 중심 프로젝트(tables_directly_referenced/stored_procedures)
        parts = []
        refs_md = _tables_directly_referenced_md(schema_json.get("tables_directly_referenced"))
        if refs_md:
            parts.append("### 직접 참조 테이블\n\n" + refs_md)
        sp_md = _stored_procedures_md(schema_json.get("stored_procedures"))
        if sp_md:
            parts.append("### 저장 프로시저\n\n" + sp_md)
        return "\n\n".join(parts)
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


def _outbound_md(outbound):
    if not outbound:
        return ""
    rows = ["| Kind | Target | Caller | File |", "|------|--------|--------|------|"]
    for c in outbound:
        if not isinstance(c, dict):
            continue
        target = c.get("target") or c.get("endpoint") or c.get("interface") or c.get("class") or ""
        rows.append(f"| {c.get('kind', '')} | {target} | {c.get('caller', '')} | {c.get('file', '')} |")
    return "\n".join(rows)


def _datastores_md(datastores):
    if not datastores:
        return ""
    out = []
    for d in datastores:
        if not isinstance(d, dict):
            continue
        out.append(f"#### {d.get('kind', '')}")
        for k, v in d.items():
            if k == "kind":
                continue
            if isinstance(v, dict):
                v = ", ".join(f"{kk}={vv}" for kk, vv in v.items())
            out.append(f"- **{k}**: {v}")
        out.append("")
    return "\n".join(out)


def _generic_value_md(v, indent=0):
    """schema를 미리 알 수 없는 임의 dict/list를 중첩 bullet로 렌더링하는 범용 폴백."""
    pad = "  " * indent
    if isinstance(v, dict):
        lines = []
        for k, vv in v.items():
            if isinstance(vv, (dict, list)) and vv:
                lines.append(f"{pad}- **{k}**:")
                lines.append(_generic_value_md(vv, indent + 1))
            else:
                lines.append(f"{pad}- **{k}**: {vv}")
        return "\n".join(lines)
    if isinstance(v, list):
        lines = []
        for item in v:
            if isinstance(item, (dict, list)):
                lines.append(_generic_value_md(item, indent))
            else:
                lines.append(f"{pad}- {item}")
        return "\n".join(lines)
    return f"{pad}{v}"


def _frontend_external_md(io_json):
    """provider(outbound/datastores)가 아닌 consumer(frontend) external_io 스키마
    (http_client/backend_gateways/vite_dev_proxy/module_federation_remote/external_scripts/anti_patterns)."""
    parts = []
    hc = io_json.get("http_client")
    if hc:
        parts.append("### HTTP Client\n\n" + _generic_value_md(hc))
    bg = io_json.get("backend_gateways")
    if bg:
        parts.append("### Backend Gateways\n\n" + _generic_value_md(bg))
    vdp = io_json.get("vite_dev_proxy")
    if vdp:
        rows = ["| Path | Target |", "|------|--------|"]
        for k, v in vdp.items():
            rows.append(f"| {k} | {v} |")
        parts.append("### Vite Dev Proxy\n\n" + "\n".join(rows))
    mfr = io_json.get("module_federation_remote")
    if mfr:
        parts.append("### Module Federation Remote\n\n" + _generic_value_md(mfr))
    es = io_json.get("external_scripts")
    if es:
        rows = ["| File | Resource | Load |", "|------|----------|------|"]
        for e in es:
            rows.append(f"| {e.get('file', '')} | {e.get('resource', '')} | {e.get('load', '')} |")
        parts.append("### External Scripts\n\n" + "\n".join(rows))
    ap = io_json.get("anti_patterns")
    if ap:
        parts.append("### Anti-patterns\n\n" + "\n".join(f"- {a}" for a in ap))
    return "\n\n".join(parts)


def _external_io_table(io_json):
    if not io_json:
        return ""
    comms = io_json.get("communications", [])
    if comms:
        rows = ["| Type | Target | File:Line |", "|------|--------|-----------|"]
        for c in comms:
            target = c.get("target") or c.get("topic") or c.get("path_pattern") or ""
            rows.append(f"| {c.get('type', '')} | {target} | {c.get('file', '')}:{c.get('line', '')} |")
        return "\n".join(rows)
    # index-spec 표준(communications)이 아닌 backend(outbound/datastores) 스키마
    ob_md = _outbound_md(io_json.get("outbound"))
    ds_md = _datastores_md(io_json.get("datastores"))
    note = io_json.get("note")
    if ob_md or ds_md:
        parts = []
        if note:
            parts.append(f"> {note}\n")
        if ob_md:
            parts.append("### Outbound 통신\n\n" + ob_md)
        if ds_md:
            parts.append("### Datastores\n\n" + ds_md)
        return "\n\n".join(parts)
    # consumer(frontend) 스키마
    fe_md = _frontend_external_md(io_json)
    if not fe_md:
        return ""
    if note:
        fe_md = f"> {note}\n\n" + fe_md
    return fe_md


def build_external_systems(own_io_json, partner_io_json=None,
                            own_label="이 저장소", partner_label=None):
    own_table = _external_io_table(own_io_json)
    parts = ["# External Systems\n"]
    parts.append(_section(own_label, own_table) if own_table else "외부 시스템 연동 정보가 없습니다.\n")
    partner_table = _external_io_table(partner_io_json)
    if partner_table:
        parts.append(_section(f"파트너 ({partner_label or '연동 저장소'})", partner_table))
    return "\n".join(p for p in parts if p)

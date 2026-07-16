# harness 산출물을 wiki 폴더(Docsify·call-graph.html·정적 HTML)로 변환하는 zero-LLM 오케스트레이터
import os
import json
import re
import sys
import wiki_render
import wiki_content
import docsify_convert

# 템플릿(call-graph)과 vis-network 라이브러리는 이 스크립트가 속한
# 플러그인 저장소(agents/lib/)에 있다. 대상 프로젝트(project_root) 안에는 없다 — 대상
# 프로젝트 경로 기준으로 찾으면 실사용(플러그인으로 설치되어 다른 프로젝트에 대해 실행되는 경우)
# 항상 못 찾아서 조용히 스킵되는 버그가 된다.
LIB_DIR = os.path.dirname(os.path.abspath(__file__))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime

def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def render_and_track(wiki_dir, page_entries, project_name, filename, content, label):
    """폴더 모드에서 서버 없이 브라우저로 바로 열리도록, .md 페이지를
    wiki/_html/<name>.html 정적 렌더 사본으로도 저장하고 index.html용 항목을 기록한다."""
    html_name = os.path.splitext(filename)[0] + ".html"
    rendered = wiki_render.render_markdown_page(project_name, filename, content, index_href="../index.html")
    write_file(os.path.join(wiki_dir, "_html", html_name), rendered)
    page_entries.append((f"_html/{html_name}", label, filename))


def parse_pair_config(root):
    """_workspace/pair_config.md (단순 key: value 마크다운)를 파싱. 없으면 None."""
    text = read_file(os.path.join(root, "_workspace", "pair_config.md"))
    if not text:
        return None
    cfg = {}
    for key in ["project_type", "partner_type", "partner_root", "partner_workspace",
                "partner_stack", "api_base_url", "api_contract_path",
                "partner_api_contract", "linked_at"]:
        m = re.search(rf"^{key}:\s*(.+)$", text, re.MULTILINE)
        if m:
            cfg[key] = m.group(1).strip()
    return cfg or None


def normalize_api_path(p):
    """/api/order/:id, /api/orders/{id}, /api/orders/${id} 를 모두 /api/orders/{} 로 정규화."""
    if not p:
        return ""
    p = p.split("?")[0].rstrip("/")
    p = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", "{}", p)
    p = re.sub(r"\$\{[^}]*\}", "{}", p)
    p = re.sub(r"\{[^}]*\}", "{}", p)
    return p.lower()


def prefix_graph(graph, prefix):
    """파트너 그래프의 노드/엣지 id에 접두사를 붙여 자기 그래프와 충돌하지 않게 한다."""
    if not graph:
        return {"nodes": [], "edges": []}
    nodes = []
    for n in graph.get("nodes", []):
        n2 = dict(n)
        n2["id"] = f"{prefix}{n.get('id')}"
        nodes.append(n2)
    edges = []
    for e in graph.get("edges", []):
        e2 = dict(e)
        e2["from"] = f"{prefix}{e.get('from')}"
        e2["to"] = f"{prefix}{e.get('to')}"
        edges.append(e2)
    return {"nodes": nodes, "edges": edges}


def extract_path_and_method(text_fields):
    """노드의 id/label/note/file 텍스트에서 HTTP 메서드·경로 후보를 뽑는다. 못 찾으면 (None, None)."""
    combined = " ".join([t for t in text_fields if t])
    method = None
    m = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", combined, re.IGNORECASE)
    if m:
        method = m.group(1).upper()
    path = None
    m2 = re.search(r"(/[A-Za-z0-9_\-{}:$./]+)", combined)
    if m2:
        path = m2.group(1)
    return method, path


def build_endpoint_index(contract):
    """api_contract.json의 endpoints -> {(method, normalized_path): endpoint_dict}."""
    idx = {}
    if not contract:
        return idx
    for ep in contract.get("endpoints", []):
        key = (ep.get("method", "").upper(), normalize_api_path(ep.get("path", "")))
        idx[key] = ep
    return idx


def find_backend_node_for_endpoint(endpoint, backend_nodes):
    """controller_file/handler로 call_graph 노드를 찾는다 (같은 저장소라 file 경로가 그대로 일치한다)."""
    cfile = endpoint.get("controller_file", "")
    handler = (endpoint.get("handler") or "").lower()
    if not cfile:
        return None
    for n in backend_nodes:
        nfile = n.get("file", "")
        if nfile and (nfile in cfile or cfile in nfile):
            if not handler or handler in str(n.get("id", "")).lower() or handler in str(n.get("label", "")).lower():
                return n.get("id")
    return None


def infer_cross_edges(frontend_nodes, endpoint_index, backend_nodes):
    """프론트 external/client 노드 <-> 백엔드 엔드포인트 노드를 메서드+경로 매칭으로 연결한다.
    노드에 경로 정보가 없으면(analyzer가 안 채운 경우) 매칭 0건 — 조용히 실패하지 않고 호출부에서 로그로 알린다."""
    edges = []
    unmatched = 0
    for n in frontend_nodes:
        if n.get("type", "") not in ("external", "client", "api"):
            continue
        method, path = extract_path_and_method([
            str(n.get("id", "")), str(n.get("label", "")),
            str(n.get("note", "")), str(n.get("file", "")),
        ])
        if not path:
            unmatched += 1
            continue
        npath = normalize_api_path(path)
        ep = endpoint_index.get((method, npath)) if method else None
        if not ep:
            candidates = [v for (m, p), v in endpoint_index.items() if p == npath]
            if len(candidates) == 1:
                ep = candidates[0]
        if not ep:
            unmatched += 1
            continue
        backend_id = find_backend_node_for_endpoint(ep, backend_nodes)
        if backend_id:
            edges.append({
                "from": n.get("id"), "to": backend_id,
                "label": f"{ep.get('method')} {ep.get('path')}", "type": "call",
            })
        else:
            unmatched += 1
    return edges, unmatched


def merge_partner_call_graph(project_root, raw_graph):
    """pair_config.md가 있으면 파트너 call_graph.json을 병합하고, api_contract.json 기반으로
    프론트<->백엔드 크로스 엣지를 추론한다. 전부 결정론적 문자열 매칭 — LLM 미개입.
    반환: (병합된 그래프, merge_info dict — 07_wiki_build.md 보고용)"""
    no_merge_info = {"merged": False}
    pair_cfg = parse_pair_config(project_root)
    if not pair_cfg or not pair_cfg.get("partner_workspace"):
        return raw_graph, no_merge_info

    partner_graph = load_json(os.path.join(pair_cfg["partner_workspace"], "index", "call_graph.json"))
    if not partner_graph:
        print("WARN: pair_config.md 있으나 파트너 call_graph.json 없음/비어있음 — 크로스 리포 병합 스킵")
        return raw_graph, {"merged": False, "reason": "파트너 call_graph.json 없음/비어있음"}

    prefixed_partner = prefix_graph(partner_graph, "partner_")
    own_type = pair_cfg.get("project_type", "")

    endpoint_index, backend_nodes, frontend_nodes = {}, [], []
    if own_type == "backend":
        backend_nodes = raw_graph.get("nodes", [])
        frontend_nodes = prefixed_partner.get("nodes", [])
        own_contract = load_json(os.path.join(project_root, "_workspace", "index", "api_contract.json"))
        endpoint_index = build_endpoint_index(own_contract)
    elif own_type == "frontend":
        backend_nodes = prefixed_partner.get("nodes", [])
        frontend_nodes = raw_graph.get("nodes", [])
        partner_contract_path = pair_cfg.get("partner_api_contract")
        partner_contract = load_json(partner_contract_path) if partner_contract_path else None
        endpoint_index = build_endpoint_index(partner_contract)

    cross_edges = []
    unmatched = 0
    if endpoint_index and (backend_nodes or frontend_nodes):
        cross_edges, unmatched = infer_cross_edges(frontend_nodes, endpoint_index, backend_nodes)
        print(f"Cross-repo merge: partner nodes {len(prefixed_partner.get('nodes', []))}, "
              f"inferred cross edges {len(cross_edges)} (unmatched candidates: {unmatched})")
    else:
        print(f"Cross-repo merge: partner nodes {len(prefixed_partner.get('nodes', []))} merged, "
              f"cross edges 0 (api_contract.json 없음 또는 project_type 미상 — 경로 매칭 스킵)")

    merge_info = {
        "merged": True,
        "partner_type": pair_cfg.get("partner_type", "미상"),
        "partner_nodes": len(prefixed_partner.get("nodes", [])),
        "cross_edges": len(cross_edges),
        "unmatched": unmatched,
    }
    merged_graph = {
        "nodes": raw_graph.get("nodes", []) + prefixed_partner.get("nodes", []),
        "edges": raw_graph.get("edges", []) + prefixed_partner.get("edges", []) + cross_edges,
    }
    return merged_graph, merge_info


def _partner_paths(pair_cfg):
    """pair_cfg에서 파트너 _workspace 하위 산출물 절대경로들을 계산. pair_cfg 없으면 전부 None."""
    if not pair_cfg or not pair_cfg.get("partner_workspace"):
        return None
    ws = pair_cfg["partner_workspace"]
    return {
        "label": pair_cfg.get("partner_type", "연동 저장소"),
        "analyzer_report": os.path.join(ws, "01_analyzer_report.md"),
        "api_contract": pair_cfg.get("partner_api_contract") or os.path.join(ws, "index", "api_contract.json"),
        "schema": os.path.join(ws, "index", "schema.json"),
        "sql_usage": os.path.join(ws, "index", "sql_usage.json"),
        "external_io": os.path.join(ws, "index", "external_io.json"),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Zero-LLM Wiki Generator — _workspace/.claude 산출물을 그대로 wiki 페이지로")
    parser.add_argument("--root", required=True, help="Project root directory")
    parser.add_argument("--wiki-dir", required=True, help="Output wiki directory")
    parser.add_argument("--storage", choices=["folder", "db"], default="folder",
                         help="folder(기본): wiki_dir에 파일로만 저장. db: 파일 생성 후 MSSQL(harness_wiki_pages)에도 upsert")
    args = parser.parse_args()

    project_root = args.root
    wiki_dir = args.wiki_dir

    print(f"Starting wiki generation (zero-LLM). Root: {project_root}, Wiki: {wiki_dir}")

    project_name = os.path.basename(os.path.normpath(project_root))
    page_entries = []  # (href, label, source_filename) — 정적 index.html 링크 목록

    pair_cfg = parse_pair_config(project_root)
    own_label = (pair_cfg or {}).get("project_type") or "이 저장소"
    partner = _partner_paths(pair_cfg)

    # ---- own-side 원본 로드 ----
    claude_md_text = read_file(os.path.join(project_root, "CLAUDE.md"))
    analyzer_report_text = read_file(os.path.join(project_root, "_workspace", "01_analyzer_report.md"))
    validator_report_text = read_file(os.path.join(project_root, "_workspace", "03_validator_report.md"))
    qa_report_text = read_file(os.path.join(project_root, "_workspace", "04_qa_report.md"))
    dead_code_json = load_json(os.path.join(project_root, "_workspace", "index", "dead_code.json"))
    own_api_contract_json = load_json(os.path.join(project_root, "_workspace", "index", "api_contract.json"))
    own_schema_json = load_json(os.path.join(project_root, "_workspace", "index", "schema.json"))
    own_sql_usage_json = load_json(os.path.join(project_root, "_workspace", "index", "sql_usage.json"))
    own_external_io_json = load_json(os.path.join(project_root, "_workspace", "index", "external_io.json"))
    skills_dir = os.path.join(project_root, ".claude", "skills")
    patterns_dir = os.path.join(project_root, ".claude", "patterns")

    # ---- partner-side 원본 로드 (pair_config.md 있을 때만) ----
    partner_report_text = read_file(partner["analyzer_report"]) if partner else None
    partner_api_contract_json = load_json(partner["api_contract"]) if partner else None
    partner_schema_json = load_json(partner["schema"]) if partner else None
    partner_sql_usage_json = load_json(partner["sql_usage"]) if partner else None
    partner_external_io_json = load_json(partner["external_io"]) if partner else None
    partner_label = partner["label"] if partner else None

    # ---- 페이지 존재 판정 ----
    api_exists = bool((own_api_contract_json or {}).get("endpoints")) or bool((partner_api_contract_json or {}).get("endpoints"))
    db_exists = bool((own_schema_json or {}).get("tables")) or bool((partner_schema_json or {}).get("tables"))
    patterns_exists = os.path.isdir(patterns_dir) and any(f.endswith(".md") for f in os.listdir(patterns_dir))
    external_exists = bool((own_external_io_json or {}).get("communications")) or bool((partner_external_io_json or {}).get("communications"))
    issues_exists = bool(validator_report_text or qa_report_text or dead_code_json)

    # 1. Home.md ← CLAUDE.md 그대로
    home_content = wiki_content.build_home(claude_md_text)
    write_file(os.path.join(wiki_dir, "Home.md"), home_content)
    render_and_track(wiki_dir, page_entries, project_name, "Home.md", home_content, "Home (프로젝트 개요)")
    print("Generated Home.md")

    # 2. architecture.md ← 01_analyzer_report.md (+ 파트너 병합)
    arch_content = wiki_content.build_architecture(
        analyzer_report_text, partner_report_text, own_label=own_label, partner_label=partner_label)
    write_file(os.path.join(wiki_dir, "architecture.md"), arch_content)
    render_and_track(wiki_dir, page_entries, project_name, "architecture.md", arch_content, "Architecture (아키텍처)")
    print("Generated architecture.md")

    # 3. workflows.md ← .claude/skills/*.md 그대로 연결 (병합 대상 아님)
    workflows_content = wiki_content.build_workflows(skills_dir)
    write_file(os.path.join(wiki_dir, "workflows.md"), workflows_content)
    render_and_track(wiki_dir, page_entries, project_name, "workflows.md", workflows_content, "Workflows (워크플로우 스킬)")
    print("Generated workflows.md")

    # 4. patterns.md ← .claude/patterns/*.md 그대로 연결 (병합 대상 아님)
    if patterns_exists:
        patterns_content = wiki_content.build_patterns(patterns_dir)
        write_file(os.path.join(wiki_dir, "patterns.md"), patterns_content)
        render_and_track(wiki_dir, page_entries, project_name, "patterns.md", patterns_content, "Patterns")
        print("Generated patterns.md")

    # 5. api-endpoints.md ← api_contract.json (+ 파트너 병합)
    if api_exists:
        api_content = wiki_content.build_api_endpoints(
            own_api_contract_json, partner_api_contract_json, own_label=own_label, partner_label=partner_label)
        write_file(os.path.join(wiki_dir, "api-endpoints.md"), api_content)
        render_and_track(wiki_dir, page_entries, project_name, "api-endpoints.md", api_content, "API Endpoints")
        print("Generated api-endpoints.md")

    # 6. database.md ← schema.json + sql_usage.json (+ 파트너 병합)
    if db_exists:
        db_content = wiki_content.build_database(
            own_schema_json, own_sql_usage_json, partner_schema_json, partner_sql_usage_json,
            own_label=own_label, partner_label=partner_label)
        write_file(os.path.join(wiki_dir, "database.md"), db_content)
        render_and_track(wiki_dir, page_entries, project_name, "database.md", db_content, "Database")
        print("Generated database.md")

    # 7. external-systems.md ← external_io.json (+ 파트너 병합)
    if external_exists:
        ext_content = wiki_content.build_external_systems(
            own_external_io_json, partner_external_io_json, own_label=own_label, partner_label=partner_label)
        write_file(os.path.join(wiki_dir, "external-systems.md"), ext_content)
        render_and_track(wiki_dir, page_entries, project_name, "external-systems.md", ext_content, "External Systems")
        print("Generated external-systems.md")

    # 8. issues.md ← 03_validator_report.md + 04_qa_report.md + dead_code.json (병합 대상 아님)
    if issues_exists:
        issues_content = wiki_content.build_issues(validator_report_text, qa_report_text, dead_code_json)
        write_file(os.path.join(wiki_dir, "issues.md"), issues_content)
        render_and_track(wiki_dir, page_entries, project_name, "issues.md", issues_content, "Issues (이슈 & 보안)")
        print("Generated issues.md")

    # 9. Copy vis-network lib
    dest_lib_dir = os.path.join(wiki_dir, "lib")
    os.makedirs(dest_lib_dir, exist_ok=True)
    for filename in ["vis-network.min.js", "vis-network.min.css"]:
        src_file = os.path.join(LIB_DIR, filename)
        dest_file = os.path.join(dest_lib_dir, filename)
        if os.path.exists(src_file):
            with open(src_file, 'rb') as sf:
                with open(dest_file, 'wb') as df:
                    df.write(sf.read())
    print("Copied vis-network library files.")

    # 10. Generate call-graph.html (100% Python program-side binding, 파트너 그래프 병합 포함)
    merge_info = {"merged": False}
    call_graph_path = os.path.join(project_root, "_workspace", "index", "call_graph.json")
    cg_template = read_file(os.path.join(LIB_DIR, "call-graph.template.html"))
    nodes_data, edges_data = [], []
    if cg_template:
        raw_graph = load_json(call_graph_path) or {"nodes": [], "edges": []}

        raw_graph, merge_info = merge_partner_call_graph(project_root, raw_graph)

        detected_types = set()
        nodes_data = []
        edges_data = []
        meta_data = {}

        COLORS = {
            "view":          {"bg": '#7B1A1A', "border": '#E74C3C', "font": '#fff'},
            "vue_view":      {"bg": '#7B1A1A', "border": '#E74C3C', "font": '#fff'},
            "endpoint":      {"bg": '#1a5fa8', "border": '#4A90D9', "font": '#fff'},
            "function":      {"bg": '#6C3483', "border": '#9B59B6', "font": '#fff'},
            "dao":           {"bg": '#154360', "border": '#2E86C1', "font": '#fff'},
            "external":      {"bg": '#8a5900', "border": '#F5A623', "font": '#fff'},
            "sap_interface": {"bg": '#8a5900', "border": '#F5A623', "font": '#fff'},
            "db_table":      {"bg": '#2d6a00', "border": '#7ED321', "font": '#fff'},
            "mssql_table":   {"bg": '#2d6a00', "border": '#7ED321', "font": '#fff'},
            "util":          {"bg": '#0e3030', "border": '#48C9B0', "font": '#fff'},
        }

        in_degree = {}
        for edge_item in raw_graph.get("edges", []):
            to_node = edge_item.get("to")
            in_degree[to_node] = in_degree.get(to_node, 0) + 1

        total_nodes = len(raw_graph.get("nodes", []))
        hub_threshold = max(5, int(total_nodes * 0.15))

        dead_code = set()
        if dead_code_json:
            for item in dead_code_json.get("dead_code", []):
                dead_code.add(item.get("id"))

        for node in raw_graph.get("nodes", []):
            nid = node.get("id")
            label = node.get("label", nid)
            raw_type = node.get("type", "function")

            vis_type = "function"
            type_mapping = {
                "view": ["view", "component", "page", "screen", "jsp", "thymeleaf", "vue", "react"],
                "endpoint": ["controller", "endpoint", "route", "api", "rest"],
                "dao": ["dao", "repository", "mapper", "store", "jpa"],
                "external": ["external", "client", "feign", "soap", "sap", "mq", "kafka", "redis"],
                "db_table": ["db", "table", "mssql", "oracle", "mysql", "postgres", "sqlite"],
                "util": ["util", "helper", "common", "config", "constant"]
            }

            if raw_type in ["vue_view", "sap_interface", "mssql_table"]:
                vis_type = raw_type
            else:
                for k, v in type_mapping.items():
                    if raw_type in v:
                        vis_type = k
                        break

            detected_types.add(vis_type)

            node_degree = in_degree.get(nid, 0)
            extra = {}
            if node_degree >= hub_threshold:
                extra["size"] = 28
                extra["borderWidth"] = 3

            if nid in dead_code:
                extra["opacity"] = 0.4

            nodes_data.append({
                "id": nid,
                "label": label,
                "type": vis_type,
                "extra": extra
            })

            meta_data[nid] = {
                "type": vis_type,
                "file": node.get("file", ""),
                "api": node.get("api", ""),
                "note": node.get("note", "")
            }

        for edge_item in raw_graph.get("edges", []):
            edges_data.append({
                "from": edge_item.get("from"),
                "to": edge_item.get("to"),
                "label": edge_item.get("label", ""),
                "dashed": edge_item.get("type") == "depends"
            })

        btn_labels = {
            "view": "🖥 뷰", "vue_view": "🖥 Vue 뷰", "endpoint": "⚡ API 엔드포인트",
            "function": "🔧 서비스/함수", "dao": "🗃 DAO/저장소", "external": "🔶 외부 시스템",
            "sap_interface": "🔶 SAP SOAP", "db_table": "🗄 DB 테이블", "mssql_table": "🗄 MSSQL 테이블",
            "util": "⚙ 유틸"
        }
        filter_buttons_html = ""
        for t in detected_types:
            if t in btn_labels:
                filter_buttons_html += f'<button class="filter-btn active" data-type="{t}">{btn_labels[t]}</button>\n    '

        legend_html = ""
        for t in detected_types:
            if t in COLORS:
                c = COLORS[t]
                cnt = sum(1 for n in nodes_data if n["type"] == t)
                legend_html += f'<div class="legend-item"><div class="legend-dot" style="background:{c["border"]}"></div>{btn_labels.get(t, t)} ({cnt}개)</div>\n        '

        type_counts = {}
        for n in nodes_data:
            type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        extra_stats_html = ""
        for t, cnt in sorted_types:
            extra_stats_html += f'<div class="stat-box"><div class="num">{cnt}</div><div class="lbl">{btn_labels.get(t, t)}</div></div>\n        '

        js_nodes = []
        for n in nodes_data:
            js_nodes.append(f"mkNode('{n['id']}', '{n['label']}', '{n['type']}', {json.dumps(n['extra'])})")

        js_edges = []
        for e in edges_data:
            js_edges.append(f"edge('{e['from']}', '{e['to']}', '{e['label']}', {str(e['dashed']).lower()})")

        js_nodes_array_str = "[\n      " + ",\n      ".join(js_nodes) + "\n    ]"
        js_edges_array_str = "[\n      " + ",\n      ".join(js_edges) + "\n    ]"

        cg_html = cg_template\
            .replace("{{PROJECT_NAME}}", project_name)\
            .replace("{{STACK_DESCRIPTION}}", "정적 분석 결과")\
            .replace("{{FILTER_BUTTONS}}", filter_buttons_html)\
            .replace("{{EXTRA_STATS}}", extra_stats_html)\
            .replace("{{LEGEND_ITEMS}}", legend_html)\
            .replace("{{COLORS}}", json.dumps(COLORS, indent=2))\
            .replace("{{NODES_DATA}}", js_nodes_array_str)\
            .replace("{{EDGES_DATA}}", js_edges_array_str)\
            .replace("{{META}}", json.dumps(meta_data, indent=2))

        write_file(os.path.join(wiki_dir, "call-graph.html"), cg_html)
        print("Generated call-graph.html successfully.")
        page_entries.append(("call-graph.html", "Call Graph (호출 그래프)", "call-graph.html"))

    # 11. index.html (Docsify) + _sidebar.md + _navbar.md + serve.bat
    # Docsify는 file:// 미지원 — serve.bat으로 로컬 서버 실행 필요.
    has_call_graph_file = os.path.exists(os.path.join(wiki_dir, "call-graph.html"))
    present_slugs = {
        os.path.splitext(f)[0]
        for f in os.listdir(wiki_dir)
        if f.endswith(".md") and not f.startswith("_")
    }

    write_file(os.path.join(wiki_dir, "index.html"), wiki_render.render_index(title=f"{project_name} Wiki"))
    print("Generated index.html")

    write_file(os.path.join(wiki_dir, "_sidebar.md"),
               docsify_convert.build_sidebar(project_name, present_slugs, has_call_graph_file))
    print("Generated _sidebar.md")

    write_file(os.path.join(wiki_dir, "_navbar.md"),
               docsify_convert.build_navbar(present_slugs, has_call_graph_file))
    print("Generated _navbar.md")

    write_file(os.path.join(wiki_dir, "serve.bat"), docsify_convert.serve_bat_content())
    print("Generated serve.bat")

    # 12. Write WIKI BUILD REPORT
    build_report_path = os.path.join(project_root, "_workspace", "07_wiki_build.md")
    report_content = f"""=== WIKI BUILD REPORT (zero-LLM) ===

생성 시각: {datetime.now().strftime("%Y-%m-%d %H:%M")}
출력 경로: wiki/

생성된 파일:
- wiki/Home.md              ✅ (원본: CLAUDE.md)
- wiki/architecture.md      ✅ (원본: _workspace/01_analyzer_report.md)
- wiki/workflows.md         ✅ (원본: .claude/skills/*.md)
- wiki/call-graph.html      {"✅" if nodes_data else "⏭"} (노드: {len(nodes_data)}, 엣지: {len(edges_data)})
- wiki/index.html           ✅ (Docsify 4 — serve.bat 실행 후 http://localhost:3501)
- wiki/_sidebar.md          ✅ (Docsify 사이드바 네비게이션)
- wiki/_navbar.md           ✅ (Docsify 상단 네비바)
- wiki/serve.bat            ✅ (python -m http.server 3501)
- wiki/_html/*.html         ✅ ({sum(1 for href, _, _ in page_entries if href.startswith("_html/"))}개 페이지의 브라우저 열람용 렌더 사본)
- wiki/patterns.md          {"✅ (원본: .claude/patterns/*.md)" if patterns_exists else "⏭ (미대상)"}
- wiki/api-endpoints.md     {"✅ (원본: _workspace/index/api_contract.json)" if api_exists else "⏭ (미대상)"}
- wiki/database.md          {"✅ (원본: _workspace/index/schema.json + sql_usage.json)" if db_exists else "⏭ (미대상)"}
- wiki/external-systems.md  {"✅ (원본: _workspace/index/external_io.json)" if external_exists else "⏭ (미대상)"}
- wiki/issues.md            {"✅ (원본: 03_validator_report.md + 04_qa_report.md + dead_code.json)" if issues_exists else "⏭ (미대상)"}
"""
    if merge_info.get("merged"):
        report_content += (
            f"\n크로스 리포 병합 (call-graph.html): ✅ 파트너({merge_info['partner_type']}) 노드 {merge_info['partner_nodes']}개 병합, "
            f"추론된 크로스 엣지 {merge_info['cross_edges']}개 (미매칭 후보 {merge_info['unmatched']}개)\n"
        )
    elif "reason" in merge_info:
        report_content += f"\n크로스 리포 병합 (call-graph.html): ⏭ 스킵 — {merge_info['reason']}\n"

    if partner:
        merged_pages = []
        if partner_report_text:
            merged_pages.append("architecture.md")
        if (partner_api_contract_json or {}).get("endpoints"):
            merged_pages.append("api-endpoints.md")
        if (partner_schema_json or {}).get("tables"):
            merged_pages.append("database.md")
        if (partner_external_io_json or {}).get("communications"):
            merged_pages.append("external-systems.md")
        if merged_pages:
            report_content += f"크로스 리포 병합 (markdown 페이지): ✅ 파트너({partner_label}) 데이터가 {', '.join(merged_pages)}에 병합됨\n"
        else:
            report_content += f"크로스 리포 병합 (markdown 페이지): ⏭ pair_config.md는 있으나 파트너 산출물({partner['analyzer_report']} 등)을 찾지 못함\n"

    storage_line = "저장 위치: 폴더 (wiki/)\n"
    if args.storage == "db":
        try:
            sys.path.insert(0, LIB_DIR)
            import wiki_db
            db_result = wiki_db.save_folder_to_db(project_root, wiki_dir)
            storage_line = (
                f"저장 위치: MSSQL DB ({db_result['synced']}개 페이지 upsert, "
                f"project_name='{db_result['project_name']}') — wiki/ 폴더는 로컬 캐시로 유지\n"
                f"브라우저 확인: python agents/lib/wiki_db_server.py --root \"{project_root}\" 실행 후 http://localhost:8000\n"
            )
        except Exception as e:
            storage_line = f"저장 위치: DB 실패 — {e} (wiki/ 폴더 저장은 정상 완료됨)\n"
    report_content += f"\n{storage_line}"

    report_content += "\n=== END ===\n"
    write_file(build_report_path, report_content)
    print("Generated 07_wiki_build.md report.")

if __name__ == "__main__":
    main()

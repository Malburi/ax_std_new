import os
import json
import re
import sys
import wiki_render

# 템플릿(Home/architecture/call-graph)과 vis-network 라이브러리는 이 스크립트가 속한
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

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hybrid Wiki Builder Generator")
    parser.add_argument("--root", required=True, help="Project root directory")
    parser.add_argument("--wiki-dir", required=True, help="Output wiki directory")
    parser.add_argument("--summary", required=True, help="Path to 07_wiki_summary.json generated by LLM")
    parser.add_argument("--storage", choices=["folder", "db"], default="folder",
                         help="folder(기본): wiki_dir에 파일로만 저장. db: 파일 생성 후 MSSQL(harness_wiki_pages)에도 upsert")
    args = parser.parse_args()

    project_root = args.root
    wiki_dir = args.wiki_dir
    summary_path = args.summary

    print(f"Starting wiki generation. Root: {project_root}, Wiki: {wiki_dir}, Summary: {summary_path}")

    # Load summary and files
    summary = load_json(summary_path) or {}
    
    # Extract project info
    project_name = os.path.basename(os.path.normpath(project_root))
    generation_date = datetime.now().strftime("%Y-%m-%d")
    page_entries = []  # (href, label, source_filename) — 정적 index.html 링크 목록

    # 1. Generate Home.md
    home_template = read_file(os.path.join(LIB_DIR, "Home.template.md"))
    if not home_template:
        print("Home template not found. Using raw default.")
        home_template = "# {{PROJECT_NAME}} Wiki\n\n{{PROJECT_SUMMARY}}"

    conditional_rows = []
    
    # check conditional files
    api_exists = os.path.exists(os.path.join(project_root, "_workspace", "index", "symbols.json")) or "api_endpoints" in summary
    db_exists = os.path.exists(os.path.join(project_root, "_workspace", "index", "schema.json")) or "database" in summary
    patterns_exists = len(os.listdir(os.path.join(project_root, ".claude", "patterns"))) > 0 if os.path.exists(os.path.join(project_root, ".claude", "patterns")) else False
    external_exists = os.path.exists(os.path.join(project_root, "_workspace", "index", "external_io.json"))
    issues_exists = os.path.exists(os.path.join(project_root, "_workspace", "03_validator_report.md"))

    if api_exists:
        conditional_rows.append("| [api-endpoints](api-endpoints.md) | MD | REST API 엔드포인트 목록 |")
    if db_exists:
        conditional_rows.append("| [database](database.md) | MD | DB 스키마·주요 SQL |")
    if patterns_exists:
        conditional_rows.append("| [patterns](patterns.md) | MD | 코드 컨벤션·패턴 요약 |")
    if external_exists:
        conditional_rows.append("| [external-systems](external-systems.md) | MD | 외부 시스템 연동 |")
    if issues_exists:
        conditional_rows.append("| [issues](issues.md) | MD | 발견된 이슈·보완 권장 |")

    call_graph_status = ""
    call_graph_path = os.path.join(project_root, "_workspace", "index", "call_graph.json")
    if not os.path.exists(call_graph_path) or os.path.getsize(call_graph_path) == 0:
        call_graph_status = " (데이터 없음)"

    home_content = home_template\
        .replace("{{PROJECT_NAME}}", project_name)\
        .replace("{{GENERATION_DATE}}", generation_date)\
        .replace("{{PROJECT_SUMMARY}}", summary.get("project_summary", "프로젝트 개요가 정의되지 않았습니다."))\
        .replace("{{CONDITIONAL_ROWS}}", "\n".join(conditional_rows))\
        .replace("{{CALL_GRAPH_STATUS}}", call_graph_status)\
        .replace("{{QUICK_START}}", summary.get("quick_start", "프로젝트 빠른 시작 가이드가 없습니다."))

    write_file(os.path.join(wiki_dir, "Home.md"), home_content)
    render_and_track(wiki_dir, page_entries, project_name, "Home.md", home_content, "Home (프로젝트 개요)")
    print("Generated Home.md")

    # 2. Generate architecture.md
    arch_template = read_file(os.path.join(LIB_DIR, "architecture.template.md"))
    if arch_template:
        arch_content = arch_template\
            .replace("{{TECH_STACK}}", summary.get("tech_stack", "기술 스택 요약이 없습니다."))\
            .replace("{{LAYERS}}", summary.get("layers", "레이어 구조 설명이 없습니다."))\
            .replace("{{FILE_LOCATIONS}}", summary.get("file_locations", "주요 파일 위치 테이블이 없습니다."))\
            .replace("{{REQUEST_FLOW}}", summary.get("request_flow", "요청 흐름 설명이 없습니다."))\
            .replace("{{MODULES}}", summary.get("modules", "모듈 구성 정보가 없습니다."))\
            .replace("{{BUILD_RUN}}", summary.get("build_run", "빌드 및 실행 방법 설명이 없습니다."))
        write_file(os.path.join(wiki_dir, "architecture.md"), arch_content)
        render_and_track(wiki_dir, page_entries, project_name, "architecture.md", arch_content, "Architecture (아키텍처)")
        print("Generated architecture.md")

    # 3. Generate workflows.md
    workflows_data = summary.get("workflows", [])
    workflows_content = "# 하네스 워크플로우 스킬\n\n> harness-fin이 제공하는 스킬들의 사용법과 트리거 문장 모음.\n\n## 스킬 목록\n\n"
    if workflows_data:
        for wf in workflows_data:
            workflows_content += f"### {wf.get('name', '이름 없음')}\n"
            workflows_content += "**트리거 예시:**\n"
            for trig in wf.get("triggers", []):
                workflows_content += f"- \"{trig}\"\n"
            workflows_content += f"\n**언제 사용:** {wf.get('when_to_use', '')}\n\n"
            workflows_content += f"**출력:** {wf.get('output', '')}\n\n---\n\n"
    else:
        workflows_content += "등록된 스킬 정보가 존재하지 않습니다.\n"
    
    workflows_content += "## 에이전트 직접 호출\n[domain-expert 등 직접 호출 에이전트 설명]\n"
    write_file(os.path.join(wiki_dir, "workflows.md"), workflows_content)
    render_and_track(wiki_dir, page_entries, project_name, "workflows.md", workflows_content, "Workflows (워크플로우 스킬)")
    print("Generated workflows.md")

    # 4. Generate conditional pages from summary if present
    page_labels = {
        "api-endpoints": "API Endpoints",
        "database": "Database",
        "patterns": "Patterns",
        "external-systems": "External Systems",
        "issues": "Issues",
    }
    for page_key in ["api-endpoints", "database", "patterns", "external-systems", "issues"]:
        if page_key in summary and summary[page_key]:
            write_file(os.path.join(wiki_dir, f"{page_key}.md"), summary[page_key])
            render_and_track(wiki_dir, page_entries, project_name, f"{page_key}.md",
                              summary[page_key], page_labels[page_key])
            print(f"Generated {page_key}.md")

    # 5. Copy vis-network lib
    src_lib_dir = LIB_DIR
    dest_lib_dir = os.path.join(wiki_dir, "lib")
    os.makedirs(dest_lib_dir, exist_ok=True)
    
    for filename in ["vis-network.min.js", "vis-network.min.css"]:
        src_file = os.path.join(src_lib_dir, filename)
        dest_file = os.path.join(dest_lib_dir, filename)
        if os.path.exists(src_file):
            with open(src_file, 'rb') as sf:
                with open(dest_file, 'wb') as df:
                    df.write(sf.read())
    print("Copied vis-network library files.")

    # 6. Generate call-graph.html (100% Python program-side binding)
    merge_info = {"merged": False}
    cg_template = read_file(os.path.join(LIB_DIR, "call-graph.template.html"))
    if cg_template:
        raw_graph = load_json(call_graph_path) or {"nodes": [], "edges": []}

        # Cross repo merge if pair config exists (nodes/edges merge + method+path 매칭 크로스 엣지)
        raw_graph, merge_info = merge_partner_call_graph(project_root, raw_graph)

        # Normalize and filter types
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

        # Build In-Degree metrics for hub nodes
        in_degree = {}
        for edge_item in raw_graph.get("edges", []):
            to_node = edge_item.get("to")
            in_degree[to_node] = in_degree.get(to_node, 0) + 1
        
        total_nodes = len(raw_graph.get("nodes", []))
        hub_threshold = max(5, int(total_nodes * 0.15))

        # Check dead code list
        dead_code = set()
        dead_code_json = load_json(os.path.join(project_root, "_workspace", "index", "dead_code.json"))
        if dead_code_json:
            for item in dead_code_json.get("dead_code", []):
                dead_code.add(item.get("id"))

        # Map nodes
        for node in raw_graph.get("nodes", []):
            nid = node.get("id")
            label = node.get("label", nid)
            raw_type = node.get("type", "function")
            
            # Map type to visual type
            vis_type = "function"
            type_mapping = {
                "view": ["view", "component", "page", "screen", "jsp", "thymeleaf", "vue", "react"],
                "endpoint": ["controller", "endpoint", "route", "api", "rest"],
                "dao": ["dao", "repository", "mapper", "store", "jpa"],
                "external": ["external", "client", "feign", "soap", "sap", "mq", "kafka", "redis"],
                "db_table": ["db", "table", "mssql", "oracle", "mysql", "postgres", "sqlite"],
                "util": ["util", "helper", "common", "config", "constant"]
            }
            
            # Special stack types
            if raw_type in ["vue_view", "sap_interface", "mssql_table"]:
                vis_type = raw_type
            else:
                for k, v in type_mapping.items():
                    if raw_type in v:
                        vis_type = k
                        break
            
            detected_types.add(vis_type)
            
            # Hub sizing
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

            # Meta mapping
            meta_data[nid] = {
                "type": vis_type,
                "file": node.get("file", ""),
                "api": node.get("api", ""),
                "note": node.get("note", "")
            }

        # Map edges
        for edge_item in raw_graph.get("edges", []):
            edges_data.append({
                "from": edge_item.get("from"),
                "to": edge_item.get("to"),
                "label": edge_item.get("label", ""),
                "dashed": edge_item.get("type") == "depends"
            })

        # Inject to JS Arrays directly via templates
        # Filter buttons
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
        
        # Legend items
        legend_html = ""
        for t in detected_types:
            if t in COLORS:
                c = COLORS[t]
                cnt = sum(1 for n in nodes_data if n["type"] == t)
                legend_html += f'<div class="legend-item"><div class="legend-dot" style="background:{c["border"]}"></div>{btn_labels.get(t, t)} ({cnt}개)</div>\n        '

        # Extra Stats (Top 2 types)
        type_counts = {}
        for n in nodes_data:
            type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
        sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:2]
        extra_stats_html = ""
        for t, cnt in sorted_types:
            extra_stats_html += f'<div class="stat-box"><div class="num">{cnt}</div><div class="lbl">{btn_labels.get(t, t)}</div></div>\n        '

        # Build inline Nodes Javascript representation
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
            .replace("{{STACK_DESCRIPTION}}", summary.get("tech_stack_summary", "정적 분석 결과"))\
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

    # 6.5 Generate index.html — 정적 랜딩 페이지. 서버·CDN 불필요, file://로 직접 열어도 동작.
    index_html = wiki_render.render_index(
        title=f"{project_name} Wiki",
        heading=f"{project_name} — System Wiki",
        entries=[(href, label, "") for href, label, _ in page_entries],
    )
    write_file(os.path.join(wiki_dir, "index.html"), index_html)
    print("Generated index.html")

    # 7. Write WIKI BUILD REPORT
    build_report_path = os.path.join(project_root, "_workspace", "07_wiki_build.md")
    report_content = f"""=== WIKI BUILD REPORT ===

생성 시각: {datetime.now().strftime("%Y-%m-%d %H:%M")}
출력 경로: wiki/

생성된 파일:
- wiki/Home.md              ✅
- wiki/architecture.md      ✅
- wiki/workflows.md         ✅
- wiki/call-graph.html      ✅ (노드: {len(nodes_data) if 'nodes_data' in locals() else 0}, 엣지: {len(edges_data) if 'edges_data' in locals() else 0})
- wiki/index.html           ✅ (정적 랜딩 페이지 — 서버·CDN 불필요, 더블클릭으로 열람 가능)
- wiki/_html/*.html         ✅ ({sum(1 for href, _, _ in page_entries if href.startswith("_html/"))}개 페이지의 브라우저 열람용 렌더 사본)
"""
    if merge_info.get("merged"):
        report_content += (
            f"\n크로스 리포 병합: ✅ 파트너({merge_info['partner_type']}) 노드 {merge_info['partner_nodes']}개 병합, "
            f"추론된 크로스 엣지 {merge_info['cross_edges']}개 (미매칭 후보 {merge_info['unmatched']}개)\n"
        )
    elif "reason" in merge_info:
        report_content += f"\n크로스 리포 병합: ⏭ 스킵 — {merge_info['reason']}\n"

    for page_key in ["api-endpoints", "database", "patterns", "external-systems", "issues"]:
        if page_key in summary and summary[page_key]:
            report_content += f"- wiki/{page_key}.md     ✅\n"
        else:
            report_content += f"- wiki/{page_key}.md     ⏭ (미대상)\n"

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

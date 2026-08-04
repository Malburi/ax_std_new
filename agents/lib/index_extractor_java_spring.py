# Java/Spring 프로젝트의 symbols.json + call_graph.json을 정규식 기반으로 기계 추출한다 (LLM 미사용).
# analyzer.md가 소스를 직접 읽고 이 두 파일을 처음부터 작성하는 대신, 이 스크립트가 먼저
# 결정론적으로 채운다 — 프로젝트 규모에 비례해 커지는 analyzer 입출력 토큰을 없애고,
# 그래프 완전성(import/inherit/inject 누락)을 LLM 꼼꼼함이 아닌 고정 알고리즘에 맡긴다.
#
# 범위(Phase 1): 정규식/텍스트 기반 — javalang 등 외부 AST 파서 의존성 없음. 프로젝트 내부에서
# 해석 가능한 관계만 엣지로 만들고(외부 라이브러리 타입 등 미해석 대상은 조용히 스킵),
# reflect/동적 프록시 같은 런타임 전용 관계는 만들지 않는다 — analyzer가 필요시 보강한다.
# 알려진 한계: 중첩(inner) 클래스는 별도 클래스로도 잡히고 바깥 클래스 메서드 스캔에도
# 섞여 들어갈 수 있다 — Spring Controller/Service/Repository/Entity는 대부분 최상위 클래스라
# Phase 1에서는 감수. 리플렉션/동적 프록시 기반 호출도 탐지하지 않는다(analyzer가 보강).
import os
import re
import sys
import json
import glob
import argparse
import subprocess

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from now_kst import now_kst

SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "out", ".idea", ".vscode", "__pycache__"}

BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"')

PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)(\.\*)?\s*;", re.MULTILINE)

# 클래스/인터페이스/enum 선언 (앞의 애노테이션은 별도로 역방향 스캔해 붙인다)
CLASS_DECL_RE = re.compile(
    r"(?:^|\n)[ \t]*(public|private|protected)?\s*(?:static\s+)?(?:abstract\s+)?(?:final\s+)?"
    r"(class|interface|enum)\s+(\w+)"
    r"(?:\s*<[^{]*?>)?"
    r"(?:\s+extends\s+([\w.<>,\s]+?))?"
    r"(?:\s+implements\s+([\w.<>,\s]+?))?"
    r"\s*\{"
)

METHOD_DECL_RE = re.compile(
    r"(?:^|\n)[ \t]*(public|private|protected)?\s*(static\s+)?(?:final\s+|synchronized\s+|abstract\s+|native\s+)*"
    r"(?:<[\w,\s]+>\s*)?"
    r"([\w<>\[\],.\s]+?)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w.,\s]+)?\s*[{;]"
)

FIELD_DECL_RE = re.compile(
    r"(?:^|\n)[ \t]*(public|private|protected)?\s*(?:static\s+)?(?:final\s+)?"
    r"([\w<>\[\],.]+)\s+(\w+)\s*(?:=[^;]*)?;"
)

ANNOTATION_LINE_RE = re.compile(r"@(\w+)(?:\([^)]*\))?")

CONTROLLER_MARKERS = ("Controller", "RestController")
SERVICE_MARKERS = ("Service", "Repository", "Component", "Configuration")


def _walk_java_files(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".java"):
                files.append(os.path.join(dirpath, fn))
    return files


def _strip_noise(text):
    """주석/문자열 리터럴을 같은 길이의 공백으로 치환 — 줄 번호(line)가 원본 텍스트와
    어긋나지 않게 하기 위해 삭제 대신 공백 치환을 쓴다."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = BLOCK_COMMENT_RE.sub(blank, text)
    text = LINE_COMMENT_RE.sub(blank, text)
    text = STRING_LITERAL_RE.sub(blank, text)
    return text


def _line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def _annotations_before(text, pos):
    """선언 시작 위치(pos, 그 직전 개행 문자 지점) 바로 앞쪽 줄들을 거슬러 올라가며
    @Annotation을 모은다. cursor는 매 반복에서 검사할 줄의 끝(제외) 경계다."""
    anns = []
    cursor = pos
    while True:
        line_start = text.rfind("\n", 0, cursor) + 1
        line = text[line_start:cursor].strip()
        if not line:
            if line_start == 0:
                break
            cursor = line_start - 1
            continue
        m = ANNOTATION_LINE_RE.match(line)
        if not m:
            break
        anns.insert(0, f"@{m.group(1)}")
        if line_start == 0:
            break
        cursor = line_start - 1
    return anns


def _matching_brace(text, open_pos):
    """open_pos가 가리키는 '{' 에 대응하는 '}' 의 인덱스를 찾는다."""
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def _split_type_list(raw):
    if not raw:
        return []
    parts = []
    depth = 0
    buf = ""
    for ch in raw:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf.strip())
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf.strip())
    return [p for p in parts if p]


def _simple_type(raw):
    """제네릭·배열 표기를 벗겨 단순 타입명만 남긴다 (예: List<OrderDto> -> List, String[] -> String)."""
    raw = raw.strip()
    raw = re.sub(r"<.*>", "", raw)
    raw = raw.replace("[]", "")
    return raw.strip().split(".")[-1]


def parse_file(path, rel):
    """파일 하나를 파싱해 클래스 목록(각 클래스는 methods/fields/extends/implements/annotations 포함)과
    import 목록, package를 반환한다. 이 단계에서는 아직 다른 파일과 교차 해석하지 않는다(2-pass 중 1-pass)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()
    except OSError:
        return None

    text = _strip_noise(raw_text)
    pkg_m = PACKAGE_RE.search(text)
    package = pkg_m.group(1) if pkg_m else ""
    imports = [m.group(1) for m in IMPORT_RE.finditer(text) if not m.group(2)]

    classes = []
    for cm in CLASS_DECL_RE.finditer(text):
        visibility, kind, name, extends_raw, implements_raw = cm.groups()
        brace_pos = text.index("{", cm.end() - 1)
        body_end = _matching_brace(text, brace_pos)
        body = text[brace_pos + 1:body_end]
        body_offset = brace_pos + 1

        class_id = f"{package}.{name}" if package else name
        annotations = _annotations_before(text, cm.start())
        line = _line_of(raw_text, cm.start())

        methods = []
        for mm in METHOD_DECL_RE.finditer(body):
            m_vis, m_static, ret_type, m_name, params = mm.groups()
            if m_name == name:
                # 생성자 — 별도 처리(주입 탐지용), call_graph 메서드 노드로는 만들지 않음
                continue
            if ret_type and ret_type.strip() in ("class", "interface", "enum", "new"):
                continue
            m_line = _line_of(raw_text, body_offset + mm.start())
            m_anns = _annotations_before(body, mm.start())
            m_body = ""
            if body[mm.end() - 1] == "{":
                m_body_end = _matching_brace(body, mm.end() - 1)
                m_body = body[mm.end():m_body_end]
            methods.append({
                "name": m_name,
                "line": m_line,
                "visibility": m_vis or "package",
                "static": bool(m_static),
                "annotations": m_anns,
                "signature": f"{(ret_type or '').strip()} {m_name}({params.strip()})".strip(),
                "body": m_body,
            })

        fields = {}
        for fm in FIELD_DECL_RE.finditer(body):
            f_vis, f_type, f_name = fm.groups()
            if f_type in ("class", "return", "new", "void"):
                continue
            f_anns = _annotations_before(body, fm.start())
            fields[f_name] = {"type": _simple_type(f_type), "annotations": f_anns}

        # 생성자 주입: @Autowired가 붙은 생성자의 파라미터 타입들
        constructor_injected_types = []
        ctor_re = re.compile(rf"(?:^|\n)[ \t]*(?:public|private|protected)?\s*{re.escape(name)}\s*\(([^)]*)\)\s*\{{")
        for cm2 in ctor_re.finditer(body):
            ctor_anns = _annotations_before(body, cm2.start())
            if "@Autowired" not in ctor_anns and len(list(ctor_re.finditer(body))) > 1:
                # 생성자가 여러 개면 @Autowired 명시된 것만 주입 생성자로 간주
                continue
            for param in _split_type_list(cm2.group(1)):
                param = param.strip()
                if not param:
                    continue
                tokens = param.replace("final ", "").split()
                if len(tokens) >= 2:
                    constructor_injected_types.append(_simple_type(tokens[-2]))

        classes.append({
            "id": class_id,
            "name": name,
            "kind": kind,
            "package": package,
            "file": rel,
            "line": line,
            "visibility": visibility or "package",
            "annotations": annotations,
            "extends_raw": _simple_type(extends_raw) if extends_raw else None,
            "implements_raw": [_simple_type(t) for t in _split_type_list(implements_raw)],
            "methods": methods,
            "fields": fields,
            "constructor_injected_types": constructor_injected_types,
            "body": body,
            "body_offset": body_offset,
            "raw_text": raw_text,
        })

    return {"package": package, "imports": imports, "classes": classes}


def _resolve(simple_name, importer_imports, importer_package, by_id, by_simple):
    """simple_name(단순 타입명)을 프로젝트 내부에서 파싱된 class id로 해석한다.
    해석 불가(외부 라이브러리 등)면 None — 추측으로 엣지를 만들지 않는다."""
    if not simple_name:
        return None
    for imp in importer_imports:
        if imp.endswith("." + simple_name) or imp == simple_name:
            if imp in by_id:
                return imp
    same_pkg = f"{importer_package}.{simple_name}" if importer_package else simple_name
    if same_pkg in by_id:
        return same_pkg
    candidates = by_simple.get(simple_name) or []
    if len(candidates) == 1:
        return candidates[0]
    return None


def build_indexes(root):
    files = _walk_java_files(root)
    parsed = []
    for path in files:
        rel = os.path.relpath(path, root).replace("\\", "/")
        result = parse_file(path, rel)
        if result:
            parsed.append(result)

    by_id = {}
    by_simple = {}
    for p in parsed:
        for c in p["classes"]:
            by_id[c["id"]] = c
            by_simple.setdefault(c["name"], []).append(c["id"])

    symbols = []
    nodes = []
    edges = []

    for p in parsed:
        for c in p["classes"]:
            method_syms = [
                {"name": m["name"], "id": f"{c['id']}.{m['name']}", "line": m["line"], "visibility": m["visibility"]}
                for m in c["methods"]
            ]
            symbols.append({
                "id": c["id"],
                "type": c["kind"],
                "file": c["file"],
                "line": c["line"],
                "package": c["package"],
                "extends": c["extends_raw"],
                "implements": c["implements_raw"],
                "annotations": c["annotations"],
                "methods": method_syms,
            })

            node_type = "class" if c["kind"] == "class" else c["kind"]
            nodes.append({
                "id": c["id"], "type": node_type, "file": c["file"], "line": c["line"],
                "visibility": c["visibility"], "static": False, "annotations": c["annotations"],
                "signature": "",
            })
            for m in c["methods"]:
                nodes.append({
                    "id": f"{c['id']}.{m['name']}", "type": "method", "file": c["file"], "line": m["line"],
                    "visibility": m["visibility"], "static": m["static"], "annotations": m["annotations"],
                    "signature": m["signature"],
                })

    for p in parsed:
        for c in p["classes"]:
            # inherit: extends/implements
            for raw in [c["extends_raw"]] + c["implements_raw"]:
                target = _resolve(raw, p["imports"], p["package"], by_id, by_simple)
                if target:
                    edges.append({"from": c["id"], "to": target, "type": "inherit", "file": c["file"], "line": c["line"]})

            # inject: @Autowired 필드 + @Autowired 생성자 파라미터
            injected_type_names = list(c["constructor_injected_types"])
            for f_name, f_info in c["fields"].items():
                if "@Autowired" in f_info["annotations"] or "@Inject" in f_info["annotations"]:
                    injected_type_names.append(f_info["type"])
            for type_name in injected_type_names:
                target = _resolve(type_name, p["imports"], p["package"], by_id, by_simple)
                if target and target != c["id"]:
                    edges.append({"from": c["id"], "to": target, "type": "inject", "file": c["file"], "line": c["line"]})

            # import: 프로젝트 내부 타입을 가리키는 import만
            for imp in p["imports"]:
                if imp in by_id and imp != c["id"]:
                    edges.append({"from": c["id"], "to": imp, "type": "import", "file": c["file"], "line": None})

            # call: 필드 호출(fieldVar.method(...)) + 자기 클래스 호출(this.method(...))
            # 메서드 경계까지 정밀 추적하지 않고 클래스 본문 전체에서 스캔 — 호출부가 어느
            # 메서드에서 일어났는지는 무시하고 "이 클래스의 모든 메서드 → 대상"으로 단순화하면
            # 오탐이 커지므로, 실제로는 아래에서 메서드별로 다시 스캔한다(범위는 클래스 본문 전체,
            # 발신 메서드만 구분).
            field_types = {name: info["type"] for name, info in c["fields"].items()}
            resolved_field_targets = {}
            for f_name, f_type in field_types.items():
                target_cls = _resolve(f_type, p["imports"], p["package"], by_id, by_simple)
                if target_cls and target_cls in by_id:
                    resolved_field_targets[f_name] = target_cls

            own_methods = {m["name"] for m in c["methods"]}
            for m in c["methods"]:
                m_body = m["body"]
                if not m_body:
                    continue
                for f_name, target_cls in resolved_field_targets.items():
                    target_methods = {tm["name"] for tm in by_id[target_cls]["methods"]}
                    for call_m in re.finditer(rf"\b{re.escape(f_name)}\s*\.\s*(\w+)\s*\(", m_body):
                        called = call_m.group(1)
                        if called in target_methods:
                            edges.append({
                                "from": f"{c['id']}.{m['name']}", "to": f"{target_cls}.{called}",
                                "type": "call", "file": c["file"], "line": None,
                            })
                for call_m in re.finditer(r"\bthis\s*\.\s*(\w+)\s*\(", m_body):
                    called = call_m.group(1)
                    if called in own_methods and called != m["name"]:
                        edges.append({
                            "from": f"{c['id']}.{m['name']}", "to": f"{c['id']}.{called}",
                            "type": "call", "file": c["file"], "line": None,
                        })

    # dedupe edges (from,to,type) 동일 조합 중복 제거
    seen = set()
    dedup_edges = []
    for e in edges:
        key = (e["from"], e["to"], e["type"])
        if key in seen:
            continue
        seen.add(key)
        dedup_edges.append(e)

    return symbols, nodes, dedup_edges, len(parsed), len(files)


def _git_commit(root):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _base_meta(root, files_scanned, files_total):
    return {
        "generated_at": now_kst(),
        "generator": "index_extractor_java_spring",
        "version": "1.0",
        "source_root": root,
        "mode": "init",
        "git_commit": _git_commit(root),
        "sampled": False,
        "files_scanned": files_scanned,
        "files_total": files_total,
    }


def main():
    parser = argparse.ArgumentParser(description="Java/Spring symbols.json + call_graph.json 기계 추출 (LLM 미사용)")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    symbols, nodes, edges, files_scanned, files_total = build_indexes(args.root)

    index_dir = os.path.join(args.root, "_workspace", "index")
    os.makedirs(index_dir, exist_ok=True)

    symbols_meta = _base_meta(args.root, files_scanned, files_total)
    symbols_meta["node_count"] = len(symbols)
    symbols_meta["edge_count"] = 0
    with open(os.path.join(index_dir, "symbols.json"), "w", encoding="utf-8") as f:
        json.dump({"_meta": symbols_meta, "symbols": symbols}, f, indent=2, ensure_ascii=False)

    cg_meta = _base_meta(args.root, files_scanned, files_total)
    cg_meta["node_count"] = len(nodes)
    cg_meta["edge_count"] = len(edges)
    with open(os.path.join(index_dir, "call_graph.json"), "w", encoding="utf-8") as f:
        json.dump({"_meta": cg_meta, "nodes": nodes, "edges": edges}, f, indent=2, ensure_ascii=False)

    print(f"symbols.json: {len(symbols)}개 심볼 ({files_scanned}/{files_total} 파일)")
    print(f"call_graph.json: 노드 {len(nodes)}개, 엣지 {len(edges)}개")
    edge_types = {}
    for e in edges:
        edge_types[e["type"]] = edge_types.get(e["type"], 0) + 1
    for t, c in sorted(edge_types.items()):
        print(f"  - {t}: {c}")


if __name__ == "__main__":
    main()

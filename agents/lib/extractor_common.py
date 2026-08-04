# 스택별 index_extractor_*.py가 공유하는 보일러플레이트 (LLM 미사용).
# Java/Spring(index_extractor_java_spring.py)에서 검증 끝난 로직을 그대로 뽑아왔다 —
# 여기서 동작을 바꾸면 이미 검증된 java_spring 추출기까지 영향받으니 신중히 다룰 것.
import os
import re
import json
import subprocess

from now_kst import now_kst

SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "out", ".idea", ".vscode", "__pycache__", "bin", "obj"}

# C-계열 문법(//, /* */, "...") 공용 — Java/C#/Kotlin과 Vue <script> 블록(JS/TS)이 모두 해당.
# 백틱(`) 템플릿 리터럴은 다루지 않음(알려진 한계, JS/TS 흔한 패턴이라 향후 보강 여지).
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT_RE = re.compile(r"//[^\n]*")
STRING_LITERAL_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def strip_noise(text):
    """주석/문자열 리터럴을 같은 길이의 공백으로 치환 — 줄 번호(line)가 원본 텍스트와
    어긋나지 않게 하기 위해 삭제 대신 공백 치환을 쓴다."""
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))
    text = BLOCK_COMMENT_RE.sub(blank, text)
    text = LINE_COMMENT_RE.sub(blank, text)
    text = STRING_LITERAL_RE.sub(blank, text)
    return text


def walk_files(root, suffix, skip_dirs=SKIP_DIRS):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if fn.endswith(suffix):
                files.append(os.path.join(dirpath, fn))
    return files


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def annotations_before(text, pos, marker_re, format_fn=None):
    """선언 시작 위치(pos, 그 직전 개행 문자 지점) 바로 앞쪽 줄들을 거슬러 올라가며
    marker_re(예: @Foo 또는 [Foo])에 매치되는 줄을 모은다. format_fn(match)로 기록할
    문자열을 결정 — 기본은 매치 전체(group(0)), 언어별로 괄호 인자 포함 여부를 다르게
    하려면 커스텀 format_fn을 넘긴다."""
    if format_fn is None:
        format_fn = lambda m: m.group(0).strip()
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
        m = marker_re.match(line)
        if not m:
            break
        anns.insert(0, format_fn(m))
        if line_start == 0:
            break
        cursor = line_start - 1
    return anns


def matching_brace(text, open_pos):
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


def split_type_list(raw):
    """콤마로 구분된 타입 목록을 <>(제네릭) 중첩은 무시하고 분리한다."""
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


def simple_type(raw):
    """제네릭·배열 표기를 벗겨 단순 타입명만 남긴다 (예: List<OrderDto> -> List, string[] -> string)."""
    raw = raw.strip()
    raw = re.sub(r"<.*>", "", raw)
    raw = raw.replace("[]", "")
    return raw.strip().split(".")[-1]


def dedupe_edges(edges):
    seen = set()
    result = []
    for e in edges:
        key = (e["from"], e["to"], e["type"])
        if key in seen:
            continue
        seen.add(key)
        result.append(e)
    return result


def git_commit(root):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def base_meta(root, generator, files_scanned, files_total):
    return {
        "generated_at": now_kst(),
        "generator": generator,
        "version": "1.0",
        "source_root": root,
        "mode": "init",
        "git_commit": git_commit(root),
        "sampled": False,
        "files_scanned": files_scanned,
        "files_total": files_total,
    }


def _load_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_outputs(root, generator, symbols, nodes, edges, files_scanned, files_total):
    """symbols.json + call_graph.json을 _workspace/index/에 표준 스키마로 저장한다.
    이미 파일이 있으면(모노레포 등에서 다른 스택 추출기가 같은 회차에 먼저 실행된 경우)
    덮어쓰지 않고 병합한다 — harness-init 2-0.5는 감지된 스택마다 이 함수를 순서대로
    호출하므로, 병합하지 않으면 나중에 실행된 추출기가 앞선 결과를 지워버린다."""
    index_dir = os.path.join(root, "_workspace", "index")
    os.makedirs(index_dir, exist_ok=True)
    symbols_path = os.path.join(index_dir, "symbols.json")
    cg_path = os.path.join(index_dir, "call_graph.json")

    existing_symbols = _load_json(symbols_path)
    prev_scanned, prev_total = 0, 0
    if existing_symbols and isinstance(existing_symbols.get("symbols"), list):
        symbols = existing_symbols["symbols"] + symbols
        prev_meta = existing_symbols.get("_meta") or {}
        prev_scanned = prev_meta.get("files_scanned") or 0
        prev_total = prev_meta.get("files_total") or 0

    existing_cg = _load_json(cg_path)
    if existing_cg and isinstance(existing_cg.get("nodes"), list):
        nodes = existing_cg["nodes"] + nodes
        edges = dedupe_edges(existing_cg.get("edges", []) + edges)

    total_scanned = prev_scanned + files_scanned
    total_files = prev_total + files_total

    symbols_meta = base_meta(root, generator, total_scanned, total_files)
    symbols_meta["node_count"] = len(symbols)
    symbols_meta["edge_count"] = 0
    with open(symbols_path, "w", encoding="utf-8") as f:
        json.dump({"_meta": symbols_meta, "symbols": symbols}, f, indent=2, ensure_ascii=False)

    cg_meta = base_meta(root, generator, total_scanned, total_files)
    cg_meta["node_count"] = len(nodes)
    cg_meta["edge_count"] = len(edges)
    with open(cg_path, "w", encoding="utf-8") as f:
        json.dump({"_meta": cg_meta, "nodes": nodes, "edges": edges}, f, indent=2, ensure_ascii=False)


def print_summary(symbols, nodes, edges, files_scanned, files_total):
    print(f"symbols.json: {len(symbols)}개 심볼 ({files_scanned}/{files_total} 파일)")
    print(f"call_graph.json: 노드 {len(nodes)}개, 엣지 {len(edges)}개")
    edge_types = {}
    for e in edges:
        edge_types[e["type"]] = edge_types.get(e["type"], 0) + 1
    for t, c in sorted(edge_types.items()):
        print(f"  - {t}: {c}")

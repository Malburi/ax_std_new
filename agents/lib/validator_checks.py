# validator 10개 체크 중 8개를 기계 실행하는 zero-LLM 검사기 (LLM 담당은 체크 5·10만)
import os
import re
import sys
import json
import glob
import argparse

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# validator.md의 10개 검증 항목 중 1,2,3,4,6,7,8,9는 file-exists/JSON-parse/regex-grep 뿐이라
# LLM 판단이 필요 없다. 이 스크립트가 그 8개를 대신 계산하고, validator(LLM)는 체크 5(레이어
# 커버리지)와 체크 10 중 이 스크립트가 "판정 불가"로 남긴 항목에만 집중한다.
# 점수 산식은 validator.md의 "신뢰도 점수 산식"과 동일: FAIL -10, WARN -3, 보안 위험 1건 -15
# (최대 -45), 인덱스 무결성 FAIL -15, 변경 이력 누락 -5.

SECURITY_PATTERNS = [
    ("PASSWORD", re.compile(r"password\s*[:=]\s*\S{4,}", re.IGNORECASE)),
    ("API_KEY", re.compile(r"(api[_-]?key|secret[_-]?key)\s*[:=]\s*\S{8,}", re.IGNORECASE)),
    ("DB_HOST", re.compile(r"jdbc:.*//[^/]*:[^/]*@")),
    ("INTERNAL_IP", re.compile(r"(10|192\.168|172\.(1[6-9]|2[0-9]|3[01]))\.\d+\.\d+")),
    ("INTERNAL_DOMAIN", re.compile(r"\.(corp|internal|local|lan)\b")),
]

CORE_INDEX_FILES = ["call_graph.json", "symbols.json", "transactions.json", "external_io.json"]
SKELETON_MARKER = "pattern-extractor 에이전트가 채울 예정입니다"
PROJECT_PATH_PREFIXES = (
    "src/", "app/", "lib/", "pages/", "components/", "test/", "tests/",
    "WEB-INF/", "routes/", "controllers/", "services/", "models/",
)


def _read(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except OSError:
        return None


def _frontmatter_fields(text):
    m = re.match(r"^---\n(.*?)\n---", text or "", re.DOTALL)
    if not m:
        return {}
    body = m.group(1)
    fields = {}
    for key in ("name", "description", "model"):
        km = re.search(rf"^{key}:\s*(.+)$", body, re.MULTILINE)
        if km:
            fields[key] = km.group(1).strip()
    return fields


# ---------------------------------------------------------------------------
# Check 1: 파일 존재 및 완성도
# ---------------------------------------------------------------------------

def check1_file_existence(root):
    results = []
    claude_md = _read(os.path.join(root, "CLAUDE.md"))
    if claude_md is None:
        results.append(("FAIL", "CLAUDE.md 없음"))
    else:
        required_headers = ["## 요청 흐름", "## 빌드 / 실행", "## 자동 워크플로우", "## 변경 이력"]
        missing = [h for h in required_headers if h not in claude_md]
        if missing:
            results.append(("FAIL", f"CLAUDE.md 필수 섹션 누락: {', '.join(missing)}"))
        else:
            results.append(("PASS", "CLAUDE.md 필수 섹션 확인"))
        if len(claude_md.splitlines()) > 500:
            results.append(("WARN", "CLAUDE.md 500줄 초과"))

    for name in ("trace.md", "scaffolder.md", "find-logic.md"):
        path = os.path.join(root, ".claude", "skills", name)
        text = _read(path)
        if text is None:
            results.append(("FAIL", f".claude/skills/{name} 없음"))
            continue
        fm = _frontmatter_fields(text)
        if not fm.get("name") or not fm.get("description"):
            results.append(("WARN", f".claude/skills/{name} frontmatter(name/description) 불완전"))
        elif len(text.splitlines()) < 5:
            results.append(("WARN", f".claude/skills/{name} 내용 부족 의심"))
        else:
            results.append(("PASS", f".claude/skills/{name} 존재·frontmatter 확인"))

    domain_expert = _read(os.path.join(root, ".claude", "agents", "domain-expert.md"))
    if domain_expert is None:
        results.append(("FAIL", ".claude/agents/domain-expert.md 없음"))
    else:
        fm = _frontmatter_fields(domain_expert)
        if not fm.get("name") or not fm.get("description"):
            results.append(("WARN", "domain-expert.md frontmatter 불완전"))
        else:
            results.append(("PASS", "domain-expert.md 존재·frontmatter 확인"))

    patterns_dir = os.path.join(root, ".claude", "patterns")
    pattern_files = glob.glob(os.path.join(patterns_dir, "*.md")) if os.path.isdir(patterns_dir) else []
    if not pattern_files:
        results.append(("WARN", ".claude/patterns/ 파일 없음"))
    else:
        results.append(("PASS", f".claude/patterns/ {len(pattern_files)}개 파일 존재"))
        for p in pattern_files:
            text = _read(p) or ""
            if len(text.splitlines()) > 300:
                results.append(("WARN", f"{os.path.basename(p)} 300줄 초과"))

    return results


# ---------------------------------------------------------------------------
# Check 2: 워크플로우 스킬 등록 확인
# ---------------------------------------------------------------------------

def check2_skill_registration(root, decisions, claude_md_text):
    results = []
    skills_dir = os.path.join(root, ".claude", "skills")

    for name in ("analyze-impact", "safe-modify", "scaffold-feature"):
        exists = os.path.isfile(os.path.join(skills_dir, f"{name}.md"))
        if not exists:
            results.append(("FAIL", f"{name}.md 미생성 (항상 존재해야 함)"))
        else:
            results.append(("PASS", f"{name}.md 존재"))

    for name, key in (("plan-migration", "plan_migration"), ("review-sql", "review_sql")):
        should_generate = bool((decisions or {}).get(key, {}).get("generate"))
        exists = os.path.isfile(os.path.join(skills_dir, f"{name}.md"))
        if should_generate and not exists:
            results.append(("WARN", f"{name}.md 생성 결정되었으나 파일 없음 — 배포 실패 의심"))
        elif exists:
            results.append(("PASS", f"{name}.md 존재"))

    if claude_md_text:
        for name in ("analyze-impact", "safe-modify", "scaffold-feature"):
            if os.path.isfile(os.path.join(skills_dir, f"{name}.md")) and name not in claude_md_text:
                results.append(("WARN", f"CLAUDE.md 자동 워크플로우 테이블에 {name} 미등록"))

    return results


# ---------------------------------------------------------------------------
# Check 3: 스킬 트리거 품질 검사
# ---------------------------------------------------------------------------

KOREAN_QUOTE_RE = re.compile(r'"([^"]*[가-힣][^"]*)"')
ASCII_QUOTE_RE = re.compile(r'"([a-zA-Z][a-zA-Z \-]*)"')

# 정적 배포 스킬(agents/lib/skills/*.md.template, 프로젝트별 변수 없음)은 매 프로젝트마다 새로
# 판단할 트리거 품질이 없다 — check 3은 writer가 실제로 새로 작성한 per-project 스킬
# (trace/scaffolder/find-logic/cross-repo-*)에만 적용. harness-init.md는 2026-07-23부터
# 프로젝트에 배포하지 않으므로(메타/툴링 스킬 — 하네스 재초기화용이지 개발 워크플로우가 아님)
# 이 목록에서 제외했다. 혹시 과거 세션에서 수동 배포된 사본이 남아있어도 이 목록에 없으면
# check3이 일반 per-project 스킬과 동일하게 트리거 품질을 검사하게 되는데, 이는 의도된
# 부작용이다 — 남아있는 사본은 트리거 부실 WARN으로 존재가 드러나 정리 대상임을 알 수 있다.
STATIC_OR_PREEXISTING_SKILLS = {
    "analyze-impact.md", "safe-modify.md", "scaffold-feature.md",
    "plan-migration.md", "review-sql.md",
}


def check3_trigger_quality(root, decisions):
    results = []
    skills_dir = os.path.join(root, ".claude", "skills")
    stack_tokens = [
        t for t in re.split(r"[^0-9A-Za-z가-힣]+", (decisions or {}).get("detected_stack", "") or "")
        if len(t) >= 3
    ]

    for path in sorted(glob.glob(os.path.join(skills_dir, "*.md"))):
        name = os.path.basename(path)
        if name in STATIC_OR_PREEXISTING_SKILLS:
            continue
        text = _read(path) or ""
        fm = _frontmatter_fields(text)
        desc = fm.get("description", "")

        if len(desc) < 100:
            results.append(("WARN", f"{name} description 100자 미만 ({len(desc)}자)"))
        ko_triggers = len(KOREAN_QUOTE_RE.findall(desc))
        if ko_triggers < 3:
            results.append(("WARN", f"{name} 한국어 트리거 {ko_triggers}개 (3개 미만)"))
        en_triggers = len([m for m in ASCII_QUOTE_RE.findall(desc) if not re.search(r"[가-힣]", m)])
        if en_triggers < 2:
            results.append(("WARN", f"{name} 영어 트리거 {en_triggers}개 (2개 미만)"))
        if stack_tokens and not any(tok.lower() in desc.lower() for tok in stack_tokens):
            results.append(("WARN", f"{name} 스택 특화 키워드 미확인 (수동 확인 권장)"))
        if not fm.get("model"):
            results.append(("FAIL", f"{name} model 필드 없음"))

    return results


# ---------------------------------------------------------------------------
# Check 4: 프로젝트 파일과 교차 검증
# ---------------------------------------------------------------------------

PATH_RE = re.compile(r"`([\w./\-]+/[\w./\-]+)`")


def _partner_root(root):
    """pair_config.md의 partner_root: 값을 읽는다 — cross-repo 스킬이 파트너 저장소
    경로를 예시로 인용할 때 이를 '없는 경로'로 오탐하지 않기 위해 필요."""
    text = _read(os.path.join(root, "_workspace", "pair_config.md"))
    if not text:
        return None
    m = re.search(r"^partner_root:\s*(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def check4_path_crosscheck(root):
    results = []
    candidates = set()
    for pattern in (".claude/skills/*.md", ".claude/patterns/*.md"):
        for path in glob.glob(os.path.join(root, pattern)):
            text = _read(path) or ""
            for m in PATH_RE.findall(text):
                if m.startswith(PROJECT_PATH_PREFIXES):
                    candidates.add(m)

    partner_root = _partner_root(root)

    def _exists(rel_path):
        stripped = rel_path.rstrip("/\\")
        full = os.path.join(root, stripped)
        if os.path.isfile(full) or os.path.isdir(full):
            return True
        if partner_root:
            partner_full = os.path.join(partner_root, stripped)
            if os.path.isfile(partner_full) or os.path.isdir(partner_full):
                return True
        return False

    missing = [p for p in sorted(candidates) if not _exists(p)]
    if missing:
        for p in missing:
            results.append(("FAIL", f"참조 경로 없음: {p}"))
    elif candidates:
        results.append(("PASS", f"참조 경로 {len(candidates)}개 확인"))
    return results


# ---------------------------------------------------------------------------
# Check 6: 보안 위험 확인
# ---------------------------------------------------------------------------

def check6_security_scan(root):
    findings = []
    targets = []
    targets.append(os.path.join(root, "CLAUDE.md"))
    targets.extend(glob.glob(os.path.join(root, ".claude", "skills", "*.md")))
    targets.extend(glob.glob(os.path.join(root, ".claude", "patterns", "*.md")))
    targets.extend(glob.glob(os.path.join(root, ".claude", "agents", "*.md")))
    targets.extend(glob.glob(os.path.join(root, "_workspace", "index", "*.json")))

    for path in targets:
        text = _read(path)
        if not text:
            continue
        for label, pattern in SECURITY_PATTERNS:
            for m in pattern.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                findings.append(f"[{label}] {os.path.relpath(path, root)}:{line}")

    return findings


# ---------------------------------------------------------------------------
# Check 7: 인덱스 무결성
# ---------------------------------------------------------------------------

def check7_index_integrity(root, analyzer_report_text):
    index_dir = os.path.join(root, "_workspace", "index")
    lines = []
    missing_core = 0
    parse_failures = 0
    call_graph_empty = False

    for name in CORE_INDEX_FILES:
        path = os.path.join(index_dir, name)
        if not os.path.isfile(path):
            lines.append(f"- {name}: WARN (없음)")
            missing_core += 1
            continue
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            lines.append(f"- {name}: FAIL (JSON 파싱 실패)")
            parse_failures += 1
            continue

        if name == "call_graph.json":
            nodes = len(data.get("nodes") or [])
            edges = len(data.get("edges") or [])
            call_graph_empty = (nodes == 0 and edges == 0)
            status = "FAIL (노드/엣지 0)" if call_graph_empty else "PASS"
            lines.append(f"- {name}: {status} (노드 {nodes}, 엣지 {edges})")
        else:
            lines.append(f"- {name}: PASS")

    confidence_m = re.search(r"의존성 그래프 완전성:\s*(HIGH|MEDIUM|LOW)", analyzer_report_text or "")
    stale_mismatch = False
    if confidence_m and confidence_m.group(1) in ("HIGH", "MEDIUM") and call_graph_empty:
        stale_mismatch = True
        lines.append("- 신뢰도 불일치: 분석 신뢰도 MEDIUM 이상인데 call_graph가 비어있음")

    fail = missing_core >= 2 or parse_failures > 0 or call_graph_empty or stale_mismatch
    return fail, "\n".join(lines)


# ---------------------------------------------------------------------------
# Check 7b: 인덱스 내용 스팟체크 (엣지·SQL 실측 대조 — LLM이 만든 인덱스의 내용 정확성 게이트)
# ---------------------------------------------------------------------------

SPOTCHECK_EDGE_SAMPLES = 20
SPOTCHECK_SQL_SAMPLES = 10
SPOTCHECK_MIN_CHECKABLE = 5
SPOTCHECK_PASS_RATE = 0.8


def _evenly_spaced(items, n):
    """결정론적 샘플링 — random 대신 정렬 후 균등 간격 추출 (재실행 시 같은 결과)."""
    if len(items) <= n:
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


NODE_TYPE_PREFIX_RE = re.compile(r"^[a-z][a-z_-]*:(?!//)")


def _simple_name(symbol_id):
    """'com.example.OrderService.cancel' / 'src/x.ts::cancelOrder' → 'cancel' / 'cancelOrder'.
    일부 analyzer는 노드 id를 'sql:PKG_X' / 'page:Menu.vue' / 'route:/lo'처럼 type: 접두사로
    낸다 — 이 접두사를 벗기지 않으면 실제 소스에 없는 문자열을 찾아 스팟체크가 오탐(FAIL)한다."""
    symbol_id = NODE_TYPE_PREFIX_RE.sub("", symbol_id, count=1)
    tail = symbol_id.rsplit("::", 1)[-1]
    tail = tail.rsplit(".", 1)[-1]
    return tail.split("(", 1)[0].strip()


def check7b_spotcheck(root):
    """call_graph 엣지·sql_usage 항목을 실제 소스와 대조한다.
    qa Boundary 5(온디맨드)와 달리 기본 파이프라인에서 항상 도는 기계 게이트."""
    index_dir = os.path.join(root, "_workspace", "index")
    lines = []
    fail = False

    # --- call_graph 엣지: from 쪽 파일에 callee 단순명이 실제로 등장하는가 ---
    cg_path = os.path.join(index_dir, "call_graph.json")
    if os.path.isfile(cg_path):
        try:
            with open(cg_path, "r", encoding="utf-8-sig") as f:
                cg = json.load(f)
        except (json.JSONDecodeError, OSError):
            cg = None
        if cg:
            node_file = {n.get("id"): n.get("file") for n in (cg.get("nodes") or []) if isinstance(n, dict)}
            edges = [e for e in (cg.get("edges") or []) if isinstance(e, dict) and e.get("from") and e.get("to")]
            edges.sort(key=lambda e: (str(e.get("from")), str(e.get("to"))))
            hits = checked = missing_files = 0
            misses = []
            for e in _evenly_spaced(edges, SPOTCHECK_EDGE_SAMPLES):
                src_rel = e.get("file") or node_file.get(e.get("from"))
                if not src_rel:
                    continue
                src_text = _read(os.path.join(root, src_rel))
                if src_text is None:
                    missing_files += 1
                    continue
                checked += 1
                callee = _simple_name(str(e.get("to")))
                if callee and re.search(rf"\b{re.escape(callee)}\b", src_text):
                    hits += 1
                else:
                    misses.append(f"{e.get('from')} → {e.get('to')} ({src_rel})")
            if checked >= SPOTCHECK_MIN_CHECKABLE:
                rate = hits / checked
                status = "PASS" if rate >= SPOTCHECK_PASS_RATE else "FAIL"
                if status == "FAIL":
                    fail = True
                lines.append(f"- call_graph 엣지 스팟체크: {status} ({hits}/{checked} 일치, 기준 {int(SPOTCHECK_PASS_RATE*100)}%)")
                for m in misses[:5]:
                    lines.append(f"  - 불일치: {m}")
            else:
                lines.append(f"- call_graph 엣지 스팟체크: 판정 불가 (대조 가능 엣지 {checked}개 < {SPOTCHECK_MIN_CHECKABLE})")
            if missing_files:
                lines.append(f"  - 소스 파일 자체가 없는 엣지 {missing_files}개 (경로 오류 또는 stale 인덱스 의심)")

    # --- sql_usage: 매퍼 파일에 SQL ID가, 사용처 파일에 참조가 실제로 있는가 ---
    su_path = os.path.join(index_dir, "sql_usage.json")
    if os.path.isfile(su_path):
        try:
            with open(su_path, "r", encoding="utf-8-sig") as f:
                su = json.load(f)
        except (json.JSONDecodeError, OSError):
            su = None
        if su:
            hits = checked = 0
            misses = []
            entries = sorted(
                [s for s in (su.get("sqls") or []) if isinstance(s, dict) and s.get("id") and s.get("file")],
                key=lambda s: str(s.get("id")),
            )
            for s in _evenly_spaced(entries, SPOTCHECK_SQL_SAMPLES):
                text = _read(os.path.join(root, s["file"]))
                if text is None:
                    misses.append(f"{s['id']} (파일 없음: {s['file']})")
                    checked += 1
                    continue
                checked += 1
                if str(s["id"]) in text:
                    hits += 1
                else:
                    misses.append(f"{s['id']} ({s['file']}에 미존재)")
            if checked >= SPOTCHECK_MIN_CHECKABLE:
                rate = hits / checked
                status = "PASS" if rate >= SPOTCHECK_PASS_RATE else "FAIL"
                if status == "FAIL":
                    fail = True
                lines.append(f"- sql_usage 스팟체크: {status} ({hits}/{checked} 일치)")
                for m in misses[:5]:
                    lines.append(f"  - 불일치: {m}")
            elif checked:
                lines.append(f"- sql_usage 스팟체크: 판정 불가 (대조 가능 항목 {checked}개 < {SPOTCHECK_MIN_CHECKABLE})")

    return fail, lines


def _index_meta_freshness(root):
    """_meta.git_commit이 있으면 현재 HEAD와 대조해 드리프트를 알린다 (감점 없음, 정보성)."""
    import subprocess
    cg_path = os.path.join(root, "_workspace", "index", "call_graph.json")
    if not os.path.isfile(cg_path):
        return []
    try:
        with open(cg_path, "r", encoding="utf-8-sig") as f:
            meta = (json.load(f) or {}).get("_meta") or {}
    except (json.JSONDecodeError, OSError):
        return []
    lines = []
    if meta.get("sampled"):
        scanned, total = meta.get("files_scanned"), meta.get("files_total")
        cov = f" (커버리지 {scanned}/{total})" if scanned and total else ""
        lines.append(f"- 인덱스가 샘플링 모드로 생성됨{cov} — dead_code 등 파생 결과 신뢰도 낮음")
    commit = meta.get("git_commit")
    if commit:
        try:
            head = subprocess.run(
                ["git", "-C", root, "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            if head and head != commit:
                lines.append(f"- 인덱스 생성 시점 커밋({commit[:8]}) ≠ 현재 HEAD({head[:8]}) — 인덱스 리프레시 권장")
        except Exception:
            pass
    return lines


# ---------------------------------------------------------------------------
# Check 8: harness-init 스킬 보존 확인 (2026-07-23 완화)
# ---------------------------------------------------------------------------
# harness-init.md는 더 이상 프로젝트 .claude/skills/에 배포하지 않는다 — 그건 하네스
# 재초기화용 메타/툴링 스킬이지 프로젝트 개발(바이브 코딩) 워크플로우 스킬이 아니라서,
# 배포해두면 wiki workflows.md·domain 참조 등 LLM이 실제 참조하는 목록에 함께 노출돼
# "기능 개발 중 하네스를 재초기화하라"는 엉뚱한 참조를 유발한다. 플러그인이 설치된
# 세션에서는 harness-init이 이미 전역적으로 호출 가능하므로 프로젝트 로컬 사본이
# 애초에 불필요하다. 이 체크는 과거 호환을 위해 남기되 항상 정보성 PASS만 반환한다
# (감점 없음) — 프로젝트에 사본이 남아있어도 무방하나 강제하지 않는다.

def check8_harness_init_preserved(root):
    path = os.path.join(root, ".claude", "skills", "harness-init.md")
    text = _read(path)
    if text is None:
        return "PASS", "harness-init.md 미배포 (정상 — 플러그인이 전역 제공, 프로젝트 로컬 사본 불필요)"
    fm = _frontmatter_fields(text)
    if fm.get("name") != "harness-init":
        return "PASS", "harness-init.md frontmatter name 불일치(정보성, 감점 없음)"
    return "PASS", "harness-init.md 존재 확인(선택 사항, 감점 대상 아님)"


# ---------------------------------------------------------------------------
# Check 9: 변경 이력 기록 확인
# ---------------------------------------------------------------------------

def check9_changelog(claude_md_text):
    if not claude_md_text or "## 변경 이력" not in claude_md_text:
        return "WARN", "변경 이력 섹션 없음"
    after = claude_md_text.split("## 변경 이력", 1)[1]
    rows = [l for l in after.splitlines() if l.strip().startswith("|") and "----" not in l and "날짜" not in l]
    if not rows:
        return "WARN", "변경 이력 테이블에 항목 없음"
    return "PASS", f"변경 이력 {len(rows)}건 확인"


# ---------------------------------------------------------------------------
# Check 10: patterns/ 스켈레톤 vs 본문 구분 (마커 기반, 애매하면 validator LLM에 위임)
# ---------------------------------------------------------------------------

def check10_pattern_status(root):
    patterns_dir = os.path.join(root, ".claude", "patterns")
    lines = []
    undecided = []
    for path in sorted(glob.glob(os.path.join(patterns_dir, "*.md"))):
        name = os.path.basename(path)
        text = _read(path) or ""
        has_skeleton_marker = SKELETON_MARKER in text
        has_filled_marker = bool(re.search(r"신뢰도:\s*(HIGH|MEDIUM|LOW)", text))
        if has_skeleton_marker and not has_filled_marker:
            lines.append(f"- {name}: SKELETON (pattern-extractor 호출 권장)")
        elif has_filled_marker and not has_skeleton_marker:
            lines.append(f"- {name}: FILLED")
        else:
            lines.append(f"- {name}: 판정 불가 — validator 직접 확인 필요")
            undecided.append(name)
    return lines, undecided


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="validator 체크 1,2,3,4,6,7,8,9 (+10 시도) 기계 실행기 (LLM 미사용)")
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    root = args.root
    out_path = args.out or os.path.join(root, "_workspace", "validator_mechanical.json")

    claude_md_text = _read(os.path.join(root, "CLAUDE.md")) or ""
    analyzer_report_text = _read(os.path.join(root, "_workspace", "01_analyzer_report.md")) or ""

    decisions = None
    decisions_path = os.path.join(root, "_workspace", "writer_decisions.json")
    if os.path.isfile(decisions_path):
        try:
            with open(decisions_path, "r", encoding="utf-8-sig") as f:
                decisions = json.load(f)
        except json.JSONDecodeError:
            pass

    r1 = check1_file_existence(root)
    r2 = check2_skill_registration(root, decisions, claude_md_text)
    r3 = check3_trigger_quality(root, decisions)
    r4 = check4_path_crosscheck(root)
    combined_1to6 = r1 + r2 + r3 + r4

    security_findings = check6_security_scan(root)

    index_fail, index_lines = check7_index_integrity(root, analyzer_report_text)
    spotcheck_fail, spotcheck_lines = check7b_spotcheck(root)
    freshness_lines = _index_meta_freshness(root)
    if spotcheck_fail:
        index_fail = True
    check8_status, check8_note = check8_harness_init_preserved(root)
    check9_status, check9_note = check9_changelog(claude_md_text)
    check10_lines, check10_undecided = check10_pattern_status(root)

    fails = [n for s, n in combined_1to6 if s == "FAIL"]
    warns = [n for s, n in combined_1to6 if s == "WARN"]
    passes = [n for s, n in combined_1to6 if s == "PASS"]
    if check8_status == "FAIL":
        fails.append(check8_note)
    else:
        passes.append(check8_note)

    deduction = 10 * len(fails) + 3 * len(warns)
    deduction += 15 * min(len(security_findings), 3)
    if index_fail:
        deduction += 15
    if check9_status == "WARN":
        deduction += 5

    md_1to6 = (
        "## 1~6. 기본 검증\n"
        + "\n".join(f"✅ PASS: {n}" for n in passes)
        + ("\n" if passes else "")
        + "\n".join(f"⚠️  WARN: {n} (각 -3점)" for n in warns)
        + ("\n" if warns else "")
        + "\n".join(f"❌ FAIL: {n} (각 -10점)" for n in fails)
    )

    md_security = (
        "## 🔒 보안 확인 필요\n" + ("\n".join(security_findings) if security_findings else "(발견 없음)")
    )

    md_7 = "## 7. 인덱스 무결성\n" + (index_lines or "(인덱스 없음)")
    extra_7 = spotcheck_lines + freshness_lines
    if extra_7:
        md_7 += "\n\n### 7b. 내용 스팟체크 (실측 대조)\n" + "\n".join(extra_7)
    md_8 = f"## 8. harness-init 보존\n{check8_status}"
    md_9 = f"## 9. 변경 이력 기록\n{check9_status}"
    md_10 = "## 10. patterns/ 상태\n" + ("\n".join(check10_lines) if check10_lines else "(패턴 파일 없음)")

    result = {
        "mechanical_deduction": deduction,
        "fails": fails,
        "warns": warns,
        "passes": passes,
        "security_findings": security_findings,
        "index_integrity_fail": index_fail,
        "index_spotcheck_fail": spotcheck_fail,
        "check8_status": check8_status,
        "check9_status": check9_status,
        "check10_undecided": check10_undecided,
        "report_fragments": {
            "1to6": md_1to6,
            "security": md_security,
            "7": md_7,
            "8": md_8,
            "9": md_9,
            "10": md_10,
        },
    }

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"생성 완료: {out_path} (기계 체크 차감 {deduction}점)")


if __name__ == "__main__":
    main()

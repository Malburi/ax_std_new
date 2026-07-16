# MSSQL harness_wiki_pages 테이블에 wiki 페이지를 upsert/조회하는 DB 클라이언트 (pymssql 기반)
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 시스템 wiki를 파일(wiki/ 폴더) 대신 MSSQL DB에 저장/조회하기 위한 모듈.
# 프로젝트 루트의 .env(MSSQL_HOST/PORT/USER/PASSWORD/DATABASE)를 읽어 접속한다.
# .env는 프로젝트별로 다를 수 있으므로 플러그인 자체(agents/lib) 기준이 아니라
# --root로 넘어온 대상 프로젝트 루트 기준으로 찾는다.

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
import wiki_render  # noqa: E402

TABLE_NAME = "harness_wiki_pages"

CONTENT_TYPE_BY_EXT = {
    ".md": "text/markdown",
    ".html": "text/html",
}

# call-graph.html이 상대경로로 참조하는 정적 라이브러리 파일 — DB에 저장하지 않고
# 서빙 시점에 플러그인 lib 폴더에서 그대로 내려준다 (프로젝트마다 동일한 파일).
STATIC_ASSET_FILES = ["vis-network.min.js", "vis-network.min.css"]


class ConfigError(Exception):
    pass


def load_env(project_root):
    """<project_root>/.env 를 KEY=VALUE 형식으로 파싱한다. python-dotenv 의존성 없이 처리."""
    env_path = os.path.join(project_root, ".env")
    if not os.path.isfile(env_path):
        raise ConfigError(f".env 파일 없음: {env_path} (MSSQL_HOST/PORT/USER/PASSWORD/DATABASE 필요)")

    values = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()

    required = ["MSSQL_HOST", "MSSQL_PORT", "MSSQL_USER", "MSSQL_PASSWORD", "MSSQL_DATABASE"]
    missing = [k for k in required if not values.get(k)]
    if missing:
        raise ConfigError(f".env에 다음 항목 누락: {', '.join(missing)}")
    return values


def _redacted(env):
    return f"{env['MSSQL_HOST']}:{env['MSSQL_PORT']}/{env['MSSQL_DATABASE']} (user={env['MSSQL_USER']})"


def resolve_system_key(project_root, env, override=None):
    """DB에서 이 프로젝트를 구분할 키를 결정한다.
    우선순위: override(--system-key 1회성) > .env의 WIKI_SYSTEM_KEY > 폴더 basename(경고).
    폴더 basename은 다른 시스템과 겹칠 수 있어 마지막 수단으로만 쓴다."""
    if override:
        return override
    if env.get("WIKI_SYSTEM_KEY"):
        return env["WIKI_SYSTEM_KEY"]
    fallback = os.path.basename(os.path.normpath(project_root))
    print(
        f"WARN: WIKI_SYSTEM_KEY 미설정 — 폴더명('{fallback}')으로 시스템 구분. "
        "다른 시스템과 폴더명이 같으면 데이터가 섞일 수 있습니다. .env에 WIKI_SYSTEM_KEY=고유값 설정 권장."
    )
    return fallback


def ensure_system_key_in_env(project_root, key):
    """.env에 WIKI_SYSTEM_KEY가 없으면 추가한다. 이미 있으면 기존 값을 그대로 반환
    (실수로 다른 값으로 덮어써 기존 시스템 키가 바뀌는 사고를 방지)."""
    env_path = os.path.join(project_root, ".env")
    existing = None
    lines = []
    if os.path.isfile(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("WIKI_SYSTEM_KEY=") or stripped.startswith("WIKI_SYSTEM_KEY ="):
                existing = stripped.partition("=")[2].strip()
                break
    if existing:
        return existing

    with open(env_path, "a", encoding="utf-8") as f:
        if lines and not lines[-1].endswith("\n"):
            f.write("\n")
        f.write(f"WIKI_SYSTEM_KEY={key}\n")
    return key


def get_connection(env, autocommit=True):
    import pymssql
    return pymssql.connect(
        server=env["MSSQL_HOST"],
        port=env["MSSQL_PORT"],
        user=env["MSSQL_USER"],
        password=env["MSSQL_PASSWORD"],
        database=env["MSSQL_DATABASE"],
        autocommit=autocommit,
        login_timeout=10,
        timeout=30,
    )


def ensure_schema(env):
    conn = get_connection(env)
    try:
        cur = conn.cursor()
        cur.execute(f"""
IF OBJECT_ID('dbo.{TABLE_NAME}', 'U') IS NULL
CREATE TABLE dbo.{TABLE_NAME} (
    id INT IDENTITY(1,1) PRIMARY KEY,
    project_name NVARCHAR(200) NOT NULL,
    page_path NVARCHAR(300) NOT NULL,
    content NVARCHAR(MAX) NOT NULL,
    content_type NVARCHAR(50) NOT NULL,
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_{TABLE_NAME}_project_path UNIQUE(project_name, page_path)
)
""")
    finally:
        conn.close()


EXCLUDED_DIRS = {"lib", "_html"}  # lib: vis-network 정적 자산 / _html: 폴더 모드 전용 렌더 사본
EXCLUDED_ROOT_FILES = {"index.html"}  # 폴더 모드 전용 정적 랜딩 페이지 — 실제 콘텐츠 아님


def _iter_wiki_files(wiki_dir):
    """wiki_dir 하위의 .md/.html 페이지만 순회 (lib/, _html/ 정적 자산·렌더 사본과
    루트의 index.html은 실제 콘텐츠가 아니므로 DB 동기화 대상에서 제외)."""
    for dirpath, dirnames, filenames in os.walk(wiki_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        is_root = os.path.normpath(dirpath) == os.path.normpath(wiki_dir)
        for filename in filenames:
            if is_root and filename in EXCLUDED_ROOT_FILES:
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in CONTENT_TYPE_BY_EXT:
                continue
            abspath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(abspath, wiki_dir).replace(os.sep, "/")
            yield rel_path, abspath, CONTENT_TYPE_BY_EXT[ext]


def save_folder_to_db(project_root, wiki_dir, env=None, system_key=None):
    """wiki_dir(폴더)의 .md/.html 페이지를 DB에 upsert하고, 폴더에 더 이상 없는
    페이지는 DB에서도 삭제한다 (폴더 -> DB 방향 완전 동기화)."""
    env = env or load_env(project_root)
    ensure_schema(env)
    project_name = resolve_system_key(project_root, env, system_key)

    pages = list(_iter_wiki_files(wiki_dir))
    conn = get_connection(env)
    try:
        cur = conn.cursor()
        for rel_path, abspath, content_type in pages:
            with open(abspath, "r", encoding="utf-8") as f:
                content = f.read()
            cur.execute(f"""
MERGE dbo.{TABLE_NAME} AS target
USING (SELECT %s AS project_name, %s AS page_path) AS src
ON target.project_name = src.project_name AND target.page_path = src.page_path
WHEN MATCHED THEN UPDATE SET content = %s, content_type = %s, updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN INSERT (project_name, page_path, content, content_type)
    VALUES (%s, %s, %s, %s);
""", (project_name, rel_path, content, content_type, project_name, rel_path, content, content_type))

        current_paths = [p[0] for p in pages]
        if current_paths:
            placeholders = ",".join(["%s"] * len(current_paths))
            cur.execute(
                f"DELETE FROM dbo.{TABLE_NAME} WHERE project_name = %s AND page_path NOT IN ({placeholders})",
                tuple([project_name] + current_paths),
            )
        else:
            cur.execute(f"DELETE FROM dbo.{TABLE_NAME} WHERE project_name = %s", (project_name,))
    finally:
        conn.close()

    print(f"DB 저장 완료: {_redacted(env)} — {len(pages)}개 페이지 (project={project_name})")
    return {"synced": len(pages), "project_name": project_name}


def load_db_to_folder(project_root, wiki_dir, env=None, system_key=None):
    """DB에 저장된 페이지를 wiki_dir(폴더)로 내려받는다 (DB -> 폴더 방향).
    call-graph.html이 참조하는 정적 lib 자산은 DB에 없으므로 플러그인 lib에서 복사한다."""
    env = env or load_env(project_root)
    ensure_schema(env)
    project_name = resolve_system_key(project_root, env, system_key)

    conn = get_connection(env)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT page_path, content, content_type FROM dbo.{TABLE_NAME} WHERE project_name = %s",
            (project_name,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print(f"WARN: DB에 project_name='{project_name}' 페이지 없음 — 내보낼 내용 없음")
        return {"restored": 0, "project_name": project_name}

    os.makedirs(wiki_dir, exist_ok=True)
    page_entries = []  # (href, label, source) — index.html용
    for page_path, content, content_type in rows:
        dest = os.path.join(wiki_dir, page_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)

        if content_type == "text/html":
            page_entries.append((page_path, page_path, page_path))
        else:
            html_name = os.path.splitext(page_path)[0] + ".html"
            rendered = wiki_render.render_markdown_page(project_name, page_path, content, index_href="../index.html")
            html_dest = os.path.join(wiki_dir, "_html", html_name)
            os.makedirs(os.path.dirname(html_dest), exist_ok=True)
            with open(html_dest, "w", encoding="utf-8") as f:
                f.write(rendered)
            page_entries.append((f"_html/{html_name}", page_path, page_path))

    dest_lib_dir = os.path.join(wiki_dir, "lib")
    os.makedirs(dest_lib_dir, exist_ok=True)
    for filename in STATIC_ASSET_FILES:
        src_file = os.path.join(LIB_DIR, filename)
        if os.path.exists(src_file):
            with open(src_file, "rb") as sf, open(os.path.join(dest_lib_dir, filename), "wb") as df:
                df.write(sf.read())

    index_html = wiki_render.render_index(
        title=f"{project_name} Wiki",
        heading=f"{project_name} — System Wiki (DB에서 복원)",
        entries=[(href, label, "") for href, label, _ in page_entries],
    )
    with open(os.path.join(wiki_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"폴더 복원 완료: {wiki_dir} — {len(rows)}개 페이지 (project={project_name})")
    return {"restored": len(rows), "project_name": project_name}


def list_pages(project_root, env=None, system_key=None):
    env = env or load_env(project_root)
    project_name = resolve_system_key(project_root, env, system_key)
    conn = get_connection(env)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT page_path, content_type, updated_at FROM dbo.{TABLE_NAME} WHERE project_name = %s ORDER BY page_path",
            (project_name,),
        )
        return cur.fetchall()
    finally:
        conn.close()


def get_page(project_root, page_path, env=None, system_key=None):
    env = env or load_env(project_root)
    project_name = resolve_system_key(project_root, env, system_key)
    conn = get_connection(env)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT content, content_type FROM dbo.{TABLE_NAME} WHERE project_name = %s AND page_path = %s",
            (project_name, page_path),
        )
        return cur.fetchone()
    finally:
        conn.close()


def list_systems(project_root, env=None):
    """DB에 저장된 모든 시스템(project_name 값) 목록과 페이지 수·최신 갱신 시각을 반환.
    여러 시스템의 wiki가 실제로 분리 저장되고 있는지 확인하는 용도."""
    env = env or load_env(project_root)
    ensure_schema(env)
    conn = get_connection(env)
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT project_name, COUNT(*), MAX(updated_at) FROM dbo.{TABLE_NAME} "
            "GROUP BY project_name ORDER BY project_name"
        )
        return cur.fetchall()
    finally:
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="시스템 wiki 폴더 <-> MSSQL DB 동기화")
    parser.add_argument("--root", required=True, help="프로젝트 루트 절대 경로 (.env 위치)")
    parser.add_argument("--wiki-dir", help="wiki 폴더 절대 경로 (--list-systems 사용 시 불필요)")
    parser.add_argument("--direction", choices=["to-db", "to-folder"],
                         help="to-db: 폴더->DB 저장 / to-folder: DB->폴더 복원")
    parser.add_argument("--system-key", help="DB에서 이 프로젝트를 구분할 키 (1회성 override, .env에 저장 안 함)")
    parser.add_argument("--list-systems", action="store_true",
                         help="DB에 저장된 모든 시스템(project_name) 목록 + 페이지 수 + 최신 갱신 시각 출력")
    args = parser.parse_args()

    try:
        if args.list_systems:
            rows = list_systems(args.root)
            if not rows:
                print("DB에 저장된 시스템 없음")
            else:
                print(f"{'시스템 키':30} {'페이지 수':>8}  최근 갱신")
                for name, count, updated_at in rows:
                    print(f"{name:30} {count:>8}  {updated_at}")
            return

        if not args.direction or not args.wiki_dir:
            parser.error("--direction과 --wiki-dir는 --list-systems가 아닐 때 필수")

        if args.direction == "to-db":
            save_folder_to_db(args.root, args.wiki_dir, system_key=args.system_key)
        else:
            load_db_to_folder(args.root, args.wiki_dir, system_key=args.system_key)
    except ConfigError as e:
        print(f"설정 오류: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

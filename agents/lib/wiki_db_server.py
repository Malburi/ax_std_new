# DB 저장 wiki를 Docsify 방식으로 서빙하는 stdlib 기반 로컬 HTTP 뷰어
import os
import sys
import html
import argparse
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

LIB_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, LIB_DIR)
import wiki_db  # noqa: E402
import wiki_render  # noqa: E402
import docsify_convert  # noqa: E402

STATIC_MIME = {".js": "application/javascript", ".css": "text/css"}


def _present_slugs(pages):
    """DB에 저장된 page_path 목록에서 Docsify 사이드바용 slug 집합을 추린다.
    call-graph.html/_html/*는 콘텐츠 페이지가 아니라 렌더 결과물이라 제외."""
    slugs = set()
    for page_path, _content_type, _updated in pages:
        if page_path == "call-graph.html" or page_path.startswith("_html/"):
            continue
        slug = os.path.splitext(page_path)[0]
        if slug and slug != "Home":
            slugs.add(slug)
    return slugs


def _other_systems_sidebar_section(system_key, other_systems):
    others = [s for s in other_systems if s[0] != system_key]
    if not others:
        return ""
    rows = "\n".join(
        f"  - [{html.escape(name)} ({count}개, {updated})](/?key={html.escape(name)} ':ignore')\n"
        for name, count, updated in others
    )
    return f"- **다른 시스템**\n{rows}"


def _render_index(system_key):
    return wiki_render.render_index(title=f"{system_key} - System Wiki (DB)")


def make_handler(project_root, default_key):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):
            print(f"[wiki_db_server] {self.address_string()} {fmt % a}")

        def _current_key(self, query):
            return (query.get("key", [None])[0]) or default_key

        def do_GET(self):
            split = urlsplit(self.path)
            path = split.path
            query = parse_qs(split.query)
            system_key = self._current_key(query)

            if path == "/":
                self._send(200, "text/html", _render_index(system_key).encode("utf-8"))
                return

            if path in ("/_sidebar.md", "/_navbar.md"):
                try:
                    pages = wiki_db.list_pages(project_root, system_key=system_key)
                    other_systems = wiki_db.list_systems(project_root)
                except Exception as e:
                    self._send(500, "text/plain", f"DB 조회 실패: {e}".encode("utf-8"))
                    return
                slugs = _present_slugs(pages)
                has_call_graph = any(p[0] == "call-graph.html" for p in pages)
                if path == "/_sidebar.md":
                    body = docsify_convert.build_sidebar(system_key, slugs, has_call_graph)
                    body += _other_systems_sidebar_section(system_key, other_systems)
                else:
                    body = docsify_convert.build_navbar(slugs, has_call_graph)
                self._send(200, "text/plain", body.encode("utf-8"))
                return

            if path.startswith("/lib/"):
                filename = path[len("/lib/"):]
                src = os.path.join(LIB_DIR, filename)
                ext = os.path.splitext(filename)[1].lower()
                if os.path.isfile(src) and ext in STATIC_MIME:
                    with open(src, "rb") as f:
                        self._send(200, STATIC_MIME[ext], f.read())
                else:
                    self._send(404, "text/plain", b"not found")
                return

            page_path = path.lstrip("/")
            try:
                row = wiki_db.get_page(project_root, page_path, system_key=system_key)
            except Exception as e:
                self._send(500, "text/plain", f"DB 조회 실패: {e}".encode("utf-8"))
                return

            if not row:
                self._send(404, "text/plain", f"페이지 없음: {page_path} (시스템: {system_key})".encode("utf-8"))
                return

            content, content_type = row
            if content_type == "text/html":
                self._send(200, "text/html", content.encode("utf-8"))
            else:
                # Docsify JS가 raw markdown을 fetch해서 클라이언트 렌더링
                self._send(200, "text/plain", content.encode("utf-8"))

        def _send(self, status, content_type, body_bytes):
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="MSSQL DB에 저장된 시스템 wiki를 브라우저로 서빙")
    parser.add_argument("--root", required=True, help="프로젝트 루트 절대 경로 (.env 위치)")
    parser.add_argument("--system-key", help="기본으로 보여줄 시스템 키 (없으면 .env의 WIKI_SYSTEM_KEY, 그것도 없으면 폴더명)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    try:
        env = wiki_db.load_env(args.root)
    except wiki_db.ConfigError as e:
        print(f"설정 오류: {e}", file=sys.stderr)
        sys.exit(1)

    default_key = wiki_db.resolve_system_key(args.root, env, args.system_key)
    handler = make_handler(args.root, default_key)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"wiki DB 뷰어 시작: http://127.0.0.1:{args.port}  (기본 시스템: {default_key}, Ctrl+C로 종료)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()

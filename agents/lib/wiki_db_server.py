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

STATIC_MIME = {".js": "application/javascript", ".css": "text/css"}


def _render_markdown_page(system_key, page_path, content):
    return wiki_render.render_markdown_page(system_key, page_path, content, index_href="/")


def _render_index(system_key, pages, other_systems):
    entries = [
        (f"/{p[0]}?key={system_key}", p[0], f"({p[1]}, {p[2]})")
        for p in pages
    ]
    others = [s for s in other_systems if s[0] != system_key]
    switcher = ""
    if others:
        other_rows = "\n".join(
            f'<li><a href="/?key={html.escape(name)}">{html.escape(name)}</a> '
            f'<small>({count}개 페이지, {updated})</small></li>'
            for name, count, updated in others
        )
        switcher = f"<h3>다른 시스템</h3><ul>{other_rows}</ul>"
    return wiki_render.render_index(
        title=f"{system_key} - System Wiki (DB)",
        heading=f"{system_key} — System Wiki (DB 저장)",
        entries=entries,
        extra_html=switcher,
    )


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
                try:
                    pages = wiki_db.list_pages(project_root, system_key=system_key)
                    other_systems = wiki_db.list_systems(project_root)
                except Exception as e:
                    self._send(500, "text/plain", f"DB 조회 실패: {e}".encode("utf-8"))
                    return
                self._send(200, "text/html", _render_index(system_key, pages, other_systems).encode("utf-8"))
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
                body = _render_markdown_page(system_key, page_path, content)
                self._send(200, "text/html", body.encode("utf-8"))

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

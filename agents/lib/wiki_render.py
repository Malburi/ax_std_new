import html

# 서버(wiki_db_server.py)와 정적 빌드(wiki_generator.py) 양쪽이 공유하는 최소 HTML 렌더러.
# 외부 CDN(marked.js, docsify 등) 의존 없이 markdown을 이스케이프 후 <pre>로 보여준다 —
# 폐쇄망 환경에서도, file:// 로 직접 열어도 동작해야 하기 때문.

PAGE_STYLE = """
body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; }
pre { white-space: pre-wrap; word-break: break-word; background: #f6f8fa; padding: 16px; border-radius: 6px; }
a { color: #1a5fa8; }
.nav { margin-bottom: 16px; }
"""

INDEX_STYLE = """
body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 700px; margin: 40px auto; }
li { margin: 6px 0; }
h3 { margin-top: 32px; color: #666; }
"""


def render_markdown_page(title, page_path, content, index_href="index.html"):
    """markdown 텍스트 1개를 안전하게 이스케이프해 <pre>로 보여주는 HTML 문서."""
    escaped = html.escape(content)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{html.escape(page_path)} - {html.escape(title)}</title>
<style>{PAGE_STYLE}</style></head>
<body>
<div class="nav"><a href="{html.escape(index_href)}">← 전체 페이지 목록</a></div>
<h2>{html.escape(page_path)}</h2>
<pre>{escaped}</pre>
</body></html>"""


def render_index(title, heading, entries, extra_html=""):
    """페이지 목록 인덱스. entries: [(href, label, sublabel), ...]"""
    rows = "\n".join(
        f'<li><a href="{html.escape(href)}">{html.escape(label)}</a> '
        f'<small>{html.escape(sublabel)}</small></li>'
        for href, label, sublabel in entries
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>{INDEX_STYLE}</style></head>
<body>
<h1>{html.escape(heading)}</h1>
<ul>{rows}</ul>
{extra_html}
</body></html>"""

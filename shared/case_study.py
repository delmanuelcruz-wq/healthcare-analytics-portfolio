"""Render every project README.md as a styled case-study page on the portfolio site.

    python shared/case_study.py

Each <project>/README.md becomes <project>/case-study.html so readers stay on the site.
Links are rewritten for the web: dashboards, images and workbooks stay relative (served by
GitHub Pages); code, folders, CSVs and other Markdown files open on GitHub, where they render.
"""
import html
import os
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared import portfolio as P  # noqa: E402

REPO = "https://github.com/delmanuelcruz-wq/healthcare-analytics-portfolio"
MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"
SERVED_AS_FILES = {".html", ".png", ".jpg", ".jpeg", ".svg", ".gif", ".xlsx"}

PAGE_CSS = """
.crumbs { margin: 0 0 10px; font-size: 13px; }
.crumbs a { color: var(--brand-ink); opacity: .85; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
.actions a { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; text-decoration: none;
  border-radius: 999px; padding: 8px 16px; border: 1px solid rgba(255,255,255,.45); color: var(--brand-ink); }
.actions a.primary { background: var(--brand-ink); color: var(--brand); border-color: var(--brand-ink); }
.toc { display: flex; flex-wrap: wrap; gap: 6px 8px; margin: 0 0 8px; padding: 12px 0 4px; font-size: 13px; }
.toc a { color: var(--accent); text-decoration: none; background: var(--surface); border: 1px solid var(--border);
  border-radius: 999px; padding: 3px 10px; }
.article { max-width: 900px; margin: 0 auto; font-size: 15.5px; }
.article h2 { font-size: 21px; margin: 38px 0 10px; padding-top: 14px; border-top: 1px solid var(--border); scroll-margin-top: 16px; }
.article h3 { font-size: 17px; margin: 26px 0 8px; }
.article p, .article li { line-height: 1.65; }
.article li { margin: 4px 0; }
.article a { color: var(--accent); }
.article code { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: .9em; background: var(--surface-2);
  padding: 1px 5px; border-radius: 4px; }
.article pre { background: var(--surface-2); border: 1px solid var(--border); padding: 12px 14px; border-radius: 8px; overflow-x: auto; }
.article pre code { background: none; padding: 0; }
.article blockquote { margin: 18px 0; padding: 10px 16px; border-left: 4px solid var(--warning); background: var(--synthetic-bg);
  color: var(--synthetic-ink); border-radius: 0 8px 8px 0; }
.article blockquote p { margin: 4px 0; }
.article img { max-width: 100%; height: auto; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
.article a.shot { display: block; position: relative; text-decoration: none; }
.article a.shot img { width: 100%; max-height: 520px; object-fit: cover; object-position: top; }
.article a.shot span { position: absolute; right: 12px; bottom: 12px; background: var(--brand); color: var(--brand-ink);
  font-size: 13px; font-weight: 600; border-radius: 999px; padding: 6px 14px; }
.article hr { display: none; }   /* h2 already draws a divider */
.article pre.mermaid svg { max-width: 100%; height: auto; }
.article .table-scroll { max-height: none; margin: 12px 0; }
.article table.data td, .article table.data th { white-space: normal; vertical-align: top; min-width: 80px; }
.article pre.mermaid { background: var(--surface); text-align: center; }
"""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESCRIPTION__">
<style>/*__SHARED_CSS__*/
__PAGE_CSS__</style>
</head>
<body>
<div class="synthetic-bar">SYNTHETIC DEMONSTRATION - fictional organization and 100% generated data. Not operational, medical or financial guidance.</div>
<header class="top">
  <div class="wrap">
    <p class="crumbs"><a href="__HOME__">&larr; All projects</a></p>
    <p class="eyebrow">__EYEBROW__ · Coralline Infusion Network (fictional)</p>
    <h1>__HEADING__</h1>
    <div class="actions">__ACTIONS__</div>
  </div>
</header>
<main class="wrap">
  <nav class="toc article" aria-label="On this page">__TOC__</nav>
  <article class="article">
__BODY__
  </article>
  <footer class="foot article">This page is generated from <a href="__SOURCE__">README.md</a>. All data is synthetic and the organization is fictional.
    SYNTHETIC DEMONSTRATION - not operational, medical or financial guidance.</footer>
</main>
<script>/*__DATA__*/</script>
<script>/*__SHARED_JS__*/</script>
__MERMAID__
</body>
</html>
"""

MERMAID_BOOT = """<script src="__CDN__"></script>
<script>
(function () {
  const dark = document.documentElement.dataset.theme === "dark" ||
    (!document.documentElement.dataset.theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
  mermaid.initialize({ startOnLoad: true, theme: dark ? "dark" : "neutral", securityLevel: "strict" });
})();
</script>"""


def project_readmes():
    found = [p for p in ROOT.glob("*/README.md")] + [p for p in ROOT.glob("tier*/*/README.md")]
    skip = {"foundation", "shared", "_private", ".venv"}
    return sorted(p for p in found if p.parent.name not in skip and p.parent.parent.name not in skip)


def eyebrow(folder: Path):
    rel = folder.relative_to(ROOT).as_posix()
    if rel.startswith("tier2/"):
        return "Tier 2 case study"
    if rel.startswith("tier3/"):
        return "Tier 3 micro-case"
    return f"Portfolio project {rel[0]}"


def github_url(target: Path, fragment=""):
    rel = target.relative_to(ROOT).as_posix()
    kind = "tree" if target.is_dir() else "blob"
    return f"{REPO}/{kind}/main/{rel}" + (f"#{fragment}" if fragment else "")


def rewrite_link(url: str, folder: Path, case_pages: set) -> str:
    if not url or url.startswith(("http://", "https://", "mailto:", "#", "data:")):
        return url
    path, _, fragment = url.partition("#")
    target = (folder / path).resolve()
    try:
        target.relative_to(ROOT)
    except ValueError:
        return url                                     # outside the repository: leave untouched
    if target.name == "README.md" and target.parent in case_pages:
        return _relpath(target.parent / "case-study.html", folder)   # another case study: stay on the site
    if target.is_file() and target.suffix.lower() in SERVED_AS_FILES:
        return url                                     # GitHub Pages serves it as-is
    return github_url(target, fragment)


def _relpath(target: Path, start: Path) -> str:
    return os.path.relpath(target, start).replace("\\", "/")


def render(readme: Path, case_pages: set):
    folder = readme.parent
    text = readme.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading = lines[0].lstrip("# ").strip() if lines and lines[0].startswith("# ") else folder.name
    body_md = "\n".join(lines[1:])
    # The GitHub README points at the live page and its source; on the site itself, one link is enough.
    body_md = re.sub(r"\[live page\]\([^)]*/dashboard\.html\) \(\[`dashboard\.html`\]\(dashboard\.html\) source\)",
                     "[live dashboard](dashboard.html)", body_md)
    mermaid_blocks = []

    def stash_mermaid(m):
        mermaid_blocks.append(m.group(1))
        return f"\n\nMERMAIDBLOCK{len(mermaid_blocks) - 1}\n\n"

    body_md = re.sub(r"```mermaid\n(.*?)```", stash_mermaid, body_md, flags=re.S)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"permalink": False}})
    body = md.convert(body_md)
    for i, block in enumerate(mermaid_blocks):
        body = body.replace(f"<p>MERMAIDBLOCK{i}</p>", f'<pre class="mermaid">{html.escape(block, quote=False)}</pre>')

    body = re.sub(r'(href|src)="([^"]*)"', lambda m: f'{m.group(1)}="{html.escape(rewrite_link(html.unescape(m.group(2)), folder, case_pages))}"', body)
    body = body.replace("<table>", '<div class="table-scroll"><table class="data wrap">').replace("</table>", "</table></div>")
    has_dashboard = (folder / "dashboard.html").exists()
    if has_dashboard:
        body = re.sub(r'<p><img alt="([^"]*)" src="dashboard\.png"\s*/?></p>',
                      r'<p><a class="shot" href="dashboard.html"><img alt="\1" src="dashboard.png"><span>Open the live dashboard</span></a></p>', body)
    body = body.replace('<a href="https://', '<a rel="noopener" href="https://')

    toc = " ".join(f'<a href="#{tid}">{html.escape(re.sub(r"^\d+\.\s*", "", name))}</a>'
                   for tid, name in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
                   if not name.lower().startswith("resume"))
    actions = []
    if has_dashboard:
        actions.append('<a class="primary" href="dashboard.html">Open the live dashboard</a>')
    actions.append(f'<a rel="noopener" href="{github_url(folder)}">View the code on GitHub</a>')
    first_para = re.search(r"<p>(.*?)</p>", re.sub(r"<blockquote>.*?</blockquote>", "", body, flags=re.S), re.S)
    description = re.sub(r"<[^>]+>", "", first_para.group(1))[:220] if first_para else heading

    page = (TEMPLATE.replace("__TITLE__", html.escape(heading.split(" - ", 1)[-1][:70]))
            .replace("__DESCRIPTION__", html.escape(description.strip()))
            .replace("__PAGE_CSS__", PAGE_CSS)
            .replace("__HOME__", _relpath(ROOT / "index.html", folder))
            .replace("__EYEBROW__", eyebrow(folder))
            .replace("__HEADING__", html.escape(heading))
            .replace("__ACTIONS__", "".join(actions))
            .replace("__TOC__", toc)
            .replace("__BODY__", body)
            .replace("__SOURCE__", github_url(readme))
            .replace("__MERMAID__", MERMAID_BOOT.replace("__CDN__", MERMAID_CDN) if mermaid_blocks else ""))
    page = page.replace("/*__SHARED_CSS__*/", (P.SHARED / "dashboard.css").read_text(encoding="utf-8"))
    page = page.replace("/*__SHARED_JS__*/", (P.SHARED / "dashboard.js").read_text(encoding="utf-8"))
    page = page.replace("/*__DATA__*/", "window.DATA = {};")
    out = folder / "case-study.html"
    out.write_text(page, encoding="utf-8", newline="\n")
    return out


def main():
    readmes = project_readmes()
    case_pages = {r.parent for r in readmes}
    for r in readmes:
        out = render(r, case_pages)
        print(f"  case study -> {out.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()

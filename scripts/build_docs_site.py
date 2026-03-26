#!/usr/bin/env python3
"""Build static site into ./site from site-src (Markdown + Jinja)."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = ROOT / "site-src"
PAGES_DIR = SITE_SRC / "pages"
TEMPLATES_DIR = SITE_SRC / "templates"
STATIC_DIR = SITE_SRC / "static"
ASSETS_DIR = SITE_SRC / "assets"
OUT = ROOT / "site"
INIT_PY = ROOT / "src" / "yokedcache" / "__init__.py"

PYPI_PACKAGE = "yokedcache"

SITE_URL = "https://sirstig.github.io/yokedcache"
GITHUB_REPO = "https://github.com/sirstig/yokedcache"

MAINTAINER_SAME_AS: list[str] = [
    "https://github.com/SirStig",
    "https://solutions.ironcoffee.com",
    "https://www.linkedin.com/in/joshua-kac-aa50b7131",
]

NAV: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Start",
        [
            ("Getting Started", "getting-started.md"),
            ("Core Concepts", "core-concepts.md"),
            ("Configuration", "configuration.md"),
        ],
    ),
    (
        "Usage",
        [
            ("Usage Patterns", "usage-patterns.md"),
            ("Backends & setup", "backends.md"),
            ("FastAPI Integration", "tutorials/fastapi.md"),
            ("FastAPI Redis Caching Tutorial", "tutorials/fastapi-redis-caching.md"),
            ("SQLAlchemy Integration", "tutorials/sqlalchemy.md"),
        ],
    ),
    (
        "Advanced",
        [
            ("Invalidation", "invalidation.md"),
            ("Resilience", "resilience.md"),
            ("HTTP Middleware", "middleware.md"),
            ("Vector Search", "vector-search.md"),
            ("Monitoring & Health", "monitoring.md"),
            ("Deployment", "deployment.md"),
        ],
    ),
    (
        "Reference",
        [
            ("API Reference", "api-reference.md"),
            ("CLI Tool", "cli.md"),
            ("Performance", "performance.md"),
            ("Security", "security.md"),
            ("Testing", "testing.md"),
            ("Troubleshooting", "troubleshooting.md"),
            ("Auto-Generated API", "__api__"),
        ],
    ),
]


def read_version() -> str:
    text = INIT_PY.read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return m.group(1) if m else "0.0.0"


def fetch_pypi_latest_version(timeout: float = 4.0) -> str | None:
    url = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
    req = Request(url, headers={"User-Agent": "yokedcache-docs-build/1"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        ver = data.get("info", {}).get("version")
        return ver if isinstance(ver, str) and ver else None
    except OSError:
        return None


def resolve_public_version() -> str:
    return fetch_pypi_latest_version() or read_version()


def md_to_html_path(md_rel: str) -> str:
    return Path(md_rel).with_suffix(".html").as_posix()


def _link_path_segment() -> str:
    raw = os.environ.get("YOKEDCACHE_SITE_PATH_PREFIX")
    if raw is not None:
        return raw.strip().strip("/")
    return urlparse(SITE_URL).path.strip("/")


def site_href(rel_path: str) -> str:
    rel = rel_path.strip().lstrip("/")
    seg = _link_path_segment()
    if seg:
        return f"/{seg}/{rel}"
    return f"/{rel}"


def title_from_first_h1(body: str) -> str | None:
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    if not raw.startswith("---"):
        return meta, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return meta, raw
    block = raw[3:end]
    body = raw[end + 4 :].lstrip("\n")
    for line in block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def fix_md_hrefs(html: str) -> str:
    return re.sub(
        r'href="([^"#]*)\.md((?:#[^"]*)?)"',
        lambda m: f'href="{m.group(1)}.html{m.group(2) or ""}"',
        html,
    )


_TOC_BLOCK = re.compile(r'<div class="toc">[\s\S]*?</div>\s*', re.IGNORECASE)


def split_toc(html: str) -> tuple[str, str | None]:
    m = _TOC_BLOCK.search(html)
    if not m:
        return html, None
    toc = m.group(0)
    rest = html[: m.start()] + html[m.end() :]
    if "<li" not in toc:
        return rest, None
    return rest, toc


def wrap_tables(html: str) -> str:
    return re.sub(
        r"<table(\s[^>]*)?>[\s\S]*?</table>",
        lambda m: f'<div class="table-wrap">{m.group(0)}</div>',
        html,
        flags=re.IGNORECASE,
    )


def _fence_opener_langs(md_body: str) -> list[str]:
    langs: list[str] = []
    in_fence = False
    for line in md_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") and not in_fence:
            in_fence = True
            header = stripped[3:].strip()
            langs.append(header.split()[0] if header else "")
        elif stripped == "```" and in_fence:
            in_fence = False
    return langs


_CODEHILITE_CODE_OPEN = re.compile(
    r'(<div class="codehilite">\s*<pre>)(?:<span></span>)?<code(?!\s+class=)>',
    re.IGNORECASE,
)


def inject_codehilite_lang_classes(md_body: str, html: str) -> str:
    langs = _fence_opener_langs(md_body)
    if not langs:
        return html
    it = iter(langs)

    def repl(m: re.Match[str]) -> str:
        try:
            lang = next(it)
        except StopIteration:
            return m.group(0)
        if not lang:
            return m.group(0)
        safe = lang.replace('"', "&quot;")
        return f'{m.group(1)}<code class="language-{safe}">'

    return _CODEHILITE_CODE_OPEN.sub(repl, html)


def write_syntax_highlight_css(path: Path) -> None:
    try:
        from pygments.formatters import HtmlFormatter
    except ImportError:
        path.write_text(
            "/* Syntax highlighting skipped: install pygments (docs extra). */\n",
            encoding="utf-8",
        )
        return

    def scoped(style: str, theme: str) -> str:
        fmt = HtmlFormatter(
            style=style,
            cssclass="codehilite",
            nobackground=True,
            wrapcode=True,
        )
        raw = fmt.get_style_defs(f'[data-theme="{theme}"] .codehilite')
        return "\n".join(ln for ln in raw.splitlines() if ".codehilite" in ln)

    chunks = [scoped("monokai", "dark"), scoped("xcode", "light")]
    path.write_text("\n".join(chunks) + "\n", encoding="utf-8")


def nav_context(current_out: str) -> list[dict]:
    groups = []
    for label, items in NAV:
        links = []
        for title, src in items:
            if src == "__api__":
                href = site_href("api/index.html")
                cur = current_out.startswith("api/")
            else:
                target = md_to_html_path(src)
                href = site_href(target)
                cur = current_out == target
            links.append({"title": title, "href": href, "current": cur})
        groups.append({"label": label, "links": links})
    return groups


def main() -> int:
    if not PAGES_DIR.is_dir():
        print("Missing site-src/pages", file=sys.stderr)
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    if STATIC_DIR.is_dir():

        def _skip_root_html(src: str, names: list[str]) -> set[str]:
            if Path(src).resolve() == STATIC_DIR.resolve():
                return {n for n in names if n in ("index.html", "changelog.html")}
            return set()

        shutil.copytree(STATIC_DIR, OUT, dirs_exist_ok=True, ignore=_skip_root_html)
    shutil.copytree(ASSETS_DIR, OUT / "assets")
    write_syntax_highlight_css(OUT / "assets" / "syntax-highlight.css")

    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("doc_page.html.jinja2")

    md_engine = markdown.Markdown(
        extensions=["tables", "fenced_code", "codehilite", "toc", "sane_lists", "nl2br"],
        extension_configs={
            "toc": {
                "permalink": False,
                "title": "",
                "toc_depth": "2-6",
            },
            "codehilite": {
                "guess_lang": True,
                "css_class": "codehilite",
            },
        },
    )

    version = resolve_public_version()

    for _group_label, items in NAV:
        for _title, src in items:
            if src == "__api__":
                continue
            md_path = PAGES_DIR / src
            if not md_path.is_file():
                print(f"Missing page source: {md_path}", file=sys.stderr)
                return 1
            raw = md_path.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(raw)
            md_body = body
            if "[TOC]" not in md_body:
                md_body = "[TOC]\n\n" + md_body
            md_engine.reset()
            raw_html = md_engine.convert(md_body)
            raw_html = inject_codehilite_lang_classes(md_body, fix_md_hrefs(raw_html))
            body_html, toc_html = split_toc(wrap_tables(raw_html))
            out_rel = md_to_html_path(src)
            out_path = OUT / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)

            title = meta.get("title") or title_from_first_h1(body)
            if not title:
                title = Path(src).stem.replace("-", " ").title()
            desc = meta.get(
                "description",
                "YokedCache — async multi-backend cache with tag invalidation and optional HTTP middleware.",
            )
            canonical = f"{SITE_URL}/{out_rel}"

            html = tpl.render(
                title=title,
                description=desc,
                keywords=meta.get("keywords", ""),
                canonical=canonical,
                body_html=body_html,
                toc_html=toc_html,
                nav_groups=nav_context(out_rel),
                asset_style_href=site_href("assets/style.css"),
                asset_syntax_href=site_href("assets/syntax-highlight.css"),
                asset_script_href=site_href("assets/app.js"),
                home_href=site_href("index.html"),
                changelog_href=site_href("changelog.html"),
                api_href=site_href("api/index.html"),
                docs_first_href=site_href("getting-started.html"),
                version=version,
                favicon_href=site_href("favicon.png"),
                favicon_svg_href=site_href("favicon.svg"),
                og_image_url=f"{SITE_URL}/og-image.png",
                site_url=SITE_URL,
                github_repo=GITHUB_REPO,
                maintainer_same_as=MAINTAINER_SAME_AS,
            )
            out_path.write_text(html, encoding="utf-8")

    home_canonical = f"{SITE_URL}/"
    standalone_ctx = {
        "site_url": SITE_URL,
        "github_repo": GITHUB_REPO,
        "og_image_url": f"{SITE_URL}/og-image.png",
        "version": version,
        "maintainer_same_as": MAINTAINER_SAME_AS,
        "home_canonical": home_canonical,
        "changelog_canonical": f"{SITE_URL}/changelog.html",
    }
    for standalone in ("index.html.jinja2", "changelog.html.jinja2"):
        stpl = env.get_template(standalone)
        out_name = standalone.replace(".jinja2", "")
        (OUT / out_name).write_text(stpl.render(**standalone_ctx), encoding="utf-8")

    print(f"Built site -> {OUT} ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

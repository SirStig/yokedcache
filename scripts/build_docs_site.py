#!/usr/bin/env python3
"""Build static site into ./site from site-src (Markdown + Jinja)."""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

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

SITE_URL = "https://sirstig.github.io/yokedcache"
GITHUB_REPO = "https://github.com/sirstig/yokedcache"

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
            ("FastAPI Integration", "tutorials/fastapi.md"),
            ("FastAPI Redis Caching Tutorial", "tutorials/fastapi-redis-caching.md"),
            ("SQLAlchemy Integration", "tutorials/sqlalchemy.md"),
        ],
    ),
    (
        "Advanced",
        [
            ("Backends & Setup", "backends.md"),
            ("Vector Search", "vector-search.md"),
            ("Monitoring & Health", "monitoring.md"),
        ],
    ),
    (
        "Reference",
        [
            ("CLI Tool", "cli.md"),
            ("Performance", "performance.md"),
            ("Security", "security.md"),
            ("Testing", "testing.md"),
            ("Troubleshooting", "troubleshooting.md"),
            ("API Reference", "__api__"),
        ],
    ),
]


def read_version() -> str:
    text = INIT_PY.read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return m.group(1) if m else "0.0.0"


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
        shutil.copytree(STATIC_DIR, OUT, dirs_exist_ok=True)
    shutil.copytree(ASSETS_DIR, OUT / "assets")

    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    tpl = env.get_template("doc_page.html.jinja2")

    md_engine = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists", "nl2br"],
        extension_configs={
            "toc": {
                "permalink": False,
                "title": "",
                "toc_depth": "2-6",
            },
        },
    )

    version = read_version()

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
            body_html, toc_html = split_toc(wrap_tables(fix_md_hrefs(raw_html)))
            out_rel = md_to_html_path(src)
            out_path = OUT / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)

            title = meta.get("title") or title_from_first_h1(body)
            if not title:
                title = Path(src).stem.replace("-", " ").title()
            desc = meta.get(
                "description",
                "YokedCache — Python caching for FastAPI with Redis and auto-invalidation.",
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
                asset_script_href=site_href("assets/app.js"),
                home_href=site_href("index.html"),
                changelog_href=site_href("changelog.html"),
                api_href=site_href("api/index.html"),
                docs_first_href=site_href("getting-started.html"),
                version=version,
            )
            out_path.write_text(html, encoding="utf-8")

    print(f"Built site -> {OUT} ({version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

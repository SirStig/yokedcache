# YokedCache SEO Audit

**Date:** March 2025

## Post-audit changes (implemented)

- **Share image** — `og-image.png` (1200×630) added in `site-src/static/`
- **Favicon** — `favicon.svg` (vector) + `favicon.png` (32×32) in `site-src/static/`
- **Open Graph & Twitter Card** meta tags on index, changelog, and all doc pages
- **Keywords** added to changelog.html

---

## Summary

| Category | Status | Notes |
|----------|--------|-------|
| Meta tags (title, description, canonical) | ✅ Good | Present on home, docs, changelog |
| Keywords | ⚠️ Partial | Missing on changelog.html |
| Open Graph (og:*) | ❌ Missing | No social preview tags |
| Twitter Cards (twitter:*) | ❌ Missing | No Twitter meta tags |
| Favicon | ❌ Missing | No rel="icon" or apple-touch-icon |
| Share image (OG image) | ❌ Missing | No dedicated 1200×630 asset |
| JSON-LD (SoftwareApplication) | ✅ Good | Home and doc pages |
| robots.txt | ✅ Good | Allow /, sitemap linked |
| sitemap.xml | ✅ Good | All main URLs included |
| lastmod on sitemap | ⚠️ Consider | Could add lastmod for freshness |

---

## 1. Meta Tags

### ✅ Working
- **charset** — UTF-8 on all pages
- **viewport** — Responsive
- **title** — Unique per page (Home, docs, changelog)
- **description** — Descriptive, ~150 chars on main pages
- **robots** — index,follow
- **canonical** — Correct absolute URLs

### ⚠️ Gaps
- **changelog.html** — No `keywords` meta (docs and home have it)

---

## 2. Open Graph & Twitter Cards

**Status:** Not implemented.

Social platforms (LinkedIn, X/Twitter, Slack, Discord, etc.) use Open Graph and Twitter Card meta tags to generate link previews. Without them, shares show a generic fallback.

### Required additions

```html
<meta property="og:type" content="website">
<meta property="og:url" content="...">
<meta property="og:title" content="...">
<meta property="og:description" content="...">
<meta property="og:image" content="https://sirstig.github.io/yokedcache/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:site_name" content="YokedCache">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="...">
<meta name="twitter:description" content="...">
<meta name="twitter:image" content="https://sirstig.github.io/yokedcache/og-image.png">
```

---

## 3. Favicon & App Icons

**Status:** No favicon or touch icons.

### Recommended
- **favicon.ico** or **favicon.svg** — 32×32 (or SVG)
- **apple-touch-icon.png** — 180×180 for iOS home screen

---

## 4. Structured Data

**Status:** ✅ Implemented on home and doc pages.

- `SoftwareApplication` JSON-LD with name, version, author, license, repository
- Doc template uses dynamic `{{ version }}`; home uses hardcoded `1.0.0` — consider syncing from package version

### Not covered
- **changelog.html** — No JSON-LD (optional; could add `WebPage`)
- **pdoc API pages** — Inherit pdoc’s default frame; may not include SoftwareApplication

---

## 5. Sitemap & Crawlability

### sitemap.xml
- All main docs, changelog, llms.txt, api/
- `changefreq` and `priority` set
- Could add `<lastmod>` for better cache freshness signals

### robots.txt
- Allows all crawlers
- Points to sitemap

---

## 6. Content & Technical SEO

- **Headings** — H1 per page, logical hierarchy in docs
- **Internal links** — Good cross-linking between docs
- **External links** — `rel="noopener"` on GitHub/PyPI
- **llms.txt** — Present and discoverable
- **Semantic HTML** — `article`, `nav`, `main` used appropriately

---

## Recommendations

1. Add Open Graph and Twitter Card meta tags to index.html, doc_page template, and changelog.html.
2. Create and serve a 1200×630 share image (`og-image.png`) for social previews.
3. Add favicon (SVG or ICO) and apple-touch-icon.
4. Add `keywords` to changelog.html.
5. Optionally add `<lastmod>` to sitemap entries.
6. Ensure home page JSON-LD `softwareVersion` stays in sync with package (or is generated at build time).

const html = document.documentElement;
const THEME_KEY = "yokedcache-theme";

function applyTheme(t) {
  html.setAttribute("data-theme", t);
  localStorage.setItem(THEME_KEY, t);
  document.querySelectorAll(".theme-btn").forEach((btn) => {
    btn.textContent = t === "dark" ? "☀ Light" : "◑ Dark";
  });
}

applyTheme(localStorage.getItem(THEME_KEY) || "dark");

document.querySelectorAll(".theme-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    applyTheme(html.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });
});

const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("sidebarOverlay");
const menuBtn = document.getElementById("menuBtn");

function drawerOpen() {
  return Boolean(sidebar?.classList.contains("open"));
}

function setDrawerOpen(open) {
  if (!sidebar || !overlay) return;
  sidebar.classList.toggle("open", open);
  overlay.classList.toggle("visible", open);
  document.body.classList.toggle("nav-drawer-open", open);
  overlay.setAttribute("aria-hidden", open ? "false" : "true");
  if (menuBtn) {
    menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
  }
}

if (menuBtn && sidebar) {
  menuBtn.setAttribute("aria-controls", "sidebar");
  menuBtn.setAttribute("aria-expanded", "false");
}

menuBtn?.addEventListener("click", () => {
  if (!sidebar || !overlay) return;
  setDrawerOpen(!drawerOpen());
});

overlay?.addEventListener("click", () => setDrawerOpen(false));

sidebar?.querySelectorAll(".sidebar-link").forEach((link) => {
  link.addEventListener("click", () => {
    if (window.innerWidth < 900) setDrawerOpen(false);
  });
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.getElementById("searchModal")?.open) {
    return;
  }
  if (e.key === "Escape" && drawerOpen()) {
    setDrawerOpen(false);
    menuBtn?.focus();
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth >= 900 && drawerOpen()) setDrawerOpen(false);
});

function attachCopyButton(pre) {
  if (pre.parentElement?.classList.contains("code-block")) return;

  const wrap = document.createElement("div");
  wrap.className = "code-block";
  pre.parentNode.insertBefore(wrap, pre);
  wrap.appendChild(pre);

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "copy-btn";
  btn.textContent = "Copy";
  btn.setAttribute("aria-label", "Copy code to clipboard");
  wrap.appendChild(btn);

  btn.addEventListener("click", () => {
    const text = pre.querySelector("code")?.textContent || pre.textContent;
    navigator.clipboard.writeText(text).then(() => {
      btn.textContent = "Copied!";
      btn.classList.add("copied");
      setTimeout(() => {
        btn.textContent = "Copy";
        btn.classList.remove("copied");
      }, 2000);
    });
  });
}

document.querySelectorAll("pre").forEach(attachCopyButton);

document.querySelectorAll(".code-block pre code").forEach((code) => {
  const m = code.className.match(/\blanguage-([\w+-]+)\b/);
  if (!m) return;
  const wrap = code.closest(".code-block");
  if (!wrap || wrap.querySelector(".code-lang-label")) return;
  const label = document.createElement("span");
  label.className = "code-lang-label";
  label.textContent = m[1];
  wrap.insertBefore(label, wrap.firstChild);
});

(function initDocSearch() {
  const indexUrl = html.getAttribute("data-search-index");
  const modal = document.getElementById("searchModal");
  const openBtn = document.getElementById("searchOpenBtn");
  const closeBtn = document.getElementById("searchCloseBtn");
  const input = document.getElementById("searchInput");
  const resultsEl = document.getElementById("searchResults");
  const emptyHint = document.getElementById("searchEmptyHint");
  const kbdHint = document.getElementById("searchKbdHint");

  if (kbdHint) {
    const mac = /Mac|iPhone|iPad|iPod/i.test(
      navigator.platform || navigator.userAgentData?.platform || ""
    );
    kbdHint.textContent = mac ? "⌘K" : "Ctrl+K";
  }

  if (!indexUrl || !modal || !input || !resultsEl || typeof Fuse === "undefined") {
    return;
  }

  let fuse = null;
  let loadError = null;

  function ensureFuse() {
    if (fuse || loadError) return Promise.resolve();
    return fetch(indexUrl)
      .then((r) => {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then((records) => {
        fuse = new Fuse(records, {
          keys: [
            { name: "title", weight: 0.42 },
            { name: "text", weight: 0.58 },
          ],
          threshold: 0.38,
          ignoreLocation: true,
          minMatchCharLength: 2,
          includeScore: true,
        });
      })
      .catch((err) => {
        loadError = err;
      });
  }

  function renderResults(q) {
    resultsEl.innerHTML = "";
    if (loadError) {
      emptyHint.textContent = "Could not load search index.";
      emptyHint.hidden = false;
      return;
    }
    if (!fuse) {
      emptyHint.textContent = "Loading…";
      emptyHint.hidden = false;
      return;
    }
    const query = q.trim();
    if (query.length < 2) {
      emptyHint.textContent = "Type at least 2 characters. Fuzzy matching handles typos.";
      emptyHint.hidden = false;
      return;
    }
    emptyHint.hidden = true;
    const hits = fuse.search(query, { limit: 14 });
    if (!hits.length) {
      emptyHint.textContent = "No matches. Try different wording.";
      emptyHint.hidden = false;
      return;
    }
    const frag = document.createDocumentFragment();
    hits.forEach(({ item }) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      const a = document.createElement("a");
      a.href = item.href;
      a.className = "search-result-link";
      const t = document.createElement("span");
      t.className = "search-result-title";
      t.textContent = item.title;
      a.appendChild(t);
      li.appendChild(a);
      frag.appendChild(li);
    });
    resultsEl.appendChild(frag);
  }

  let debounceTimer = null;
  function scheduleSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => renderResults(input.value), 60);
  }

  function openSearch() {
    ensureFuse().then(() => {
      modal.showModal();
      input.focus();
      if (loadError) {
        renderResults("");
        return;
      }
      input.select();
      renderResults(input.value);
    });
  }

  function closeSearch() {
    modal.close();
  }

  openBtn?.addEventListener("click", () => openSearch());
  closeBtn?.addEventListener("click", () => closeSearch());
  input?.addEventListener("input", scheduleSearch);

  modal.addEventListener("close", () => {
    input.value = "";
    resultsEl.innerHTML = "";
    emptyHint.textContent = "Type to search. Fuzzy matching handles typos.";
    emptyHint.hidden = false;
  });

  document.addEventListener("keydown", (e) => {
    if (!(e.metaKey || e.ctrlKey) || (e.key !== "k" && e.key !== "K")) return;
    const tag = e.target?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || e.target?.isContentEditable) {
      if (e.target !== input) return;
    }
    e.preventDefault();
    if (modal.open) {
      closeSearch();
    } else {
      openSearch();
    }
  });
})();

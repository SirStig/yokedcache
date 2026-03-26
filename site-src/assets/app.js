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

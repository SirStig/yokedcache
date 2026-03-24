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

function openSidebar() {
  sidebar?.classList.add("open");
  overlay?.classList.add("visible");
}
function closeSidebar() {
  sidebar?.classList.remove("open");
  overlay?.classList.remove("visible");
}

menuBtn?.addEventListener("click", openSidebar);
overlay?.addEventListener("click", closeSidebar);

sidebar?.querySelectorAll(".sidebar-link").forEach((link) => {
  link.addEventListener("click", () => {
    if (window.innerWidth < 900) closeSidebar();
  });
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

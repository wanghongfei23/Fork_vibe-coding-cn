/* ==========================================================================
   vibe-coding-cn 项目可视化 — 共享交互
   分面筛选引擎、主题、演示模式、导航。无外部依赖。
   ========================================================================== */
(function () {
  "use strict";

  const D = window.VIZ_DATA || {};

  /* -------------------------------------------------------------- 小工具 */
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function el(tag, attrs, html) {
    const n = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      if (k === "class") n.className = attrs[k];
      else if (k === "text") n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    if (html != null) n.innerHTML = html;
    return n;
  }

  const nf = n => (n == null ? "—" : n.toLocaleString("en-US"));

  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); }
    catch (e) { return null; }
  }

  /* -------------------------------------------------------------- 主题 */
  const THEMES = ["dark", "light"];
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    const b = $("#btn-theme");
    if (b) b.textContent = t === "dark" ? "🌙 深色" : "☀️ 浅色";
    store("viz-theme", t);
  }
  function initTheme() {
    const t = store("viz-theme") || "dark";
    applyTheme(THEMES.includes(t) ? t : "dark");
  }

  /* -------------------------------------------------------------- 演示模式 */
  // 第一项是入门层入口，其余为项目本身的 9 个页面
  const PAGES = [
    ["start.html", "从这里开始"],
    ["index.html", "总览"], ["design.html", "设计思路"], ["architecture.html", "结构机制"],
    ["gongfa.html", "功法体系"], ["faqi.html", "法器体系"], ["research.html", "研究域"],
    ["gates.html", "质量门禁"], ["roles.html", "三种读者"], ["glossary.html", "术语对照"],
  ];
  const SEP_AFTER = 0;   // 入门层与深入层之间的分隔位置

  function currentPage() {
    const f = location.pathname.split("/").pop() || "index.html";
    return f === "" ? "index.html" : f;
  }

  function goPage(dir) {
    const cur = currentPage();
    let i = PAGES.findIndex(p => p[0] === cur);
    if (i < 0) i = 0;
    const next = (i + dir + PAGES.length) % PAGES.length;
    location.href = PAGES[next][0];
  }

  function applyDemo(on) {
    document.body.classList.toggle("demo", on);
    const b = $("#btn-demo");
    if (b) { b.classList.toggle("on", on); b.textContent = on ? "🎬 演示中" : "🎬 演示模式"; }
    store("viz-demo", on ? "1" : "0");
    const bar = $("#demobar-page");
    if (bar) bar.textContent = (PAGES.findIndex(p => p[0] === currentPage()) + 1) + " / " + PAGES.length;
  }

  function initKeys() {
    document.addEventListener("keydown", e => {
      if (e.target.matches("input, textarea, select")) return;
      const k = e.key;
      if (k === "p" || k === "P") { applyDemo(!document.body.classList.contains("demo")); }
      else if (k === "Escape") { applyDemo(false); }
      else if (e.altKey || document.body.classList.contains("demo")) {
        if (k === "ArrowRight" || k === "PageDown") { e.preventDefault(); goPage(1); }
        if (k === "ArrowLeft" || k === "PageUp") { e.preventDefault(); goPage(-1); }
      }
    });
  }

  /* -------------------------------------------------------------- 顶栏 */
  function buildTopbar() {
    const cur = currentPage();
    const host = $("#topbar");
    if (!host) return;
    const links = PAGES.map(([f, t], i) =>
      (i === SEP_AFTER + 1 ? '<span class="navsep" aria-hidden="true"></span>' : "") +
      `<a href="${f}"${f === cur ? ' class="active"' : ""}>${esc(t)}</a>`).join("");
    host.innerHTML =
      `<div class="brand"><span class="dot"></span>vibe-coding-cn<small>项目可视化</small></div>` +
      `<nav class="navlinks">${links}</nav>` +
      `<div class="actions">` +
      `<button class="iconbtn" id="btn-demo" title="演示模式（快捷键 P）">🎬 演示模式</button>` +
      `<button class="iconbtn" id="btn-theme" title="切换主题">🌙 深色</button>` +
      `</div>`;
    $("#btn-demo").onclick = () => applyDemo(!document.body.classList.contains("demo"));
    $("#btn-theme").onclick = () =>
      applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  }

  function buildDemobar() {
    if ($("#demobar")) return;
    document.body.appendChild(el("div", { class: "demobar", id: "demobar" },
      `<button data-go="-1">◀ 上一页</button>` +
      `<span class="mono-n" id="demobar-page"></span>` +
      `<button data-go="1">下一页 ▶</button>` +
      `<span class="dsep">|</span>` +
      `<span class="faint tiny">P 退出演示 · ← → 翻页</span>`));
    $$("#demobar button[data-go]").forEach(b =>
      b.onclick = () => goPage(parseInt(b.dataset.go, 10)));
  }

  /* -------------------------------------------------------------- 分面引擎 */
  /**
   * 通用分面筛选。
   * cfg = { root, items, dimensions:[{key,label,color,values:[{v,label,color}],get(item)->[v]|v, hint}],
   *         render(items, host), counter, search:(item,q)->bool, searchPlaceholder }
   */
  function createFacets(cfg) {
    const state = {};
    cfg.dimensions.forEach(d => { state[d.key] = new Set(); });
    let query = "";

    const root = typeof cfg.root === "string" ? $(cfg.root) : cfg.root;
    const host = typeof cfg.host === "string" ? $(cfg.host) : cfg.host;
    if (!root || !host) return null;

    function matches(it) {
      if (query && cfg.search && !cfg.search(it, query)) return false;
      for (const d of cfg.dimensions) {
        const sel = state[d.key];
        if (!sel || !sel.size) continue;
        const vals = [].concat(d.get(it) == null ? [] : d.get(it));
        if (!vals.some(v => sel.has(v))) return false;
      }
      return true;
    }

    // 单维度内计数：其他维度已选中但本维度放开（标准分面计数）
    function countFor(dim, value) {
      const saved = state[dim.key];
      state[dim.key] = new Set();
      const n = cfg.items.filter(it => {
        if (query && cfg.search && !cfg.search(it, query)) return false;
        for (const d of cfg.dimensions) {
          if (d === dim) continue;
          const sel = state[d.key];
          if (!sel || !sel.size) continue;
          const vals = [].concat(d.get(it) == null ? [] : d.get(it));
          if (!vals.some(v => sel.has(v))) return false;
        }
        const vals = [].concat(dim.get(it) == null ? [] : dim.get(it));
        return vals.includes(value);
      }).length;
      state[dim.key] = saved;
      return n;
    }

    function renderFacets() {
      root.innerHTML = "";
      if (cfg.search) {
        const row = el("div", { class: "facet-row" });
        row.appendChild(el("span", { class: "flabel", text: "搜索" }));
        const inp = el("input", {
          type: "search", placeholder: cfg.searchPlaceholder || "输入关键词…",
          value: query, style: "flex:1;min-width:220px;background:var(--surface-2);border:1px solid var(--border);" +
            "color:var(--text);border-radius:999px;padding:5px 14px;font-size:.85rem;font-family:inherit;outline:none",
        });
        inp.oninput = () => { query = inp.value.trim().toLowerCase(); apply(); };
        row.appendChild(inp);
        root.appendChild(row);
      }
      cfg.dimensions.forEach(d => {
        const row = el("div", { class: "facet-row" });
        row.appendChild(el("span", { class: "flabel", text: d.label }));
        d.values.forEach(v => {
          const n = countFor(d, v.v);
          const c = el("button", {
            class: "chip" + (state[d.key].has(v.v) ? " on" : "") + (n === 0 && !state[d.key].has(v.v) ? " dim" : ""),
            style: v.color ? `--chip-c:${v.color}` : "",
          }, esc(v.label) + `<span class="c">${n}</span>`);
          c.onclick = () => {
            state[d.key].has(v.v) ? state[d.key].delete(v.v) : state[d.key].add(v.v);
            apply();
          };
          row.appendChild(c);
        });
        if (state[d.key].size) {
          const cl = el("span", { class: "fclear", text: "清除" });
          cl.onclick = () => { state[d.key].clear(); apply(); };
          row.appendChild(cl);
        }
        root.appendChild(row);
      });
      const line = el("div", { class: "result-line" });
      const shown = cfg.items.filter(matches).length;
      const active = cfg.dimensions.reduce((a, d) => a + state[d.key].size, 0);
      line.innerHTML = `匹配 <b>${nf(shown)}</b> / ${nf(cfg.items.length)} 条` +
        (active ? ` · 已选 ${active} 个筛选条件` : "") +
        (query ? ` · 关键词「${esc(query)}」` : "");
      if (active || query) {
        const r = el("span", { class: "fclear", text: "全部重置", style: "margin-left:auto" });
        r.onclick = () => {
          cfg.dimensions.forEach(d => state[d.key].clear());
          query = "";
          apply();
        };
        line.appendChild(r);
      }
      root.appendChild(line);
    }

    let raf = null;
    function apply() {
      renderFacets();
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const out = cfg.items.filter(matches);
        if (!out.length) {
          host.innerHTML = `<div class="empty">没有匹配项。试着减少筛选条件，或点「全部重置」。</div>`;
        } else {
          cfg.render(out, host);
        }
        if (cfg.counter) {
          const c = $(cfg.counter);
          if (c) c.textContent = nf(out.length) + " / " + nf(cfg.items.length);
        }
      });
    }

    apply();
    return { apply, state };
  }

  /* -------------------------------------------------------------- 页面初始化 */
  function init() {
    initTheme();
    buildTopbar();
    buildDemobar();
    initKeys();
    if (store("viz-demo") === "1") applyDemo(true);
    const f = $("#footer-year");
    if (f) f.textContent = new Date().getFullYear();
  }

  window.Viz = {
    D, $, $$, esc, el, nf, store, createFacets, applyDemo, goPage,
    PAGES, init,
    // 便捷取数
    top(list, n, key) {
      const m = {};
      list.forEach(it => { const k = key(it); m[k] = (m[k] || 0) + 1; });
      return Object.entries(m).sort((a, b) => b[1] - a[1]).slice(0, n || 10);
    },
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

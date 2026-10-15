/* ==========================================================================
   vibe-coding-cn 项目可视化 — 图表组件
   手写 SVG/DOM，无图表库依赖。所有函数接受容器元素与数据。
   ========================================================================== */
(function () {
  "use strict";
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const NS = "http://www.w3.org/2000/svg";
  const svgEl = (tag, attrs) => {
    const n = document.createElementNS(NS, tag);
    for (const k in (attrs || {})) n.setAttribute(k, attrs[k]);
    return n;
  };
  const resolve = t => (typeof t === "string" ? document.querySelector(t) : t);

  /* ---------------------------------------------------------------- 环形图 */
  /**
   * segs: [{label, value, color}]
   * opts: {size, thickness, centerValue, centerLabel, inner}
   */
  function donut(target, segs, opts) {
    const host = resolve(target); if (!host) return;
    opts = opts || {};
    const size = opts.size || 156, th = opts.thickness || 20;
    const r = (size - th) / 2, cx = size / 2, cy = size / 2;
    const total = segs.reduce((a, s) => a + s.value, 0) || 1;
    const C = 2 * Math.PI * r;

    const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${size} ${size}`, width: size, height: size });
    svg.appendChild(svgEl("circle", {
      cx, cy, r, fill: "none", stroke: "var(--track)", "stroke-width": th,
    }));
    let off = 0;
    segs.forEach(s => {
      const frac = s.value / total;
      if (frac <= 0) return;
      const arc = svgEl("circle", {
        cx, cy, r, fill: "none", stroke: s.color, "stroke-width": th,
        "stroke-dasharray": `${(frac * C).toFixed(2)} ${C.toFixed(2)}`,
        "stroke-dashoffset": (-off * C).toFixed(2),
        transform: `rotate(-90 ${cx} ${cy})`,
        "stroke-linecap": "butt",
      });
      arc.appendChild(svgEl("title")).textContent = `${s.label}: ${s.value}`;
      svg.appendChild(arc);
      off += frac;
    });
    if (opts.centerValue != null) {
      const t1 = svgEl("text", {
        x: cx, y: cy + 2, "text-anchor": "middle",
        "dominant-baseline": "middle", class: "cnum",
        style: `font-size:${size > 140 ? 26 : 20}px`,
      });
      t1.textContent = opts.centerValue;
      svg.appendChild(t1);
      if (opts.centerLabel) {
        const t2 = svgEl("text", {
          x: cx, y: cy + 21, "text-anchor": "middle", class: "clabel",
        });
        t2.textContent = opts.centerLabel;
        svg.appendChild(t2);
      }
    }
    host.innerHTML = "";
    host.appendChild(svg);
    if (opts.legend !== false) {
      const lg = document.createElement("div");
      lg.className = "legend";
      lg.style.flexDirection = "column";
      lg.style.gap = "5px";
      segs.filter(s => s.value > 0).forEach(s => {
        const d = document.createElement("div");
        d.className = "li";
        d.innerHTML = `<span class="sw" style="--sw:${s.color}"></span>` +
          `<span>${esc(s.label)}</span>` +
          `<b class="mono-n" style="margin-left:auto;color:var(--text)">${s.value}</b>`;
        lg.appendChild(d);
      });
      host.appendChild(lg);
    }
  }

  /* ---------------------------------------------------------------- 堆叠条 */
  /** segs: [{label,value,color}] → 单条水平堆叠 */
  function stackBar(target, segs, opts) {
    const host = resolve(target); if (!host) return;
    opts = opts || {};
    const total = segs.reduce((a, s) => a + s.value, 0) || 1;
    const h = opts.height || 30;
    const wrap = document.createElement("div");
    wrap.style.display = "flex";
    wrap.style.height = h + "px";
    wrap.style.borderRadius = "5px";
    wrap.style.overflow = "hidden";
    wrap.style.background = "var(--track)";
    wrap.style.border = "1px solid var(--border)";
    segs.filter(s => s.value > 0).forEach(s => {
      const d = document.createElement("div");
      const pct = (s.value / total) * 100;
      d.style.flex = `0 0 ${pct}%`;
      d.style.background = s.color;
      d.style.display = "flex";
      d.style.alignItems = "center";
      d.style.justifyContent = "center";
      d.style.fontSize = ".72rem";
      d.style.fontWeight = "700";
      d.style.color = "#08121a";
      d.style.overflow = "hidden";
      d.title = `${s.label}: ${s.value}（${pct.toFixed(1)}%）`;
      d.textContent = pct > 6 ? s.value : "";
      wrap.appendChild(d);
    });
    host.innerHTML = "";
    host.appendChild(wrap);
    if (opts.legend !== false) {
      const lg = document.createElement("div");
      lg.className = "legend";
      segs.filter(s => s.value > 0).forEach(s => {
        const d = document.createElement("div");
        d.className = "li";
        d.innerHTML = `<span class="sw" style="--sw:${s.color}"></span>${esc(s.label)} ` +
          `<b class="mono-n" style="color:var(--text)">${s.value}</b>`;
        lg.appendChild(d);
      });
      host.appendChild(lg);
    }
  }

  /* ------------------------------------------------------- 四阶十二级矩阵 */
  /**
   * tiers: [{id,name,levels:[{id,name}]}]
   * values: {"tian-advanced": n, ...}
   * 列 = 段位（高/中/初），行 = 阶（天/地/玄/黄）
   */
  function tierMatrix(target, tiers, values, opts) {
    const host = resolve(target); if (!host) return;
    opts = opts || {};
    const max = Math.max(1, ...Object.values(values));
    const t = document.createElement("table");
    t.className = "matrix";
    t.style.width = "100%";

    const thead = document.createElement("thead");
    const hr = document.createElement("tr");
    hr.appendChild(Object.assign(document.createElement("th"), { textContent: "" }));
    ["高级", "中级", "初级"].forEach(l => {
      const th = document.createElement("th");
      th.textContent = l;
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    t.appendChild(thead);

    const tb = document.createElement("tbody");
    tiers.forEach(tier => {
      const tr = document.createElement("tr");
      const th = document.createElement("th");
      th.className = "rowhead";
      th.textContent = tier.name;
      th.style.color = (opts.tierColors || {})[tier.id] || "var(--text-dim)";
      tr.appendChild(th);
      ["advanced", "intermediate", "initial"].forEach(seg => {
        const key = `${tier.id}-${seg}`;
        const v = values[key] || 0;
        const td = document.createElement("td");
        const cell = document.createElement("div");
        cell.className = "cell" + (v ? " has" : "");
        if (v) {
          const inten = 0.18 + 0.62 * (v / max);
          cell.style.background = `color-mix(in srgb, ${(opts.tierColors || {})[tier.id] || "var(--c-gongfa)"} ${(inten * 100).toFixed(0)}%, transparent)`;
        }
        cell.textContent = v || "·";
        cell.title = `${key}: ${v}`;
        td.appendChild(cell);
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    host.innerHTML = "";
    host.appendChild(t);
  }

  /* ---------------------------------------------------------------- 气泡图 */
  /**
   * items: [{label, value, color, sub}] — 面积正比于 value 的方块阵列
   */
  function bubbles(target, items, opts) {
    const host = resolve(target); if (!host) return;
    opts = opts || {};
    const max = Math.max(1, ...items.map(i => i.value));
    const box = document.createElement("div");
    box.style.display = "flex";
    box.style.flexWrap = "wrap";
    box.style.gap = "6px";
    box.style.alignItems = "flex-end";
    items.forEach(i => {
      const s = 30 + 66 * Math.sqrt(i.value / max);
      const d = document.createElement("div");
      d.style.cssText = `width:${s}px;height:${s}px;border-radius:7px;display:flex;flex-direction:column;` +
        `align-items:center;justify-content:center;cursor:default;` +
        `background:color-mix(in srgb, ${i.color || "var(--c-struct)"} 22%, var(--surface));` +
        `border:1px solid color-mix(in srgb, ${i.color || "var(--c-struct)"} 45%, transparent);`;
      d.title = `${i.label}: ${i.value}${i.sub ? " · " + i.sub : ""}`;
      d.innerHTML = `<b class="mono-n" style="font-size:${s > 70 ? 19 : 15}px;line-height:1">${i.value}</b>` +
        (s > 56 ? `<span style="font-size:.68rem;color:var(--text-dim);text-align:center;line-height:1.15;padding:0 4px">${esc(i.label)}</span>` : "");
      box.appendChild(d);
    });
    host.innerHTML = "";
    host.appendChild(box);
    if (opts.caption) {
      const c = document.createElement("div");
      c.className = "tiny faint mt8";
      c.textContent = opts.caption;
      host.appendChild(c);
    }
  }

  /* ---------------------------------------------------------------- 条形组 */
  /** rows: [{label, value, color, sub}] 横向条形（DOM 版，自动宽度） */
  function bars(target, rows, opts) {
    const host = resolve(target); if (!host) return;
    opts = opts || {};
    const max = Math.max(1, ...rows.map(r => r.value));
    const wrap = document.createElement("div");
    wrap.className = "bars";
    rows.forEach(r => {
      const row = document.createElement("div");
      row.className = "bar-row" + (opts.wide ? " wide" : "");
      row.innerHTML =
        `<span class="bl" title="${esc(r.label)}">${esc(r.label)}</span>` +
        `<span class="bt"><span class="bf" style="width:${(r.value / max * 100).toFixed(1)}%;--bar-c:${r.color || "var(--c-struct)"}"></span></span>` +
        `<span class="bv">${r.value}</span>`;
      if (r.sub) row.title = r.sub;
      wrap.appendChild(row);
    });
    host.innerHTML = "";
    host.appendChild(wrap);
  }

  /* ---------------------------------------------------------------- 阶梯 */
  /** steps: [{label, count, desc}] 竖向阶梯（成熟度） */
  function steps(target, items) {
    const host = resolve(target); if (!host) return;
    const wrap = document.createElement("div");
    wrap.style.display = "grid";
    wrap.style.gridTemplateColumns = `repeat(${items.length}, minmax(0,1fr))`;
    wrap.style.gap = "10px";
    items.forEach((s, i) => {
      const d = document.createElement("div");
      d.style.cssText = "background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:11px 13px;position:relative";
      if (s.color) d.style.borderTop = `3px solid ${s.color}`;
      d.innerHTML = `<div class="mono-n" style="font-size:1.5rem;font-weight:700;line-height:1.1">${s.count}</div>` +
        `<div style="font-size:.85rem;font-weight:600;margin-top:2px">${esc(s.label)}</div>` +
        `<div class="tiny faint" style="margin-top:3px">${esc(s.desc || "")}</div>`;
      wrap.appendChild(d);
    });
    host.innerHTML = "";
    host.appendChild(wrap);
  }

  window.Charts = { donut, stackBar, tierMatrix, bubbles, bars, steps, svgEl };
})();

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用无头 Chromium 真实渲染每个页面，检查运行时错误与关键内容，并输出截图。

用法：
    python viz/build/render_check.py            # 检查 + 截图
    python viz/build/render_check.py --no-shot  # 只检查
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
VIZ = HERE.parent.parent
SHOTS = HERE.parent / "shots"

PAGES = [
    ("start", "从这里开始", ["#bridge .node", "#steps a", "#words .panel", "#forks .panel"]),
    ("index", "总览", [".stat", "#bubbles .panel, #bubbles div", "#portal a"]),
    ("design", "设计思路", [".principle", "#principle-nav a"]),
    ("architecture", "结构机制", ["#tree .trow", "#duty tbody tr", "#pipeline .node"]),
    ("gongfa", "功法体系", ["#entries .entry", "#tier-matrix .cell", "#collections .panel"]),
    ("faqi", "法器体系", ["#items .entry", "#counts tbody tr", "#tier-grid .panel"]),
    ("research", "研究域", ["#domains .panel", "#kinds .panel", "#layers .panel"]),
    ("gates", "质量门禁", ["#targets tbody tr", "#groups .panel", "#chain .node"]),
    ("roles", "三种读者", ["#cards .panel", "#cover tbody tr", "#paths .panel"]),
    ("glossary", "术语对照", ["#cultivation tbody tr", "#confusions .panel", "#terms .panel"]),
]


def interactions(browser, problems: list[str], shots: Path):
    """验证关键交互：主题切换、演示模式、分面筛选、搜索、树折叠。"""
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.goto((VIZ / "gongfa.html").as_uri(), wait_until="load")
    page.wait_for_timeout(400)

    base = page.locator("#entries .entry").count()
    if base != 79:
        problems.append(f"分面初始条目数 {base}，预期 79")

    # 1) 点第一个「阶」chip（天阶）→ 条目数应减少
    page.locator("#facets .facet-row").nth(1).locator(".chip").first.click()
    page.wait_for_timeout(260)
    after = page.locator("#entries .entry").count()
    if after == 0 or after >= base:
        problems.append(f"分面筛选无效：点击天阶后条目 {after}（初始 {base}）")
    print(f"  · 分面筛选：天阶 → {after} 条 (初始 {base})")

    # 2) 先重置，再单独测搜索
    page.locator("#facets .fclear").last.click()
    page.wait_for_timeout(280)
    reset = page.locator("#entries .entry").count()
    if reset != 79:
        problems.append(f"重置失败：条目回到 {reset}，预期 79")
    print(f"  · 全部重置 → {reset} 条")

    page.locator("#facets input[type=search]").fill("问题")
    page.wait_for_timeout(340)
    searched = page.locator("#entries .entry").count()
    if searched == 0 or searched >= base:
        problems.append(f"搜索无效：搜「问题」命中 {searched} 条（初始 {base}）")
    print(f"  · 搜索「问题」 → {searched} 条")

    page.locator("#facets input[type=search]").fill("")
    page.wait_for_timeout(300)

    # 4) 演示模式
    page.keyboard.press("p")
    page.wait_for_timeout(200)
    demo = page.evaluate("() => document.body.classList.contains('demo')")
    bar = page.locator("#demobar").is_visible()
    if not (demo and bar):
        problems.append(f"演示模式异常：body.demo={demo} demobar={bar}")
    print(f"  · 演示模式：开启={demo} 底栏={bar}")
    page.keyboard.press("Escape")
    page.wait_for_timeout(150)
    if page.evaluate("() => document.body.classList.contains('demo')"):
        problems.append("Esc 未退出演示模式")

    # 5) 主题切换
    page.locator("#btn-theme").click()
    page.wait_for_timeout(200)
    th = page.evaluate("() => document.documentElement.getAttribute('data-theme')")
    if th != "light":
        problems.append(f"主题切换失败：{th}")
    print(f"  · 主题切换 → {th}")
    page.screenshot(path=str(shots / "theme-light.png"))
    page.locator("#btn-theme").click()
    page.wait_for_timeout(150)

    # 6) 目录树折叠
    page.goto((VIZ / "architecture.html").as_uri(), wait_until="load")
    page.wait_for_timeout(300)
    row_h = page.locator("#tree .trow[data-t]").first
    before = page.locator("#tree .trow").count()
    row_h.click()
    page.wait_for_timeout(150)
    hidden = page.evaluate("() => document.querySelectorAll('#tree .tkids.hidden').length")
    if hidden == 0:
        problems.append("目录树折叠未生效")
    print(f"  · 目录树折叠：隐藏 {hidden} 个分支（原有 {before} 行）")

    page.close()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    from playwright.sync_api import sync_playwright

    want_shot = "--no-shot" not in sys.argv
    SHOTS.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, title, selectors in PAGES:
            page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
            errs: list[str] = []
            page.on("pageerror", lambda e: errs.append(f"JS 错误: {e}"))
            page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}")
                    if m.type in ("error",) else None)

            f = VIZ / f"{name}.html"
            page.goto(f.as_uri(), wait_until="load")
            page.wait_for_timeout(420)

            counts = {}
            for sel in selectors:
                n = page.locator(sel).count()
                counts[sel] = n
                if n == 0:
                    problems.append(f"{name}.html：选择器无匹配 → {sel}")

            stats = page.evaluate("""() => {
                const s = window.VIZ_DATA;
                return {
                  ok: !!s,
                  theme: document.documentElement.getAttribute('data-theme'),
                  nav: document.querySelectorAll('.navlinks a').length,
                  bodyText: document.body.innerText.length,
                };
            }""")
            if not stats["ok"]:
                problems.append(f"{name}.html：VIZ_DATA 未加载")
            if stats["nav"] != 10:
                problems.append(f"{name}.html：导航链接数为 {stats['nav']}，预期 10")
            if stats["bodyText"] < 1200:
                problems.append(f"{name}.html：渲染文本量偏少（{stats['bodyText']} 字符），可能有内容未生成")

            status = "OK " if not errs else "ERR"
            print(f"[{status}] {name:14s} {title:6s} nav={stats['nav']} text={stats['bodyText']:>6d} " +
                  " ".join(f"{k.split()[-1]}={v}" for k, v in counts.items()))
            for e in errs:
                problems.append(f"{name}.html：{e}")

            if want_shot:
                page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
            page.close()

        print("\n交互检查：")
        interactions(browser, problems, SHOTS)
        browser.close()

    print()
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for p in problems:
            print("  x " + p)
        return 1
    print("全部页面渲染正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())

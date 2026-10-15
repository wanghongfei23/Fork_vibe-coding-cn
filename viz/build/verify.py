#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 viz/ 输出：资源引用、内联脚本语法、数据字段引用。

用法：
    python viz/build/verify.py
"""

from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
VIZ = HERE.parent.parent
TMP = HERE.parent / ".tmp"

PAGES = ["start", "index", "design", "architecture", "gongfa", "faqi",
         "research", "gates", "roles", "glossary"]

errors: list[str] = []
warns: list[str] = []


def read(p: Path) -> str:
    return io.open(p, encoding="utf-8").read()


def check_assets():
    """每个页面引用的 CSS / JS 必须存在。"""
    for name in PAGES:
        f = VIZ / f"{name}.html"
        if not f.exists():
            errors.append(f"缺少页面 {name}.html")
            continue
        text = read(f)
        for ref in re.findall(r'(?:href|src)="((?!https?:|#)[^"]+)"', text):
            if "${" in ref:            # JS 模板串，运行时才生成
                continue
            target = (VIZ / ref.split("#")[0]).resolve()
            if not target.exists():
                errors.append(f"{name}.html 引用不存在的资源：{ref}")
        for need in ["assets/style.css", "assets/data.js", "assets/app.js", "id=\"topbar\""]:
            if need not in text:
                errors.append(f"{name}.html 缺少必需引用：{need}")


def check_inline_js():
    """内联脚本交给 node --check 验语法。"""
    node = shutil.which("node")
    if not node:
        warns.append("未找到 node，跳过内联脚本语法检查")
        return
    TMP.mkdir(parents=True, exist_ok=True)
    for name in PAGES:
        f = VIZ / f"{name}.html"
        if not f.exists():
            continue
        blocks = re.findall(r"<script>(.*?)</script>", read(f), re.S)
        if not blocks:
            continue
        tmp = TMP / f"{name}.js"
        io.open(tmp, "w", encoding="utf-8").write("\n".join(blocks))
        r = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"{name}.html 内联脚本语法错误：\n{r.stderr.strip()[:600]}")
    for js in ["assets/app.js", "assets/charts.js", "assets/data.js"]:
        r = subprocess.run([node, "--check", str(VIZ / js)], capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"{js} 语法错误：\n{r.stderr.strip()[:400]}")


def check_data_fields():
    """扫描页面里 D.a.b 形式的引用，核对 data.js 中确实存在这些路径。"""
    src = read(VIZ / "assets/data.js")
    data = json.loads(src.split("window.VIZ_DATA = ", 1)[1].rstrip().rstrip(";"))

    def has(path: list[str]) -> bool:
        cur = data
        for seg in path:
            if isinstance(cur, dict) and seg in cur:
                cur = cur[seg]
            elif isinstance(cur, list):
                return True  # 列表元素字段无法静态判定
            else:
                return False
        return True

    pat = re.compile(r"\bD\.([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)*)")
    skip = {"length", "map", "filter", "forEach", "slice", "join", "find", "sort", "reduce",
            "flatMap", "concat", "some", "every", "includes", "indexOf", "toLowerCase"}
    seen = set()
    for name in PAGES:
        f = VIZ / f"{name}.html"
        if not f.exists():
            continue
        for m in pat.finditer(read(f)):
            expr = m.group(1)
            parts = [p for p in expr.split(".") if p not in skip]
            if not parts or expr in seen:
                continue
            seen.add(expr)
            if not has(parts):
                errors.append(f"{name}.html 引用了 data.js 中不存在的字段：D.{expr}")


def check_data_freshness():
    """data.js 应比仓库内容新；否则提示重新生成。"""
    data = VIZ / "assets" / "data.js"
    if not data.exists():
        errors.append("assets/data.js 不存在，请先运行 python viz/build/extract.py")
        return
    newest = max((p.stat().st_mtime for p in (VIZ.parent / ".github").rglob("*.md")
                  if ".git" not in p.parts), default=0)
    if data.stat().st_mtime < newest:
        warns.append("data.js 可能过期（仓库里有更新的 Markdown），建议重跑 extract.py")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    check_assets()
    check_inline_js()
    if (VIZ / "assets/data.js").exists():
        check_data_fields()
    check_data_freshness()
    if TMP.exists():
        shutil.rmtree(TMP, ignore_errors=True)

    print(f"页面 {len(PAGES)} 个 · 资源与语法检查完成")
    for w in warns:
        print(f"  ⚠  {w}")
    if errors:
        print(f"\n发现 {len(errors)} 个问题：")
        for e in errors:
            print(f"  ✗  {e}")
        return 1
    print("  ✓ 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 vibe-coding-cn 仓库提取结构化数据，生成 viz/assets/data.js。

只读仓库文件，不修改仓库内容。输出供离线 HTML 页面通过 <script src> 加载。

用法：
    python viz/build/extract.py
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
VIZ_DIR = HERE.parent.parent           # viz/
REPO = VIZ_DIR.parent                  # 仓库根
GH = REPO / ".github"                  # 内容树
OUT = VIZ_DIR / "assets" / "data.js"

GRADE_ORDER = [
    "tian-advanced", "tian-intermediate", "tian-initial",
    "di-advanced", "di-intermediate", "di-initial",
    "xuan-advanced", "xuan-intermediate", "xuan-initial",
    "huang-advanced", "huang-intermediate", "huang-initial",
]
GRADE_ZH = {
    "tian-advanced": "天阶高级", "tian-intermediate": "天阶中级", "tian-initial": "天阶初级",
    "di-advanced": "地阶高级", "di-intermediate": "地阶中级", "di-initial": "地阶初级",
    "xuan-advanced": "玄阶高级", "xuan-intermediate": "玄阶中级", "xuan-initial": "玄阶初级",
    "huang-advanced": "黄阶高级", "huang-intermediate": "黄阶中级", "huang-initial": "黄阶初级",
}
TYPE_ZH = {
    "method-specification": "方法规范",
    "normative-allocation-content": "准则分配",
    "dao-content": "道论内容",
    "explanatory-content": "解释内容",
    "operational-capability": "操作能力",
    "software-artifact": "软件制品",
}

# 目录职责：来自各级 AGENTS.md 的职责描述（原文摘录，不新增主张）
DIR_ROLES = {
    "docs": {"label": "docs", "cn": "入门教程与功法正文", "tier": "知识"},
    "docs/getting-started": {"label": "getting-started", "cn": "学习路线、环境配置与第一个可验收练习", "tier": "知识"},
    "docs/gongfa": {"label": "gongfa", "cn": "方法、准则、模型与法器配套说明的唯一正文位置", "tier": "知识"},
    "research": {"label": "research", "cn": "研究对象、来源事实与冻结材料", "tier": "事实"},
    "prompts": {"label": "prompts", "cn": "提示词库入口", "tier": "指令"},
    "skills": {"label": "skills", "cn": "可复用技能库", "tier": "能力"},
    "tools": {"label": "tools", "cn": "工具、配置与外部依赖", "tier": "能力"},
    "scripts": {"label": "scripts", "cn": "本地检查、目录生成与数据维护脚本", "tier": "机器"},
    "metadata": {"label": "metadata", "cn": "机器可读登记、分类、重定向和生成目录", "tier": "机器"},
    "assets": {"label": "assets", "cn": "静态资产、外部资源注册表与 AI 引用语料", "tier": "机器"},
}

# 门禁分组：按守护的对象归类
GATE_GROUPS = {
    "lint": "格式", "check-links": "格式", "check-details": "格式",
    "check-doc-structure": "结构", "check-directory-docs": "结构", "check-metadata": "结构",
    "check-gongfa": "功法", "test-gongfa": "功法", "sync-gongfa-catalog": "功法",
    "check-gongfa-catalog": "功法", "test-gongfa-catalog": "功法",
    "sync-faqi-catalog": "法器", "check-faqi-catalog": "法器", "test-faqi-catalog": "法器",
    "check-ai-citation": "引用", "check-external-resources": "资源",
    "check-research-raw": "研究", "check-source-facts": "研究", "check-wiki": "研究",
    "fetch-research-raw": "研究（手动）",
    "sync-doc-toc": "工具", "build": "工具", "test": "总入口", "clean": "工具", "clean-deps": "工具", "help": "工具",
}

GATE_GUARDS = {
    "lint": "Markdown 排版规则",
    "check-links": "仓库内相对链接与锚点可达",
    "check-details": "折叠块 details/summary 结构",
    "check-doc-structure": "docs README 标准块顺序与目录入口",
    "check-directory-docs": "目录 README/AGENTS 覆盖",
    "check-metadata": "metadata 路径与锚点真实存在",
    "check-gongfa": "功法 JSON、来源外键、词表与评级引用",
    "test-gongfa": "功法 CLI 行为与产物留存",
    "sync-gongfa-catalog": "（写）总表重建",
    "check-gongfa-catalog": "总表来源 SHA、覆盖与两视图一致",
    "test-gongfa-catalog": "总表维护行为契约",
    "sync-faqi-catalog": "（写）法器总表重建",
    "check-faqi-catalog": "法器登记、依赖图 SHA 与只读视图",
    "test-faqi-catalog": "法器总表维护行为契约",
    "check-ai-citation": "llms 与 AI 引用语料路径、锚点与仓库身份",
    "check-external-resources": "外部资源注册表字段、分类与 ID",
    "check-research-raw": "研究域 raw 层、Git 工作树与来源清单",
    "check-source-facts": "外部源镜像文件数、边界与隐私登记",
    "check-wiki": "GitHub Wiki checkout 页面覆盖与旧口径",
    "fetch-research-raw": "（拉取）研究 raw 与工作树",
    "sync-doc-toc": "（写）docs 细粒度目录",
    "build": "确认本仓库没有构建步骤",
    "test": "串起 16 个门禁",
    "clean": "清理生成缓存",
    "clean-deps": "清理依赖缓存",
    "help": "列出全部目标",
}


def read_text(path: Path) -> str:
    return io.open(path, encoding="utf-8").read()


def load_json(path: Path):
    return json.loads(read_text(path))


def try_yaml(path: Path):
    try:
        import yaml  # type: ignore
        return yaml.safe_load(read_text(path))
    except Exception:
        return None


def parse_simple_yaml_terms(path: Path):
    """glossary.yml 的最小无依赖解析：terms.<key>.{zh,description}。"""
    text = read_text(path)
    terms = []
    cur = None
    for line in text.splitlines():
        m = re.match(r"^  ([\w\-]+):\s*$", line)
        if m:
            cur = {"key": m.group(1)}
            continue
        m = re.match(r"^    (zh|description):\s*(.+?)\s*$", line)
        if m and cur is not None:
            cur[m.group(1)] = m.group(2)
            if "zh" in cur and "description" in cur:
                terms.append(cur)
                cur = None
    return terms


def parse_taxonomy_docs(path: Path):
    """从 taxonomy.yml 的 documents 段提取 path -> (title, role)。"""
    if not path.exists():
        return {}
    text = read_text(path)
    out = {}
    for m in re.finditer(
        r"- path:\s*(\S+)\s*\n\s+title:\s*(.+?)\s*\n\s+role:\s*(.+?)\s*\n", text
    ):
        p, title, role = m.group(1), m.group(2).strip(), m.group(3).strip()
        out[norm(p)] = {"title": title, "role": role}
    return out


def norm(p: str) -> str:
    p = p.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    if p.startswith(".github/"):
        p = p[len(".github/"):]
    return p


def count_files(d: Path):
    n = md = 0
    for root, dirs, files in os.walk(d):
        dirs.sort()
        for f in files:
            n += 1
            if f.lower().endswith(".md"):
                md += 1
    return n, md


def git(*args):
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return r.stdout.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------- 提取块

def build_tree(max_depth=3):
    """目录树（只列目录，标注文件数），用于结构页。"""
    skip = {"raw", "repository", "node_modules", "__pycache__", ".history", ".tmp"}

    def walk(d: Path, depth: int):
        nodes = []
        try:
            entries = sorted(d.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        except OSError:
            return nodes
        for f in entries:
            if f.name.startswith(".") or f.name in skip:
                continue
            if f.is_dir():
                n, md = count_files(f)
                node = {"name": f.name, "files": n, "md": md}
                node["kids"] = walk(f, depth + 1) if depth < max_depth and n <= 400 else []
                if n > 400:
                    node["note"] = "体积较大，已折叠"
                nodes.append(node)
        return nodes

    # 内容树以 .github 为根（仓库内容全部收拢在此）
    root_n, root_md = count_files(GH)
    return {"name": ".github", "files": root_n, "md": root_md, "kids": walk(GH, 1)}


def parse_reading_paths(path: Path):
    """taxonomy.yml 的 reading_paths：面向不同身份的阅读路线。"""
    if not path.exists():
        return []
    text = read_text(path)
    block = text.split("reading_paths:", 1)[-1].split("selection_rules:", 1)[0]
    out = []
    for m in re.finditer(
        r"^  ([\w\-]+):\s*\n\s+title:\s*(.+?)\s*\n\s+documents:\s*\n((?:\s+- .+\n)+)", block, re.M
    ):
        docs = [norm(x) for x in re.findall(r"^\s+- (.+?)\s*$", m.group(3), re.M)]
        out.append({"key": m.group(1), "title": m.group(2).strip(), "docs": docs})
    return out


def build_overview():
    dirs = []
    total_files = total_md = 0
    for key, meta in DIR_ROLES.items():
        d = GH / key
        if not d.is_dir():
            continue
        n, md = count_files(d)
        total_files += n
        total_md += md
        dirs.append({"path": f".github/{key}", "label": meta["label"], "cn": meta["cn"],
                     "tier": meta["tier"], "files": n, "md": md,
                     "hasReadme": (d / "README.md").exists(),
                     "hasAgents": (d / "AGENTS.md").exists()})
    root_files = []
    for f in sorted(REPO.iterdir()):
        if f.is_file() and f.suffix in (".md", ".txt", ".toml"):
            root_files.append({"name": f.name, "lines": len(read_text(f).splitlines())})
    keyfiles = []
    for rel, role in [
        ("README.md", "人类首页，GitHub 展示入口"),
        ("AGENTS.md", "AI Agent 操作手册"),
        ("llms.txt", "AI 助手短上下文入口"),
        ("Makefile", "全部本地命令入口"),
        (".github/assets/ai-citation/llms-full.txt", "AI 助手完整上下文入口"),
        (".github/docs/gongfa/README.md", "功法体系导航"),
        (".github/metadata/gongfa/catalog.md", "功法总表（生成视图）"),
        (".github/tools/faqi-catalog.md", "法器总表（生成视图）"),
    ]:
        p = REPO / rel
        if p.exists():
            keyfiles.append({"path": rel, "role": role,
                             "lines": len(read_text(p).splitlines()),
                             "bytes": p.stat().st_size})
    return {
        "dirs": dirs,
        "totals": {"files": total_files, "md": total_md, "trees": len(dirs)},
        "rootFiles": root_files,
        "keyFiles": keyfiles,
    }


def build_meta():
    ns = git("log", "--oneline")
    return {
        "generatedAt": git("log", "-1", "--format=%cI"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "head": git("rev-parse", "--short", "HEAD"),
        "headSubject": git("log", "-1", "--format=%s"),
        "commits": len(ns.splitlines()) if ns else 0,
        "repo": "tukuaiai/vibe-coding-cn",
    }


def build_gongfa(tax):
    reg = load_json(GH / "metadata/gongfa/registry.json")
    entries = {e["id"]: e for e in reg["gongfa"]}

    # 初评批次 -> 品级映射
    grade_of = {}
    proposals = []
    for p in reg["grade_proposals"]:
        items = p.get("items", [])
        gd = Counter(i.get("grade_id") for i in items)
        for i in items:
            grade_of[i["gongfa_id"]] = {
                "grade": i.get("grade_id"),
                "task_family": i.get("task_family", ""),
                "reason": i.get("reason", ""),
                "confidence": i.get("confidence", ""),
                "batch": p["id"],
            }
        proposals.append({
            "id": p["id"], "status": p.get("status"), "basis": p.get("basis"),
            "assessor": p.get("assessor"), "at": p.get("assessed_at", "")[:10],
            "policy": f'{p.get("policy_id")}@{p.get("policy_version")}',
            "count": len(items),
            "gradeDist": {k: v for k, v in gd.items() if k},
        })

    out_entries = []
    for gid, e in entries.items():
        prof = (e.get("content") or {}).get("profile") or {}
        gr = grade_of.get(gid, {})
        out_entries.append({
            "id": gid,
            "name": e.get("name", ""),
            "type": e.get("ontology_type", ""),
            "typeZh": TYPE_ZH.get(e.get("ontology_type", ""), e.get("ontology_type", "")),
            "version": e.get("content_version", ""),
            "status": e.get("entry_status", ""),
            "summary": prof.get("summary", ""),
            "problem": prof.get("problem", ""),
            "missing": prof.get("missing_fields", []),
            "sourceId": ((e.get("source_ref") or {}).get("source_id") or ""),
            "grade": gr.get("grade"),
            "gradeZh": GRADE_ZH.get(gr.get("grade"), "未初评"),
            "taskFamily": gr.get("task_family", ""),
            "confidence": gr.get("confidence", ""),
            "batch": gr.get("batch", ""),
        })
    out_entries.sort(key=lambda x: (GRADE_ORDER.index(x["grade"]) if x["grade"] in GRADE_ORDER else 99, x["name"]))

    # 文集：README 分组 + taxonomy 角色
    collections = []
    readme = read_text(GH / "docs/gongfa/README.md")
    group = ""
    body = readme.split("完整细粒度目录", 1)[-1]
    for line in body.splitlines():
        h = re.match(r"^### (.+?)\s*$", line)
        if h:
            group = h.group(1)
            continue
        m = re.match(r"^- \[(.+?)\]\((.+?)\)：(.*)$", line)
        if m and m.group(2).endswith(".md") and m.group(2) not in ("AGENTS.md", "README.md"):
            f = norm(m.group(2))
            meta = tax.get(f"docs/gongfa/{f}", {})
            collections.append({
                "file": f, "title": m.group(1), "role": m.group(3).strip(),
                "group": group, "taxRole": meta.get("role", ""),
            })

    sources = []
    for s in reg["sources"]:
        sources.append({
            "id": s["id"], "kind": s.get("kind"), "path": norm(s.get("path", "")),
            "revision": (s.get("git_revision") or "")[:7],
            "captured": (s.get("captured_at") or "")[:10],
            "anchors": len(s.get("included_anchors") or []),
        })

    catalog = {"total": 0, "gradeDist": {}}
    cm = GH / "metadata/gongfa/catalog.md"
    if cm.exists():
        text = read_text(cm)
        rows = [l for l in text.splitlines()
                if l.startswith("| ") and "品级" not in l.split("|")[1] and not l.startswith("|:")]
        catalog["total"] = len(rows)
        catalog["gradeDist"] = dict(Counter(r.split("|")[1].strip() for r in rows))
        m = re.search(r"输入绑定：`([0-9a-f]+)`", text)
        catalog["binding"] = (m.group(1)[:12] + "…") if m else ""

    type_dist = dict(Counter(e["ontology_type"] for e in reg["gongfa"]))
    grade_dist = dict(Counter(grade_of[gid].get("grade") for gid in entries if gid in grade_of))

    return {
        "vocabulary": reg["vocabulary"],
        "policy": {
            "id": reg["policies"][0]["id"],
            "version": reg["policies"][0]["version"],
            "status": reg["policies"][0]["status"],
            "ordering": reg["policies"][0].get("ordering", []),
        },
        "entries": out_entries,
        "collections": collections,
        "sources": sources,
        "proposals": proposals,
        "catalog": catalog,
        "stats": {
            "registered": len(entries),
            "collections": len(collections),
            "sources": len(reg["sources"]),
            "assessments": len(reg.get("assessments", [])),
            "graded": len(grade_of),
            "gradeDist": grade_dist,
            "typeDist": type_dist,
            "missingFieldCounts": dict(Counter(
                f for e in out_entries for f in e["missing"]
            )),
        },
    }


def build_faqi():
    fj = load_json(GH / "metadata/faqi.json")
    pga = fj["provisional_grade_assignments"]

    def cat_of(sid: str) -> str:
        if sid.startswith("dep-category-"):
            return "category"
        if sid.startswith("dep-"):
            return "dep"
        return "impl"

    cat_by_scope = {p.get("scope", ""): cat_of(p["subject_id"]) for p in pga}
    cat_by_grade_name = {}
    for p in pga:
        cat_by_grade_name.setdefault(p["grade_id"], set()).add(cat_of(p["subject_id"]))

    # 从只读总表取名称与解释；用 scope 前缀把条目挂回 subject 视角类别
    items = []
    cat = GH / "tools/faqi-catalog.md"
    if cat.exists():
        for line in read_text(cat).splitlines():
            if not line.startswith("| ") or "品级" in line.split("|")[1] or line.startswith("|:"):
                continue
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                item = {"gradeZh": parts[0], "name": parts[1], "explain": parts[2], "cat": ""}
                for scope, c in cat_by_scope.items():
                    if scope and item["explain"].startswith(scope[:28]):
                        item["cat"] = c
                        break
                items.append(item)

    # 品级中文名 -> 规范化 key
    zh_to_key = {zh: k for k, zh in GRADE_ZH.items()}
    for it in items:
        it["grade"] = zh_to_key.get(it["gradeZh"], "")
        it["tier"] = it["grade"].split("-")[0] if it["grade"] else ""
        it["seg"] = it["grade"].split("-")[1] if it["grade"] else ""

    grade_dist = dict(Counter(p["grade_id"].replace("faqi-", "") for p in pga))
    cat_dist = dict(Counter(cat_of(p["subject_id"]) for p in pga))
    total_items = len(items)

    # 外部资源登记表行数（9 个分类 YAML）
    ext_rows = 0
    ext_files = []
    ext_dir = GH / "assets/external-resources"
    if ext_dir.is_dir():
        for f in sorted(ext_dir.glob("*.yml")):
            if f.name == "schema.yml":
                continue
            n = len(re.findall(r"^- id:", read_text(f), re.M))
            ext_rows += n
            ext_files.append({"file": f.name, "rows": n})

    dg = fj.get("dependency_graph", {})
    return {
        "items": items,
        "gradeDist": grade_dist,
        "catDist": cat_dist,
        "extRows": ext_rows,
        "extFiles": ext_files,
        "tierTotals": {
            "tian": sum(v for k, v in grade_dist.items() if k.startswith("tian")),
            "di": sum(v for k, v in grade_dist.items() if k.startswith("di")),
            "xuan": sum(v for k, v in grade_dist.items() if k.startswith("xuan")),
            "huang": sum(v for k, v in grade_dist.items() if k.startswith("huang")),
        },
        "counts": {
            "provisional": len(pga),
            "objects": len(fj.get("objects", [])),
            "localEntries": len(fj.get("local_entries", [])),
            "localExclusions": len(fj.get("local_exclusions", [])),
            "externalSources": len(fj.get("external_sources", [])),
            "externalReviews": len(fj.get("external_reviews", [])),
            "sources": len(fj.get("sources", [])),
            "relations": len(fj.get("relations", [])),
            "references": len(fj.get("references", [])),
            "depObjects": len(dg.get("objects", [])),
        },
        "limits": fj.get("limits", {}),
        "dependencyGraph": {
            "source": norm(dg.get("source_path", "")),
            "anchor": dg.get("source_anchor", ""),
            "observed": (dg.get("observed_at") or "")[:10],
            "sha": (dg.get("source_sha256") or "")[:12],
        },
        "ontologySha": (fj.get("ontology", {}).get("sha256") or "")[:12],
        "reviewedAt": (fj.get("reviewed_at") or "")[:10],
        "sourceRevision": (fj.get("source_revision") or "")[:7],
        "totalItems": total_items,
    }


def build_research(tax):
    base = GH / "research"
    mirrors = {"vibe-cybersecurity-cn", "vibe-harness-cn", "vibe-mathing-cn-public"}
    special = {"facts", "harness"}
    domains = []
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        readme = d / "README.md"
        if not readme.exists():
            continue
        title = ""
        for line in read_text(readme).splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break
        n, md = count_files(d)
        raw_dir = d / "raw"
        raw_n = count_files(raw_dir)[0] if raw_dir.is_dir() else 0
        meta = tax.get(f"research/{d.name}/README.md", {})
        kind = "mirror" if d.name in mirrors else ("facts" if d.name == "facts" else
                                                   ("subject" if d.name == "harness" else "repo"))
        domains.append({
            "dir": d.name, "title": title or meta.get("title", "") or d.name,
            "role": meta.get("role", ""), "kind": kind,
            "files": n, "md": md, "rawFiles": raw_n,
            "analysis": (d / "analysis.md").exists(),
            "deepDive": (d / "deep-dive.md").exists(),
            "raw": raw_dir.is_dir(),
            "domainYml": (d / "domain.yml").exists(),
            "notes": (d / "notes").is_dir(),
        })
    return {"domains": domains}


def build_gates():
    mk = read_text(REPO / "Makefile")
    help_block = mk.split("help:", 1)[-1].split("\n\n", 1)[0]
    descs = {}
    for m in re.finditer(r"@echo \"  ([\w-]+)\s+-\s+(.+?)\"", help_block):
        descs[m.group(1)] = m.group(2)
    targets = []
    for m in re.finditer(r"^([a-z][a-z0-9-]*):", mk, re.M):
        name = m.group(1)
        targets.append({
            "name": name,
            "desc": descs.get(name, ""),
            "group": GATE_GROUPS.get(name, "其他"),
            "guards": GATE_GUARDS.get(name, ""),
        })
    test_line = re.search(r"^test:\s*(.+)$", mk, re.M)
    in_test = set(test_line.group(1).split()) if test_line else set()
    for t in targets:
        t["inTest"] = t["name"] in in_test

    scripts = []
    for f in sorted((GH / "scripts").iterdir()):
        if f.is_file() and f.suffix == ".py":
            scripts.append({"name": f.name, "lines": len(read_text(f).splitlines()),
                            "role": "check" if f.name.startswith("check") else
                                    "sync" if f.name.startswith("sync") else
                                    "test" if f.name.startswith("test") else "fetch"})

    ignores = re.search(r"lint:\n(?:.*\n)*?.*?--ignore (.+)$", mk)
    excluded = re.findall(r"--ignore '?([^\s']+)'?", ignores.group(1)) if ignores else []
    return {
        "targets": targets,
        "scripts": scripts,
        "inTest": sorted(in_test),
        "excludedFromLint": excluded,
        "testCount": len(in_test),
    }


def build_glossary():
    y = try_yaml(GH / "metadata/glossary.yml")
    terms = []
    if isinstance(y, dict) and isinstance(y.get("terms"), dict):
        for k, v in y["terms"].items():
            if isinstance(v, dict):
                terms.append({"key": k, "zh": v.get("zh", ""), "desc": v.get("description", "")})
    if not terms:
        terms = [{"key": t["key"], "zh": t.get("zh", ""), "desc": t.get("description", "")}
                 for t in parse_simple_yaml_terms(GH / "metadata/glossary.yml")]
    return {"terms": terms}


def main():
    tax = parse_taxonomy_docs(GH / "metadata/taxonomy.yml")
    data = {
        "meta": build_meta(),
        "overview": build_overview(),
        "tree": build_tree(),
        "gongfa": build_gongfa(tax),
        "faqi": build_faqi(),
        "research": build_research(tax),
        "gates": build_gates(),
        "glossary": build_glossary(),
        "paths": parse_reading_paths(GH / "metadata/taxonomy.yml"),
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* 由 viz/build/extract.py 生成，请勿手改。 */\n")
        fh.write("window.VIZ_DATA = ")
        fh.write(payload)
        fh.write(";\n")
    kb = OUT.stat().st_size / 1024
    print(f"OK  {OUT.relative_to(REPO)}  {kb:.1f} KB")
    print(f"    功法登记 {data['gongfa']['stats']['registered']} 条 / 文集 {data['gongfa']['stats']['collections']} 篇 / 来源 {data['gongfa']['stats']['sources']} 个")
    print(f"    法器 {data['faqi']['totalItems']} 项 / 研究对象 {len(data['research']['domains'])} 个")
    print(f"    门禁 {len(data['gates']['targets'])} 个目标，make test 串联 {data['gates']['testCount']} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())

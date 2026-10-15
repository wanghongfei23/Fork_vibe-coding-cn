# viz/ Agent 指南

本目录是面向人类的**项目可视化图册**：把仓库的结构、机制和设计思路做成可交互的静态页面，
用于快速摸清项目，以及投屏讲解给第一次接触本项目的人。

本目录是独立附属产物，不属于 `.github/docs/`（知识）、`.github/prompts/`（指令）、
`.github/skills/`（能力）的三层内容架构，也不被 `Makefile` 的任何目标或 CI 检查引用。

## 结构

```text
viz/
├── README.md              # 使用说明与数据口径（面向读者）
├── AGENTS.md              # 本文件：维护规则（面向 Agent）
├── start.html             # 入门层入口
├── index.html             # 总览
├── design.html            # 设计原则
├── architecture.html      # 结构与机制
├── gongfa.html            # 功法体系
├── faqi.html              # 法器体系
├── research.html          # 研究域
├── gates.html             # 质量门禁
├── roles.html             # 三种读者
├── glossary.html          # 术语对照
├── assets/                # 样式、交互脚本与生成数据
└── build/                 # 数据提取、静态校验与渲染检查脚本
```

## 约束

- 零依赖、纯离线：页面不加载任何 CDN、字体或图表库，图元全部手写 SVG/DOM；新增页面必须遵守。
- `assets/data.js` 是生成物，不得手改；其内容全部来自实时扫描仓库。
- 页面只呈现仓库既有事实，不引入仓库外的新结论、新评级或新身份判断。
- 数据口径以 `README.md` 的「数据口径说明」为准；页面数字与源文件不一致时先查口径，不直接改数。
- 页面引用的外部内容必须标注出处，不整段转载。

## 数据更新

仓库内容变化后（新增功法、改 Makefile、迁移目录等）：

```bash
python viz/build/extract.py       # 重新生成 assets/data.js（只读仓库）
python viz/build/verify.py        # 静态校验：资源引用、内联脚本语法、数据字段
python viz/build/render_check.py  # 无头 Chromium 真实渲染校验 + 交互测试 + 截图
```

- 只更新数据跑第 1 步即可；改过页面代码后必须跑第 2、3 步。
- 三个脚本都只读仓库文件，不修改仓库其他内容；第 3 步需要 playwright + chromium。

## 提交规则

- `check-directory-docs.py` 要求本目录与 `assets/` 各自成对具备 `README.md` 和 `AGENTS.md`，
  缺一即失败。
- `build/shots/` 下的渲染截图是产物，不入库；`build/` 只有 `.py` 脚本入库。
- 本目录变更不影响 `.github/docs/` 正文，不需要同步更新知识库章节或 metadata 登记。

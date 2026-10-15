# viz/assets/ Agent 指南

本目录是 `viz/` 图册的共享资源层，存放样式、交互脚本与页面数据。职责说明面向读者，
写在 `README.md`；本文件只记录维护规则。

## 约束

- `data.js` 由 `viz/build/extract.py` 生成，**不得手改**。要改数据先改提取脚本，再重新生成。
- `style.css` 的改动会影响全部 10 个页面，改主题令牌前先确认页面在深浅两套主题下都正常。
- `app.js` 承载分面引擎、主题记忆、演示模式与导航，是全部页面的公共依赖，改动后必须跑渲染校验。
- 不引入 CDN、外部字体、图表库或任何运行时依赖；页面必须在 `file://` 协议下完全可用。
- 不在此目录放置构建产物、截图或临时文件。

## 验证

改过本目录任何文件后：

```bash
python viz/build/verify.py        # 资源引用、内联脚本语法、数据字段
python viz/build/render_check.py  # 无头 Chromium 真实渲染 + 交互测试
```

## 提交规则

- 本目录与 `viz/` 各自需要 `README.md` 和 `AGENTS.md` 成对存在，
  由 `check-directory-docs.py` 检查，缺一即失败。
- 新增文件前先确认它确实属于共享资源层，而非单个页面的私有内容。

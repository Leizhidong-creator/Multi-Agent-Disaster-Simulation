# 图像来源与证据口径

| 文件 | 类型 | 公开用途 | 证据说明 |
|---|---|---|---|
| `zhiyan-wordmark.svg` / `.png` | 科研字标 | README 首屏项目身份 | 由 `scripts/generate_readme_figures.py` 本地生成；SVG 中标题文字已轮廓化，不依赖 GitHub 客户端字体 |
| `method-architecture.svg` / `.png` | 论文式方法架构图 | 展示场景编码、Fast Brain、风险门控、Slow Brain 与同种子闭环验证 | 由生成脚本确定性绘制，不包含实验结果或外部素材；README 使用 SVG 以保证缩放清晰度 |
| `results-overview.svg` / `.png` | 实验与证据图 | 展示干预相对降幅、历史场景复现误差、仿真吞吐与知识库规模 | 直接读取 `docs/results/interventions.json`、`benchmark.json` 和 `historical-calibration.json`；知识库统计与可复现实验结果明确分区 |
| `icons/*.svg` | 章节线性图标 | README 二级标题导航 | 同一颜色、描边与视口规范的本地 SVG，不依赖第三方图床 |
| `crowd-distribution-audit.png` | 仿真实验输出 | 展示人群向瓶颈核心区汇聚的空间演化 | 由原项目 `scripts/verify_phase2_visual.py` 对 60 步事故场景生成 |
| `zhiyan-simulation-dashboard.png` | 项目历史运行截图 | 保留的产品界面证据 | 截图中的 Agent 数和密度不作为本仓库基准结果 |
| `zhiyan-control-workspace.png` | 公开仓库当前版本截图 | 保留的无 Key 控制台证据 | 2026-08-24 在无 `.env` 环境下从本仓库本地服务生成 |

旧版 `method-overview.*` 与 `intervention-comparison.*` 仅作为历史生成留档，不再被 README 引用。

所有图片均由项目负责人提供或由项目代码生成，不包含 API Key、二维码和个人身份信息。README 的量化实验结论以 `docs/results/` 中的 JSON 留档为准，不从界面截图反推数值。`93 / 52 / 25` 只表示知识工程规模，不表示检索准确率。

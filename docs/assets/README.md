# 图像来源与证据口径

| 文件 | 类型 | 公开用途 | 证据说明 |
|---|---|---|---|
| `method-overview.png` / `.svg` | 论文式方法总览 | README 首屏，展示场景输入、快慢双脑、RAG 与干预评估闭环 | 由 `scripts/generate_readme_figures.py` 确定性生成；PNG 为 300 DPI，SVG 为矢量源 |
| `intervention-comparison.png` / `.svg` | 实验数据图 | 对比峰值密度和出口通过率 | 直接读取 `docs/results/interventions.json` 生成，不从截图或手工表格取值 |
| `crowd-distribution-audit.png` | 仿真实验输出 | 展示人群向瓶颈核心区汇聚的空间演化 | 由原项目 `scripts/verify_phase2_visual.py` 对 60 步事故场景生成 |
| `zhiyan-simulation-dashboard.png` | 项目历史运行截图 | 保留的产品界面证据 | 截图中的 Agent 数和密度不作为本仓库基准结果 |
| `zhiyan-control-workspace.png` | 公开仓库当前版本截图 | 保留的无 Key 控制台证据 | 2026-08-24 在无 `.env` 环境下从本仓库本地服务生成 |

所有图片均由项目负责人提供或由项目代码生成，不包含 API Key、二维码和个人身份信息。README 的量化实验结论以 `docs/results/` 中的 JSON 留档为准，不从界面截图反推数值。

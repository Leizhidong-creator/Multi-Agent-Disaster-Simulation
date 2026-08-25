# 智演 Agent 顶会项目主页式 README 重构设计

## 目标

将当前偏求职问答和功能罗列的 README 重构为中文为主、英文术语为辅的科研项目主页。页面首先解释项目解决的问题、方法贡献、竞赛成果和实验结果，再提供系统演示与复现入口。求职价值通过方法难度、量化证据和作者贡献自然呈现，不出现“30 秒看懂项目”“面试官关心的问题”等面向面试场景的叙述。

## 设计依据

- 信息组织参考 DUSt3R、MASt3R、Segment Anything、UniAD 等公开研究仓库常见结构：研究身份、摘要、方法图、贡献、实验、复现与引用。
- 中文叙事以 `E:\A竞赛和项目\作品集文档.md` 中“问题 -> 方法 -> 结果”的智演 Agent 段落为主要素材。
- 量化结论以当前公开仓库的机器可读留档为准；作品集中标记为“包装估算”的数值不作为可复现实验结论。

## 首屏与视觉系统

首屏使用透明 SVG 科研字标替代原生 Markdown 大标题。字标主体为“智演 Agent”，中文采用宋体/衬线风格，英文采用现代无衬线风格；闪电与决策脉冲线融入字形，表达风险感知、快速推演与干预决策，不使用 emoji 或装饰性大背景。

字标下方依次放置：

1. 中文与英文副标题；
2. 第二十八届中国机器人及人工智能大赛国家级奖项、项目负责人和年份；
3. `Multi-Agent Simulation`、`Social Force Model`、`Fast-Slow Reasoning`、`RAG Diagnosis` 四个低饱和度技术标签；
4. 摘要、方法、实验、演示、复现和引用的文字导航。

整体采用深灰文字、冷蓝方法模块、青绿证据链、少量橙红风险提示。二级标题使用同一套小型线性图标，图标仅承担导航作用。

## README 信息结构

1. 科研字标与项目身份
2. 摘要 / Abstract
3. 方法概览 / Method
4. 主要贡献 / Contributions
5. 实验结果 / Results
6. 系统演示 / Demo
7. 复现指南 / Reproduction
8. 项目结构 / Repository Structure
9. 局限性 / Limitations
10. 作者贡献 / Author Contributions
11. 参考文献、引用与许可

## 方法架构图

架构图采用约 `1600 x 900` 的论文 Pipeline Figure，组织为“主干推演 + 慢脑旁路 + 闭环验证”，确保在 GitHub 正文宽度下仍可阅读。

- 上层 Fast Brain：`Scenario Encoding -> Agent Interaction Layers -> Temporal Evolution -> Crowd State`。Agent Interaction Layers 使用错位堆叠模块，表现邻域感知、社会力计算、避障和行为更新；时间轴显示 `t -> t+1 -> ... -> t+n`。
- 中部 Risk-aware Gating：由密度、速度和拥堵状态计算风险分数，只在超过阈值时触发慢脑。
- 下层 Slow Brain：`Risk Context -> Evidence Retrieval -> Reasoning -> Intervention Head`，表达异常上下文提取、RAG 证据检索、证据排序与干预参数生成。
- 右侧 Matched-seed Replay：在同场景、同种子下比较 Baseline 与 Intervention，输出峰值密度变化、通行指标、行为轨迹和结构化报告。

所有数据流从左向右，不使用交叉箭头；文字必须位于模块内部；标签采用中英双语但控制长度。

## 贡献与实验表达

主要贡献使用论文式表述：

1. Fast-Slow Multi-Agent 架构；
2. 社会力模型、异质群体画像与时序状态传播结合的可解释仿真环境；
3. 证据增强的 RAG 风险诊断链；
4. 同随机种子的反事实干预复跑机制。

实验区区分证据层级：

- 可复现结果：本地基准 `56.98 simulation steps/s`、历史场景峰值密度复现相对误差 `0.43%`、单向导流峰值密度降低 `23.10%`。
- 项目规模统计：93 条可检索内容、52 条 reviewed、25 条 golden。此处只描述知识工程规模，不作为检索准确率。
- 不进入主结果：缺少公开评测记录的 `Recall@5 85%-90%` 与包装估算的 `18%-27%`。

干预效果图以相对 Baseline 的百分比为主要视觉编码，不再突出 `6.433 -> 4.947` 这组孤立绝对值。历史校准称为“峰值密度复现相对误差”，不转换为“99.57% 准确率”。

## 系统演示与作者贡献

系统演示位于实验结果之后，只选取能证明“场景推演、风险诊断、干预比较”的高清图片，并使用科研图注解释图中证据，不创建产品卡片墙。

作者贡献采用 CRediT 风格，明确项目负责人承担的 Conceptualization、Methodology、Software、Validation、Visualization 和 Project Administration。该部分用于展示个人所有权和技术深度，但不出现面试或 HR 话术。

## 复现、安全与引用

- 无 Key 模式保持为默认路径；LLM 配置只展示 `.env.example` 中的变量名和占位值。
- 提交前运行工作区、暂存区和 Git 历史的敏感信息扫描。
- 方法参考保留 Social Force Model、escape panic simulation 和 Talker-Reasoner，明确参考文献只说明方法来源，不验证本仓库实验结论。
- 保留 `CITATION.cff`、MIT License、实验限制和安全免责声明。

## 验收标准

- README 不再包含“30 秒看懂项目”“面试官关心的问题”或“核心页面”。
- 首屏存在高清 SVG 字标、统一技术标签和论文式导航。
- 方法图在约 1000 px 显示宽度下文字可读、无出框、无交叉箭头。
- 实验图以相对变化、指标含义和测试条件为核心，数值与 `docs/results/*.json` 一致。
- 图像可由仓库脚本确定性重新生成；相应测试覆盖资产存在性、README 顺序和数据来源。
- 测试、README 链接检查和敏感信息扫描通过后，提交并推送到 `codex/public-release`。

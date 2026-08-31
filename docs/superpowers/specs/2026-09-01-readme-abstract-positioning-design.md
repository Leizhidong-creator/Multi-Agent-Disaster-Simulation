# 智演 Agent 摘要定位句设计

## 目标

在 README 摘要开头增加中英文一句话定位，使读者在进入详细摘要前明确项目采用的 Agent 范式：这是基于 Agent-Based Modeling 的具身多智能体人群仿真与风险治理系统，而不是将每个行人描述为具备通用规划、工具调用和 ReAct 循环的 LLM Agent。

## 位置与排版

- 定位句放在 `摘要 / Abstract` 二级标题之后、现有摘要正文之前。
- 不增加“项目定位”等三级标题，不使用卡片、表格、徽章或引用块。
- 中文定位句使用独立段落并加粗，作为快速阅读入口。
- 英文定位句紧随中文，使用独立斜体段落，视觉权重略低于中文。
- 英文段落之后保留一个空行，再进入现有摘要正文。

## 最终文案

中文：

> 一个基于 Agent-Based Modeling 的具身多智能体人群仿真与风险治理系统，通过事件触发的 Slow Brain、RAG 证据检索与同种子反事实复演，实现风险诊断、策略生成与干预验证。

英文：

> An embodied multi-agent crowd simulation and risk-governance system built on Agent-Based Modeling, with event-triggered Slow Brain reasoning, retrieval-augmented evidence grounding, and matched-seed counterfactual evaluation.

## 表达边界

- `embodied multi-agent` 对应具有独立状态、局部感知、行为更新和环境反馈的行人 Agent。
- `event-triggered Slow Brain` 对应风险阈值触发的代表性 Agent 推理，不暗示所有 Agent 每步调用 LLM。
- `retrieval-augmented evidence grounding` 对应 RAG 为风险诊断和治理建议提供规范证据。
- `matched-seed counterfactual evaluation` 对应 Baseline 与 Intervention 共享随机种子的成对复演。
- 不使用 `autonomous LLM agent`、`ReAct agent`、`tool-using agent` 或“每个 Agent 自主规划”等超出当前实现的表述。

## 验收标准

- 定位句准确出现在摘要标题和原摘要正文之间。
- 中英文含义一致，均覆盖 ABM、具身多智能体、Slow Brain、RAG 和同种子反事实验证。
- README 不新增图片或卡片，不改变现有摘要正文、方法图及结果图。
- README 相关测试、全量测试、本地链接检查与敏感信息扫描通过后再推送远端 `main`。

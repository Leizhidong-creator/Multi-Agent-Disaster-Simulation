<div align="center">

<img src="docs/assets/zhiyan-wordmark.svg" alt="智演 Agent" width="860">

### 面向城市高密度人群风险治理的快慢思考多智能体系统

*A Fast-Slow Multi-Agent System for Risk-aware Crowd Governance*

**第二十八届中国机器人及人工智能大赛 · 国家级奖项（国奖）** · 项目负责人 · 2026

<kbd>Multi-Agent Simulation</kbd> &nbsp; <kbd>Social Force Model</kbd> &nbsp; <kbd>Fast-Slow Reasoning</kbd> &nbsp; <kbd>RAG Diagnosis</kbd>

[摘要](#abstract) · [方法](#method) · [实验](#results) · [复现指南](#reproduction) · [引用](#references)

</div>

<a id="abstract"></a>

## <img src="docs/assets/icons/abstract.svg" width="22" alt=""> 摘要 / Abstract

**一个基于 Agent-Based Modeling 的具身多智能体人群仿真与风险治理系统，通过事件触发的 Slow Brain、RAG 证据检索与同种子反事实复演，实现风险诊断、策略生成与干预验证。**

*An embodied multi-agent crowd simulation and risk-governance system built on Agent-Based Modeling, with event-triggered Slow Brain reasoning, retrieval-augmented evidence grounding, and matched-seed counterfactual evaluation.*

面向高密度人群场景中**风险识别滞后、规范检索与疏散推演相互割裂**的问题，智演 Agent 构建“实时仿真—风险诊断—规范检索—干预复演”的多智能体治理闭环。系统以向量化社会力模型持续推进群体状态，在风险阈值触发时调度 Slow Brain，并将仿真指标、个体行为与本地规则证据组织为可追溯诊断；中央护栏、单向导流和出口拓宽等建议进一步被转换为可执行参数，在相同随机种子下进行反事实复跑。

<a id="method"></a>

## <img src="docs/assets/icons/method.svg" width="22" alt=""> 方法概览 / Method

<p align="center">
  <img src="docs/assets/method-architecture.svg" alt="智演 Agent 方法架构：场景编码、Fast Brain、风险门控、Slow Brain 与同种子闭环验证" width="100%">
</p>

<p align="center"><sub><b>图 1｜方法架构。</b> 上方蓝色主线将场景编码为 Agent 交互并持续推进群体状态；Risk Gate 在密度、速度或对向冲突超过阈值时，将异常上下文送入下方橙色证据推理链；生成的 Strategy 与 Baseline 最终进入右侧绿色模块，在相同随机种子下比较干预前后的成对变化。</sub></p>

**Fast Brain：高频群体演化。** 场景拓扑、出入口、障碍物与异质群体画像被编码为初始状态；[`simulation.py`](app/services/simulation.py) 通过 NumPy 向量化计算局部交互力、碰撞与边界约束，并沿 `t → t+1 → … → t+n` 连续输出密度、速度、拥堵和行为轨迹。

**Risk-aware Gating：事件触发调度。** 快脑在每个仿真步评估密度、速度衰减和对向冲突。常态阶段保持低成本物理更新；超过阈值时才抽取异常区域与代表性 Agent 上下文，避免复杂推理持续占用仿真预算。

**Slow Brain：证据增强推理。** [`slow_brain.py`](app/services/slow_brain.py) 组织 Agent 的感知、情绪、意图、对话与动作；[`rag.py`](app/engine/rag.py) 将风险上下文映射到规则、案例和研究材料，再由诊断链生成带证据来源的干预参数。未配置 LLM Provider 时，系统自动使用本地确定性推理器，不中断物理仿真。

**Matched-seed Replay：反事实闭环。** 中央护栏、单向导流和出口拓宽作用于实际边界、生成方向与寻路参数。Baseline 与 Intervention 共享随机种子，输出峰值密度、危险持续时间、出口通过率、行为摘录和报告，形成可比较而非只可阅读的治理建议。

<a id="contributions"></a>

## <img src="docs/assets/icons/contributions.svg" width="22" alt=""> 主要贡献 / Contributions

1. **快慢双脑架构。** 针对人群仿真既要连续推进、又要支持复杂风险判断的问题，将高频 NumPy 物理演化与事件触发的 LLM / Local Slow Brain 解耦，降低多智能体并行中的推理成本。
2. **可解释群体动力学。** 将社会力模型、异质群体画像、时序状态传播和个体行为日志纳入同一仿真环境，使宏观拥堵形成过程能够追溯到局部交互与 Agent 决策。
3. **证据增强风险诊断。** 针对消防规范、事故案例与疏散研究分散的问题，构建 ChromaDB + LangChain RAG 链路，把指标、行为与检索证据共同写入诊断报告。
4. **可执行干预验证。** 将治理建议映射为可调仿真参数，并以同种子成对复跑衡量相对变化，使“风险展示”进一步转化为可检验的决策支持流程。

<a id="results"></a>

## <img src="docs/assets/icons/results.svg" width="22" alt=""> 实验结果 / Results

<p align="center">
  <img src="docs/assets/results-overview.svg" alt="智演 Agent 量化结果：三次固定种子的干预效果与历史场景复现误差" width="100%">
</p>

<p align="center"><sub><b>图 2｜量化结果。</b> 左图保留三次固定种子的个体结果，并以菱形与误差棒表示均值 ± 标准差；右图比较历史目标与仿真复现值。</sub></p>

| 量化指标 | 测试结果 | 指标说明 |
|---|---:|---|
| 历史场景峰值密度复现精度 | 复现相对误差 **0.43%** | 历史目标为 16.40 人 / m²，仿真复现为 16.33 人 / m²；见 [`historical-calibration.json`](docs/results/historical-calibration.json) |
| 单向导流拥堵缓解效率 | 峰值密度降低 **23.10%** | 3 个固定种子、300 Agent 容量、120 步的同种子成对实验；见 [`interventions.json`](docs/results/interventions.json) |
| 本地仿真推进吞吐 | **56.98 simulation steps/s** | `accident` 场景运行 120 步，最大同时活跃 157 Agent；见 [`benchmark.json`](docs/results/benchmark.json) |
| 知识库建设规模 | **93 / 52 / 25** | 分别为 retrievable / reviewed / golden 条目数，用于说明知识工程规模 |

### 空间演化 / Spatial Evolution

<p align="center">
  <img src="docs/assets/crowd-distribution-audit.png" alt="固定种子事故场景中 Pedestrian Agent 向瓶颈区域汇聚的四时刻空间演化" width="100%">
</p>

<p align="center"><sub><b>图 3｜瓶颈区域的空间演化。</b> 每个点代表一个 Pedestrian Agent，颜色与形状区分行进方向，浅色热度层表示局部占据量；四个关键时刻展示双向人流如何向收窄区聚集。</sub></p>

<details>
<summary><b>查看实验配置与复现命令</b></summary>

```powershell
# 本地物理仿真吞吐
python scripts/benchmark_simulation.py `
  --agents 300 --steps 120 --seed 20260824 `
  --output docs/results/benchmark.json

# 三类干预与 Baseline 的同种子成对比较
python scripts/evaluate_interventions.py `
  --agents 300 --steps 120 `
  --seeds 20260824 20260825 20260826 `
  --output docs/results/interventions.json

# 从 JSON 留档重新生成 README 科研图
python scripts/generate_readme_figures.py

# 复现固定种子的空间演化审计图
python scripts/verify_phase2_visual.py
```

</details>

<a id="reproduction"></a>

## <img src="docs/assets/icons/reproduction.svg" width="22" alt=""> 复现指南 / Reproduction

### 1. 环境安装

推荐 Python 3.11。Windows PowerShell 示例：

```powershell
git clone https://github.com/Leizhidong-creator/Multi-Agent-Disaster-Simulation.git
Set-Location Multi-Agent-Disaster-Simulation

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
```

`requirements.txt` 维护直接依赖，`requirements.lock` 固化完整传递依赖图。

### 2. 无 Key 本地模式

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

访问 [http://127.0.0.1:8000](http://127.0.0.1:8000)。不创建 `.env` 也可运行物理仿真、确定性个体解释、干预比较和报告骨架；LLM Slow Brain 保持禁用。

### 3. 可选 LLM / RAG 模式

```powershell
Copy-Item .env.example .env
python scripts/build_fire_safety_index.py
```

仅在本地 `.env` 中填写 OpenAI-compatible Provider。仓库中的 [`.env.example`](.env.example) 只有变量名与占位值，`.env` 已被 Git 忽略；本地向量索引使用进程内 ChromaDB，不公开启动 Chroma HTTP Server。

### 4. 发布前安全检查

```powershell
python scripts/security_scan.py --worktree --staged --history
```

公开版不包含真实 API Key、个人身份信息、竞赛申报材料或内部 Agent 指令。扫描器只报告规则名、文件和行号，不回显疑似敏感值。

<details>
<summary><b>主要 API</b></summary>

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/health` | 服务健康检查 |
| `GET` | `/api/bootstrap` | 场景、阈值、运行限制与 Provider 状态 |
| `POST` | `/api/simulate` | 返回仿真帧、行为日志与汇总指标 |
| `POST` | `/api/engine/run` | 运行底层沙盒引擎 |
| `POST` | `/api/report` | 生成 Markdown 诊断报告 |
| `POST` | `/api/report/pdf` | 导出 PDF 报告 |

FastAPI 交互文档位于 `http://127.0.0.1:8000/docs`。

</details>

<a id="structure"></a>

## <img src="docs/assets/icons/structure.svg" width="22" alt=""> 项目结构 / Repository Structure

```text
.
├── app/
│   ├── api/              # FastAPI 路由与公开协议
│   ├── engine/           # 沙盒、LLM、RAG 与 PDF 输出
│   ├── models/           # Pydantic 请求/响应模型
│   └── services/         # 仿真、Slow Brain、报告和运行服务
├── frontend/             # 2.5D 控制台与交互逻辑
├── scripts/              # 建库、实验、图表与安全检查
├── tests/                # 本地降级、安全和实验契约测试
├── docs/assets/          # 科研图与资产来源说明
├── docs/results/         # 机器可读实验留档
├── sources/              # 基础方法引用核验记录
├── fire_safety_rules.txt # 公开 RAG 示例规则
└── .env.example          # 不含真实凭据的配置模板
```

<a id="limitations"></a>

## <img src="docs/assets/icons/limitations.svg" width="22" alt=""> 局限性 / Limitations

- **跨场景验证：** 当前实验聚焦典型瓶颈与固定种子对比，后续将扩展不同空间形态、客流强度与真实轨迹数据的交叉验证。
- **推理与知识覆盖：** RAG 语料覆盖、Slow Brain 输出稳定性及端到端时延仍需通过更大规模的检索基准和消融实验持续优化。

<a id="author-contributions"></a>

## <img src="docs/assets/icons/author.svg" width="22" alt=""> 作者贡献 / Author Contributions

本项目由项目负责人主导总体方案与核心实现，贡献按 CRediT 风格说明如下：

| 贡献角色 | 具体工作 |
|---|---|
| **Conceptualization** | 定义“实时仿真—风险诊断—规范检索—干预复演”的闭环问题与系统边界 |
| **Methodology** | 设计 Fast-Slow 分层架构、风险触发机制、RAG 证据链和同种子反事实实验 |
| **Software** | 主导向量化人群动力学、Slow Brain、ChromaDB + LangChain 检索、干预参数映射与前后端联调 |
| **Validation** | 完成历史峰值密度校准、固定种子干预实验、吞吐测试与安全回归 |
| **Visualization** | 设计 2.5D 人群沙盒、实验审计图、方法架构图与结果展示体系 |
| **Project Administration** | 负责竞赛目标拆解、技术路线推进、整体交付与国奖项目管理 |

<a id="references"></a>

## <img src="docs/assets/icons/references.svg" width="22" alt=""> 参考文献与引用 / References & Citation

1. Helbing, D. & Molnár, P. [*Social force model for pedestrian dynamics*](https://doi.org/10.1103/PhysRevE.51.4282). *Physical Review E*, 1995.
2. Helbing, D., Farkas, I. & Vicsek, T. [*Simulating dynamical features of escape panic*](https://doi.org/10.1038/35035023). *Nature*, 2000.
3. Lewis, P. et al. [*Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*](https://arxiv.org/abs/2005.11401). *NeurIPS*, 2020.
4. Christakopoulou, K., Mourad, S. & Matarić, M. [*Agents Thinking Fast and Slow: A Talker-Reasoner Architecture*](https://arxiv.org/abs/2410.08328), 2024.

上述文献用于说明方法来源，不构成对本仓库实现或实验结论的背书。引用核验记录见 [`sources/research_foundational_methods.md`](sources/research_foundational_methods.md)。

```bibtex
@software{lei_zhiyan_agent_2026,
  author  = {Zhidong Lei},
  title   = {Zhiyan Agent: A Fast-Slow Multi-Agent System for Risk-aware Crowd Governance},
  year    = {2026},
  url     = {https://github.com/Leizhidong-creator/Multi-Agent-Disaster-Simulation},
  license = {MIT}
}
```

完整软件引用元数据见 [`CITATION.cff`](CITATION.cff)。代码以 [MIT License](LICENSE) 发布。

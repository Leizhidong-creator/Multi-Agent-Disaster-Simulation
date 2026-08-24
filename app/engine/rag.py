from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

try:
    import chromadb
    from langchain_core.documents import Document
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_openai import ChatOpenAI
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover
    chromadb = None
    Document = None
    StrOutputParser = None
    ChatPromptTemplate = None
    RunnableLambda = None
    HuggingFaceEmbeddings = None
    ChatOpenAI = None
    RecursiveCharacterTextSplitter = None

from app.core.config import settings


def _ensure_langchain_dependencies() -> None:
    if not all(
        [
            chromadb,
            Document,
            StrOutputParser,
            ChatPromptTemplate,
            RunnableLambda,
            HuggingFaceEmbeddings,
            ChatOpenAI,
            RecursiveCharacterTextSplitter,
        ]
    ):
        raise RuntimeError(
            "LangChain/Chroma dependencies are missing. Install requirements before using the RAG pipeline."
        )


class LocalChromaVectorStore:
    """Small embedded-only adapter between LangChain documents and ChromaDB."""

    def __init__(self, *, collection: Any, embeddings: Any) -> None:
        self._collection = collection
        self._embeddings = embeddings

    def add_documents(self, documents: Sequence[Any]) -> None:
        texts = [str(document.page_content) for document in documents]
        metadatas = [dict(document.metadata) for document in documents]
        ids = [
            f"chunk-{metadata.get('chunk_index', index)}"
            for index, metadata in enumerate(metadatas)
        ]
        self._collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=self._embeddings.embed_documents(texts),
        )

    def similarity_search(self, query: str, *, k: int = 4) -> list[Any]:
        result = self._collection.query(
            query_embeddings=[self._embeddings.embed_query(query)],
            n_results=k,
        )
        texts = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        return [
            Document(page_content=text, metadata=metadata or {})
            for text, metadata in zip(texts, metadatas)
        ]


def build_fire_safety_vector_store(
    *,
    rules_path: str | Path | None = None,
    persist_dir: str | Path | None = None,
    embedding_model_name: str | None = None,
) -> Any:
    _ensure_langchain_dependencies()
    rules_file = Path(rules_path or settings.fire_safety_rules_path)
    chroma_dir = Path(persist_dir or settings.chroma_dir)
    chroma_dir.mkdir(parents=True, exist_ok=True)

    raw_text = rules_file.read_text(encoding="utf-8")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=260,
        chunk_overlap=48,
        separators=["\n\n", "\n", "。", "；", " "],
    )
    chunks = splitter.split_text(raw_text)
    documents = [
        Document(
            page_content=chunk,
            metadata={"source": str(rules_file), "chunk_index": index},
        )
        for index, chunk in enumerate(chunks)
    ]

    embeddings = HuggingFaceEmbeddings(
        model_name=embedding_model_name or settings.embedding_model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_or_create_collection(
        name="fire_safety_rules",
        metadata={"hnsw:space": "cosine"},
    )
    vector_store = LocalChromaVectorStore(collection=collection, embeddings=embeddings)
    if vector_store._collection.count() == 0:  # type: ignore[attr-defined]
        vector_store.add_documents(documents)
    return vector_store


def generate_diagnostic_report(
    simulation_logs: Sequence[dict[str, Any]] | dict[str, Any] | str,
    *,
    vector_store: Any | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    _ensure_langchain_dependencies()
    metrics = _extract_simulation_metrics(simulation_logs)
    vector_store = vector_store or build_fire_safety_vector_store()
    docs = vector_store.similarity_search(
        "高密度人员聚集 疏散净宽度 护栏分流 走道安全距离 弱势群体 安全阈值",
        k=4,
    )
    context = _format_docs(docs)
    llm_section = _generate_rag_sections(
        metrics,
        context=context,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
    )
    density_chart_markdown = _build_density_chart_markdown(
        metrics["density_series"],
        metrics["density_sample_interval_seconds"],
        baseline_series=metrics["baseline_density_series"],
        safety_threshold=4.0,
    )
    micro_table = _build_micro_behavior_table(metrics["logs"])
    code_table = _build_code_mapping_table(docs)
    velocity_chart = _build_velocity_chart_markdown(
        metrics.get("velocity_series") or [],
        metrics["density_series"],
        metrics["density_sample_interval_seconds"],
    )
    risk_timeline = _build_risk_timeline_markdown(
        metrics.get("risk_level_series") or [],
        metrics["density_sample_interval_seconds"],
    )
    metrics_table = _build_metrics_table(metrics)

    # 生成结构化干预建议
    interventions = _generate_interventions(metrics, llm_section.get("interventions_raw", ""))

    risk_banner = _build_risk_banner(metrics)
    comparison_table = _build_comparison_table(metrics)
    mitigation_behavior_section = _build_mitigation_behavior_section(metrics)

    sections = [
        "# 城市街道人群拥堵诊断报告",
        risk_banner,
        "## 摘要",
        llm_section["abstract"],
        "## 动态演变图",
        density_chart_markdown,
        "## 速度-密度演变图",
        velocity_chart,
        "## 风险等级时间线",
        risk_timeline,
        "## 仿真核心指标",
        metrics_table,
        comparison_table,
        mitigation_behavior_section,
        "## 典型微观行为表",
        micro_table,
        "## 规范映射与整改方案",
        llm_section["mapping"],
        code_table,
    ]
    report_markdown = "\n\n".join(section for section in sections if section.strip())

    return {
        "report_markdown": report_markdown,
        "recommended_interventions": interventions,
        "default_intervention": interventions[0] if interventions else None,
        "comparison_targets": {
            "peak_density": metrics.get("frontend_peak_density", 0.0),
            "slow_brain_trigger_count": metrics.get("slow_brain_trigger_count", 0),
            "dangerous_steps": metrics.get("deadlock_seconds", 0.0),
        },
    }


def _build_risk_banner(metrics: dict[str, Any]) -> str:
    peak = metrics.get("frontend_peak_density", 0.0)
    summary = metrics.get("summary") or {}
    fatal_min = summary.get("literature_target_min", 12.0)
    critical = 5.0
    safe = 4.0

    if peak >= fatal_min:
        level = "**FATAL**"
        desc = "已进入致死密度区间，踩踏事故风险极高"
    elif peak >= critical:
        level = "**DANGER**"
        desc = "超过临界危险密度，存在严重安全隐患"
    elif peak >= safe:
        level = "**WARNING**"
        desc = "超过安全密度上限，需持续监测"
    else:
        level = "**SAFE**"
        desc = "处于安全密度范围内"

    return (
        "## 风险评估总览\n\n"
        "| 风险等级 | 当前实时涌现密度 | 致死密度基准 | 安全阈值 |\n"
        "|:---:|:---:|:---:|:---:|\n"
        f"| {level} | {peak:.2f} 人/m² | {fatal_min:.0f}-16.0 人/m² | {safe:.0f} 人/m² |\n\n"
        f"**评估结论**: {desc}\n\n"
        "---\n"
    )


def _build_comparison_table(metrics: dict[str, Any]) -> str:
    baseline_peak = metrics.get("baseline_peak_density", 0.0)
    current_peak = metrics.get("frontend_peak_density", 0.0)
    if baseline_peak <= 0:
        return ""

    reduction = ((baseline_peak - current_peak) / baseline_peak * 100) if baseline_peak > 0 else 0
    verdict = "有效" if current_peak < baseline_peak else "无效"

    summary = metrics.get("summary") or {}
    baseline_summary = metrics.get("baseline_summary") or {}

    return (
        "## 干预前后对比\n\n"
        "| 指标 | 干预前 | 干预后 | 变化 |\n"
        "|---|---:|---:|---:|\n"
        f"| 实时涌现密度 | {baseline_peak:.2f} 人/m² | {current_peak:.2f} 人/m² | {reduction:+.1f}% |\n"
        f"| 慢脑触发次数 | {int(baseline_summary.get('slow_brain_triggers', 0))} | {int(summary.get('slow_brain_triggers', 0))} | - |\n"
        f"| 对向冲突次数 | {int(baseline_summary.get('conflict_count', 0))} | {int(summary.get('conflict_count', 0))} | - |\n"
        f"| 出口通过率 | {baseline_summary.get('exit_pass_rate', 0):.1%} | {summary.get('exit_pass_rate', 0):.1%} | - |\n"
        f"\n**干预效果判定**: 整改{verdict}\n\n"
    )


def _build_mitigation_behavior_section(metrics: dict[str, Any]) -> str:
    strategy = str(metrics.get("mitigation_strategy") or "none")
    logs = metrics.get("logs") or []
    if strategy in ("none", "", "未设置") or not logs:
        return ""

    strategy_label = {
        "central_guardrail": "中央护栏分流",
        "one_way_flow": "单向导流",
        "widen_exits": "出口拓宽",
    }.get(strategy, strategy)

    grouped: dict[str, list[dict[str, Any]]] = {
        "normal_pedestrian": [],
        "group_family": [],
        "vulnerable": [],
    }
    for item in logs:
        content = item.get("content") or {}
        grouped.setdefault(str(content.get("typology") or "normal_pedestrian"), []).append(item)

    def _sample_text(typology: str) -> str:
        items = grouped.get(typology) or []
        if not items:
            return "当前日志样本不足，建议继续观察该类人群。"
        scored = sorted(items, key=lambda entry: float(entry.get("density") or 0.0), reverse=True)
        content = scored[0].get("content") or {}
        return str(content.get("action") or content.get("intention") or content.get("perception") or "当前日志样本不足。").replace("\n", " ")

    normal_text = _sample_text("normal_pedestrian")
    group_text = _sample_text("group_family")
    vuln_text = _sample_text("vulnerable")

    return (
        "## 措施后人群变化\n\n"
        f"当前方案为 **{strategy_label}**。结合措施后推演日志，可见不同人群对人流组织变化的响应如下：\n\n"
        f"- **常态行人**：{normal_text}\n"
        f"- **结伴群体**：{group_text}\n"
        f"- **弱势群体**：{vuln_text}\n"
    )


def _generate_interventions(metrics: dict[str, Any], raw_text: str) -> list[dict[str, Any]]:
    summary = metrics.get("summary") or {}
    peak_density = metrics.get("frontend_peak_density", 0.0)
    conflict_count = summary.get("conflict_count", 0)
    exit_rate = summary.get("exit_pass_rate", 0.0)
    velocity_decay = summary.get("velocity_decay_ratio", 1.0)

    interventions: list[dict[str, Any]] = []

    # 基于指标自动推荐干预类型
    if peak_density >= 8.0 or conflict_count >= 50:
        interventions.append({
            "type": "central_guardrail",
            "label": "中央护栏分流",
            "reason": f"峰值密度 {peak_density:.1f} 人/m²，冲突 {conflict_count} 次，需物理隔离双向人流",
            "expected_effect": "降低对向冲突 60%+，峰值密度下降 20-30%",
            "overlay_spec": {
                "barrier_x_start": 14.5,
                "barrier_x_end": 30.5,
                "barrier_height": 1.3,
                "barrier_half_width": 0.18,
            },
            "simulation_params": {
                "mitigation_strategy": "central_guardrail",
            },
        })

    if exit_rate < 0.5 or peak_density >= 6.0:
        interventions.append({
            "type": "widen_exits",
            "label": "出口拓宽",
            "reason": f"出口通过率仅 {exit_rate:.0%}，出口区域拥堵严重",
            "expected_effect": "提升出口通过率 30%+，降低出口区排队长度",
            "overlay_spec": {
                "widen_segments": [
                    {"x_start": 0.0, "x_end": 8.0, "extra_width": 0.95},
                    {"x_start": 37.0, "x_end": 45.0, "extra_width": 0.95},
                ],
            },
            "simulation_params": {
                "mitigation_strategy": "widen_exits",
            },
        })

    if conflict_count >= 30 or velocity_decay < 0.4:
        interventions.append({
            "type": "one_way_flow",
            "label": "单向导流",
            "reason": f"速度衰减比 {velocity_decay:.2f}，对向冲突频繁，需简化流线",
            "expected_effect": "消除对向冲突，速度恢复至安全区 80%+",
            "overlay_spec": {
                "block_direction": "south",
                "guide_marker_x": 22.5,
            },
            "simulation_params": {
                "mitigation_strategy": "one_way_flow",
            },
        })

    # 如果没有触发任何干预，添加一个默认建议
    if not interventions:
        interventions.append({
            "type": "central_guardrail",
            "label": "中央护栏分流（预防性）",
            "reason": "当前指标尚在安全范围，但建议预防性设置分流设施",
            "expected_effect": "维持当前安全水平，预防突发流量冲击",
            "overlay_spec": {
                "barrier_x_start": 14.5,
                "barrier_x_end": 30.5,
                "barrier_height": 1.3,
                "barrier_half_width": 0.18,
            },
            "simulation_params": {
                "mitigation_strategy": "central_guardrail",
            },
        })

    return interventions


def _generate_rag_sections(
    metrics: dict[str, Any],
    *,
    context: str,
    llm_base_url: str | None,
    llm_api_key: str | None,
    llm_model: str | None,
) -> dict[str, str]:
    llm = ChatOpenAI(
        base_url=(llm_base_url or settings.resolved_llm_base_url),
        api_key=(llm_api_key or settings.resolved_llm_api_key or "EMPTY"),
        model=(llm_model or settings.llm_model),
        temperature=0.2,
    )
    summary = metrics.get("summary") or {}
    prompt = ChatPromptTemplate.from_template(
        "你是公共安全分析师，请基于真实仿真指标与检索到的规范上下文，输出一个 JSON 对象。\n"
        "严格约束：\n"
        "- 只能使用输入中的数值、日志和检索上下文，禁止编造法规编号、机构、日期或额外统计值。\n"
        "- `abstract` 必须是 120-220 字中文摘要，明确引用实时涌现密度，并综合速度衰减、冲突次数等指标进行风险评估。\n"
        "- `mapping` 必须是 Markdown，包含一段因果分析和一段整改建议，可使用简短项目符号。\n"
        "- 如果存在基准环境实时涌现密度，必须明确写出基准与当前方案的差异。\n"
        "- 输出必须是合法 JSON，仅包含 `abstract` 和 `mapping` 两个字段。\n\n"
        "输入摘要：\n"
        "- 场景：{scenario}\n"
        "- 干预策略：{mitigation_strategy}\n"
        "- 基准环境实时涌现密度：{baseline_peak_density} 人/平方米\n"
        "- 本次真实实时涌现密度：{frontend_peak_density} 人/平方米\n"
        "- 仿真全程峰值密度：{summary_peak_density} 人/平方米\n"
        "- 慢脑触发次数：{slow_brain_trigger_count}\n"
        "- 当前风险等级：{current_risk_level}\n"
        "- 速度衰减比：{velocity_decay_ratio}（危险区/安全区速度比，越低越严重）\n"
        "- 危险区平均速度：{mean_velocity_danger_zone} m/s\n"
        "- 对向冲突次数：{conflict_count}\n"
        "- 出口通过率：{exit_pass_rate}\n"
        "- 平均危险滞留步数：{mean_dwell_time_danger}\n"
        "- 慢脑日志摘要：{log_excerpt}\n"
        "- 基准对比摘要：{causal_delta_excerpt}\n\n"
        "检索到的规范上下文：\n{context}\n"
    )
    chain = prompt | llm | StrOutputParser()
    raw = chain.invoke(
        {
            "scenario": metrics["scenario"],
            "mitigation_strategy": metrics["mitigation_strategy"],
            "baseline_peak_density": metrics["baseline_peak_density"],
            "frontend_peak_density": metrics["frontend_peak_density"],
            "summary_peak_density": metrics["summary_peak_density"],
            "slow_brain_trigger_count": metrics["slow_brain_trigger_count"],
            "current_risk_level": metrics["current_risk_level"],
            "velocity_decay_ratio": summary.get("velocity_decay_ratio", 1.0),
            "mean_velocity_danger_zone": summary.get("mean_velocity_danger_zone", 0.0),
            "conflict_count": summary.get("conflict_count", 0),
            "exit_pass_rate": f"{summary.get('exit_pass_rate', 0.0):.1%}",
            "mean_dwell_time_danger": summary.get("mean_dwell_time_danger", 0.0),
            "log_excerpt": metrics["log_excerpt"],
            "causal_delta_excerpt": metrics["causal_delta_excerpt"],
            "context": context,
        }
    )
    parsed = json.loads(raw)
    return {
        "abstract": str(parsed.get("abstract") or "待补充"),
        "mapping": str(parsed.get("mapping") or "待补充"),
        "interventions_raw": str(parsed.get("mapping") or ""),
    }


def _extract_simulation_metrics(simulation_logs: Sequence[dict[str, Any]] | dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(simulation_logs, str):
        try:
            payload = json.loads(simulation_logs)
        except json.JSONDecodeError:
            payload = {"raw": simulation_logs}
    else:
        payload = simulation_logs

    if isinstance(payload, dict):
        summary = payload.get("summary") or {}
        logs = payload.get("logs") or []
        baseline_summary = payload.get("baseline_summary") or {}
        baseline_logs = payload.get("baseline_logs") or []
        density_series = payload.get("density_series") or summary.get("peak_density_series") or []
        baseline_density_series = payload.get("baseline_density_series") or baseline_summary.get("peak_density_series") or []
        velocity_series = payload.get("velocity_series") or summary.get("velocity_series") or []
        risk_level_series = payload.get("risk_level_series") or summary.get("risk_level_series") or []
        return {
            "scenario": str(payload.get("scenario") or summary.get("scenario") or "unknown"),
            "mitigation_strategy": str(payload.get("mitigation_strategy") or summary.get("mitigation_strategy") or "未设置"),
            "baseline_peak_density": round(float(payload.get("baseline_peak_density") or baseline_summary.get("peak_density") or 0.0), 2),
            "frontend_peak_density": round(float(payload.get("frontend_peak_density") or summary.get("peak_density") or 0.0), 2),
            "summary_peak_density": round(float(summary.get("peak_density") or 0.0), 2),
            "deadlock_seconds": round(float(summary.get("dangerous_steps") or 0.0) * float(summary.get("density_sample_interval_seconds") or 0.5), 2),
            "slow_brain_trigger_count": int(summary.get("slow_brain_triggers") or len(logs)),
            "current_risk_level": str(payload.get("current_risk_level") or summary.get("final_risk_level") or "unknown"),
            "baseline_log_excerpt": _build_log_excerpt(baseline_logs, limit=6),
            "log_excerpt": _build_log_excerpt(logs, limit=8),
            "causal_delta_excerpt": _build_causal_delta_excerpt(baseline_logs, logs),
            "logs": logs,
            "density_series": [float(item) for item in density_series],
            "baseline_density_series": [float(item) for item in baseline_density_series],
            "density_sample_interval_seconds": float(summary.get("density_sample_interval_seconds") or 0.5),
            "velocity_series": [float(item) for item in velocity_series],
            "risk_level_series": [str(item) for item in risk_level_series],
            "summary": summary,
        }

    return {
        "scenario": "unknown",
        "mitigation_strategy": "未设置",
        "baseline_peak_density": 0.0,
        "frontend_peak_density": 0.0,
        "summary_peak_density": 0.0,
        "deadlock_seconds": 0.0,
        "slow_brain_trigger_count": 0,
        "current_risk_level": "unknown",
        "baseline_log_excerpt": "未提供基准环境日志。",
        "log_excerpt": "待补充",
        "causal_delta_excerpt": "待补充",
        "logs": [],
        "density_series": [],
        "baseline_density_series": [],
        "density_sample_interval_seconds": 0.5,
    }


def _format_docs(docs: Sequence[Any]) -> str:
    return "\n\n".join(
        f"[Chunk {doc.metadata.get('chunk_index', '?')}]\n{doc.page_content}" for doc in docs
    )


def _build_log_excerpt(logs: Sequence[dict[str, Any]], *, limit: int) -> str:
    excerpt_parts: list[str] = []
    for item in logs[:limit]:
        content = item.get("content", {})
        excerpt_parts.append(
            json.dumps(
                {
                    "agent_id": item.get("agent_id"),
                    "density": item.get("density"),
                    "profile": content.get("profile_label") or content.get("typology"),
                    "intention": content.get("intention"),
                    "dialogue": content.get("dialogue"),
                    "action": content.get("action"),
                    "heard_messages": content.get("heard_messages"),
                },
                ensure_ascii=False,
            )
        )
    return " | ".join(excerpt_parts)[:1600] or "本次推演未触发慢脑日志。"


def _build_causal_delta_excerpt(
    baseline_logs: Sequence[dict[str, Any]],
    mitigation_logs: Sequence[dict[str, Any]],
) -> str:
    baseline_help = sum(1 for item in baseline_logs if _text_contains_help((item.get("content") or {}).get("action", ""), (item.get("content") or {}).get("dialogue", "")))
    mitigation_help = sum(1 for item in mitigation_logs if _text_contains_help((item.get("content") or {}).get("action", ""), (item.get("content") or {}).get("dialogue", "")))
    baseline_push = sum(1 for item in baseline_logs if _text_contains_push((item.get("content") or {}).get("action", "")))
    mitigation_push = sum(1 for item in mitigation_logs if _text_contains_push((item.get("content") or {}).get("action", "")))
    return (
        f"基准环境中呼救/求助表述约 {baseline_help} 次、推挤/强行突破表述约 {baseline_push} 次；"
        f"当前方案中呼救/求助表述约 {mitigation_help} 次、推挤/强行突破表述约 {mitigation_push} 次。"
        "请据此判断干预是否削弱了局部失稳与呼救级联。"
    )


def _build_density_chart_markdown(
    series: Sequence[float],
    sample_interval_seconds: float,
    *,
    baseline_series: Sequence[float],
    safety_threshold: float,
) -> str:
    if not series:
        return "当前报告未收到峰值密度时间序列。"
    times = [index * sample_interval_seconds for index in range(len(series))]
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    ax.plot(times, series, color="#2b6ef2", linewidth=2.2, label="当前推演")
    if baseline_series:
        baseline_times = [index * sample_interval_seconds for index in range(len(baseline_series))]
        ax.plot(baseline_times, baseline_series, color="#8f5af7", linewidth=1.8, linestyle="--", label="基准环境")
    ax.axhline(safety_threshold, color="#d64f4f", linestyle="--", linewidth=1.4, label=f"安全阈值 {safety_threshold:.1f}")
    ax.set_title("仿真时间 - 人群峰值密度", fontsize=12)
    ax.set_xlabel("仿真时间 / s")
    ax.set_ylabel("峰值密度 / 人/m²")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.legend(frameon=False)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"![密度折线图](data:image/png;base64,{encoded})"


def _build_velocity_chart_markdown(
    velocity_series: Sequence[float],
    density_series: Sequence[float],
    sample_interval_seconds: float,
) -> str:
    if not velocity_series or not density_series:
        return "当前报告未收到速度时间序列。"
    times = [index * sample_interval_seconds for index in range(len(velocity_series))]
    fig, ax1 = plt.subplots(figsize=(10, 4.8), dpi=150)
    ax1.set_xlabel("仿真时间 / s")
    ax1.set_ylabel("平均速度 / m/s", color="#2b6ef2")
    ax1.plot(times, velocity_series, color="#2b6ef2", linewidth=2.0, label="平均速度")
    ax1.tick_params(axis="y", labelcolor="#2b6ef2")
    ax1.set_ylim(bottom=0.0)
    ax2 = ax1.twinx()
    density_times = [index * sample_interval_seconds for index in range(len(density_series))]
    ax2.set_ylabel("峰值密度 / 人/m²", color="#d64f4f")
    ax2.plot(density_times, density_series, color="#d64f4f", linewidth=1.8, linestyle="--", label="峰值密度")
    ax2.tick_params(axis="y", labelcolor="#d64f4f")
    ax1.set_title("速度-密度双轴演变图", fontsize=12)
    ax1.grid(True, linestyle=":", alpha=0.35)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"![速度-密度图](data:image/png;base64,{encoded})"


def _build_risk_timeline_markdown(
    risk_level_series: Sequence[str],
    sample_interval_seconds: float,
) -> str:
    if not risk_level_series:
        return "当前报告未收到风险等级时间序列。"
    risk_map = {"safe": 0, "warning": 1, "danger": 2, "fatal": 3}
    color_map = {"safe": "#4caf50", "warning": "#ff9800", "danger": "#f44336", "fatal": "#7b1fa2"}
    times = [index * sample_interval_seconds for index in range(len(risk_level_series))]
    colors = [color_map.get(r, "#999999") for r in risk_level_series]
    fig, ax = plt.subplots(figsize=(10, 2.5), dpi=150)
    for i in range(len(times) - 1):
        ax.barh(0, times[i + 1] - times[i], left=times[i], height=0.6, color=colors[i], edgecolor="none")
    ax.set_yticks([])
    ax.set_xlabel("仿真时间 / s")
    ax.set_title("风险等级时间线", fontsize=11)
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#4caf50", label="安全"),
        Patch(facecolor="#ff9800", label="警告"),
        Patch(facecolor="#f44336", label="危险"),
        Patch(facecolor="#7b1fa2", label="致命"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"![风险时间线](data:image/png;base64,{encoded})"


def _build_metrics_table(metrics: dict[str, Any]) -> str:
    summary = metrics.get("summary") or {}
    rt = summary.get("risk_transitions") or {}
    rows = [
        "| 指标 | 值 | 说明 |",
        "|---|---:|---|",
        f"| 实时涌现密度 | {metrics.get('frontend_peak_density', 0):.2f} 人/m² | 报告生成时右侧看板显示的实时密度 |",
        f"| 仿真峰值密度 | {summary.get('peak_density', 0):.2f} 人/m² | 模拟过程中观测到的最大局部密度 |",
        f"| 速度衰减比 | {summary.get('velocity_decay_ratio', 1.0):.3f} | 危险区/安全区速度比，越低衰减越严重 |",
        f"| 危险区平均速度 | {summary.get('mean_velocity_danger_zone', 0):.3f} m/s | 密度>=临界值区域的平均行走速度 |",
        f"| 平均危险滞留步数 | {summary.get('mean_dwell_time_danger', 0):.1f} 步 | 行人在危险密度下的平均滞留时间 |",
        f"| 对向冲突次数 | {summary.get('conflict_count', 0)} | 双向行人近距离相遇总次数 |",
        f"| 出口通过率 | {summary.get('exit_pass_rate', 0):.1%} | 成功离开通道的行人占比 |",
        f"| 总生成人数 | {summary.get('total_spawned', 0)} | 全程模拟中生成的行人总数 |",
        f"| 安全→警告 | {rt.get('safe_to_warning', 0)} 次 | 密度首次突破安全阈值 |",
        f"| 警告→危险 | {rt.get('warning_to_danger', 0)} 次 | 密度突破临界值 |",
        f"| 危险→致命 | {rt.get('danger_to_fatal', 0)} 次 | 密度突破致死阈值 |",
    ]
    return "\n".join(rows)


def _build_micro_behavior_table(logs: Sequence[dict[str, Any]]) -> str:
    if not logs:
        return "| Agent | 身份 | 密度 | 呼救/对话 | 最终动作 |\n|---|---|---:|---|---|\n| - | - | - | 未触发慢脑日志 | 待补充 |"
    scored = sorted(
        logs,
        key=lambda item: float(item.get("density") or 0.0),
        reverse=True,
    )[:5]
    rows = ["| Agent | 身份 | 密度 | 呼救/对话 | 最终动作 |", "|---|---|---:|---|---|"]
    for item in scored:
        content = item.get("content") or {}
        rows.append(
            "| {agent} | {profile} | {density:.2f} | {dialogue} | {action} |".format(
                agent=item.get("agent_id", "-"),
                profile=_escape_cell(content.get("profile_label") or content.get("typology") or "-"),
                density=float(item.get("density") or 0.0),
                dialogue=_escape_cell(content.get("dialogue") or content.get("perception") or "-"),
                action=_escape_cell(content.get("action") or "-"),
            )
        )
    return "\n".join(rows)


def _build_code_mapping_table(docs: Sequence[Any]) -> str:
    rows = ["| 规范片段 | 检索内容 | 对应整改方向 |", "|---|---|---|"]
    for doc in docs[:4]:
        text = " ".join(str(doc.page_content).split())
        excerpt = _escape_cell(text[:90] + ("..." if len(text) > 90 else ""))
        recommendation = _recommendation_from_excerpt(text)
        rows.append(
            f"| Chunk {doc.metadata.get('chunk_index', '?')} | {excerpt} | {recommendation} |"
        )
    return "\n".join(rows)


def _text_contains_help(*parts: str) -> bool:
    text = " ".join(parts)
    return any(keyword in text for keyword in ["救", "求助", "呼救", "帮", "help"])


def _text_contains_push(*parts: str) -> bool:
    text = " ".join(parts)
    return any(keyword in text for keyword in ["推", "挤", "冲", "撞", "扒开"])


def _recommendation_from_excerpt(text: str) -> str:
    if "净宽" in text or "疏散" in text:
        return "优先增加瓶颈净宽或削减对冲流量"
    if "分流" in text or "隔离" in text:
        return "优先采用中央护栏或单向导流"
    if "出口" in text:
        return "优先拓宽出口并保持出口前区连续可达"
    return "结合 RAG 条款继续校核走道连续性、净宽与人流组织"


def _escape_cell(value: Any) -> str:
    text = str(value or "-").replace("\n", " ").replace("|", "/")
    return text[:120] + ("..." if len(text) > 120 else "")

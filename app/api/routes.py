from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.schemas import (
    BootstrapResponse,
    EngineRunRequest,
    EngineRunResponse,
    ReportRequest,
    SimulationRequest,
    SimulationResponse,
)
from app.engine.rag import generate_diagnostic_report
from app.services.data_loader import load_fire_code_chunks, load_itaewon_parameters
from app.services.engine_runtime import engine_runtime_service
from app.services.simulation import simulation_service
from app.services.slow_brain import slow_brain_service

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@router.get("/bootstrap", response_model=BootstrapResponse)
async def bootstrap() -> BootstrapResponse:
    itaewon = load_itaewon_parameters()
    fire_code = load_fire_code_chunks()
    spatial_parameters = itaewon["spatial_parameters"]["parameters"]
    density_parameters = itaewon["density_parameters"]["parameters"]
    references = itaewon["references"][:3]
    density_by_id = {item["id"]: item for item in density_parameters}

    spatial_summary = {
        "core_size": spatial_parameters[0]["value"],
        "corridor_length": spatial_parameters[2]["value"],
        "grid_resolution": spatial_parameters[4]["value"],
    }
    density_summary = {
        "observed_peak_density": density_by_id["DP-002"]["value"],
        "fatal_range": density_by_id["DP-003"]["value"],
        "fatal_range_min": 12.0,
        "fatal_range_max": 16.0,
        "critical_density": density_by_id["DP-004"]["value"],
        "stampede_density": density_by_id["DP-005"]["value"],
        "safe_limit": density_by_id["DP-006"]["value"],
        "historical_core_agents": density_by_id["DP-001"]["value"],
    }
    simulation_limits = {
        # 修复：根据数据集DP-001：事故核心区域聚集人数=300人，提高上限到800
        "max_agents": max(800, int(density_by_id["DP-001"]["value"])),
        "arrival_rate_min": 0.1,
        # 修复：根据数据集FP-002：双向人流速率范围=1-8人/秒，提高上限到12
        "arrival_rate_max": 12.0,
        "duration_steps_min": 40,
        "duration_steps_max": 360,
    }
    rag_summary = [
        {
            "article": chunk["article"],
            "title": chunk["title"],
            "keywords": chunk["rag_keywords"][:3],
        }
        for chunk in fire_code["document_chunks"][:4]
    ]
    cross_validation_summary = [
        {
            "label": "论文对齐目标",
            "value": "16.4 人/平方米峰值",
            "detail": "来自事故参数 JSON 的核心区域观测峰值；致死密度参考区间为 12-16 人/平方米。",
        },
        {
            "label": "系统慢脑触发阈值",
            "value": "5 人/平方米",
            "detail": "局部 5x5 网格密度超过临界危险密度时，触发慢脑认知推理。",
        },
        {
            "label": "事故场景输入速率",
            "value": "2.5 + 2.5 人/秒",
            "detail": "使用梨泰院参数 JSON 中的事故场景 Spawner 配置。",
        },
        {
            "label": "巷道通行能力",
            "value": "约 1.5 人/秒",
            "detail": "来自文献解析报告，可用于判断当前输入是否超过瓶颈承载能力。",
        },
        {
            "label": "整改目标",
            "value": "< 4 人/平方米",
            "detail": "与文档第四幕的安全回归目标保持一致。",
        },
    ]

    return BootstrapResponse(
        app_name=settings.app_name,
        spatial_summary=spatial_summary,
        density_summary=density_summary,
        simulation_limits=simulation_limits,
        source_summary=references,
        scenarios=simulation_service.get_scenarios(),
        rag_summary=rag_summary,
        llm_provider_ready=slow_brain_service.provider_ready,
        llm_provider_name=slow_brain_service.provider_name,
        llm_model_name=settings.llm_model,
        cross_validation_summary=cross_validation_summary,
        engine_layout=engine_runtime_service.describe_layout(),
    )


@router.post("/simulate", response_model=SimulationResponse)
async def simulate(request: SimulationRequest) -> SimulationResponse:
    try:
        return await simulation_service.run(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/engine/run", response_model=EngineRunResponse)
async def run_engine(request: EngineRunRequest) -> EngineRunResponse:
    return await engine_runtime_service.run(request)


@router.post("/report")
async def report(payload: ReportRequest):
    logs_payload = [
        item.model_dump() if hasattr(item, "model_dump") else item.dict()
        for item in payload.logs
    ]
    summary_payload = None
    if payload.summary is not None:
        summary_payload = (
            payload.summary.model_dump()
            if hasattr(payload.summary, "model_dump")
            else payload.summary.dict()
        )
    baseline_summary_payload = None
    if payload.baseline_summary is not None:
        baseline_summary_payload = (
            payload.baseline_summary.model_dump()
            if hasattr(payload.baseline_summary, "model_dump")
            else payload.baseline_summary.dict()
        )
    baseline_logs_payload = [
        item.model_dump() if hasattr(item, "model_dump") else item.dict()
        for item in payload.baseline_logs
    ]
    try:
        result = generate_diagnostic_report(
            {
                "scenario": payload.scenario,
                "frontend_peak_density": payload.frontend_peak_density,
                "mitigation_strategy": payload.mitigation_strategy,
                "current_risk_level": payload.current_risk_level,
                "summary": summary_payload,
                "logs": logs_payload,
                "density_series": payload.density_series,
                "baseline_peak_density": payload.baseline_peak_density,
                "baseline_summary": baseline_summary_payload,
                "baseline_logs": baseline_logs_payload,
                "baseline_density_series": payload.baseline_density_series,
                "velocity_series": payload.velocity_series,
                "baseline_velocity_series": payload.baseline_velocity_series,
                "risk_level_series": payload.risk_level_series,
            }
        )
        return {
            "report": result.get("report_markdown", ""),
            "recommended_interventions": result.get("recommended_interventions", []),
            "default_intervention": result.get("default_intervention"),
            "comparison_targets": result.get("comparison_targets", {}),
        }
    except Exception as exc:
        return {
            "report": _build_degraded_report(
                payload=payload,
                summary_payload=summary_payload,
                logs_payload=logs_payload,
                error_message=str(exc),
            ),
            "recommended_interventions": [],
            "default_intervention": None,
            "comparison_targets": {},
            "degraded": True,
            "error": str(exc),
        }


@router.post("/report/pdf")
async def report_pdf(payload: ReportRequest):
    """Generate PDF version of the diagnostic report."""
    from fastapi.responses import Response

    from app.engine.pdf_export import markdown_to_pdf

    # First generate the report
    result = await report(payload)
    report_markdown = result.get("report", "")
    interventions = result.get("recommended_interventions", [])

    pdf_bytes = markdown_to_pdf(report_markdown, interventions)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=diagnostic_report.pdf"},
    )


def _build_degraded_report(
    *,
    payload: ReportRequest,
    summary_payload: dict | None,
    logs_payload: list[dict],
    error_message: str,
) -> str:
    peak_density = payload.frontend_peak_density
    summary_peak = None
    if summary_payload is not None:
        summary_peak = summary_payload.get("peak_density")
    trigger_count = len(logs_payload)
    representative_logs = logs_payload[:3]
    rows = ["| Agent | 密度 | 行为摘要 |", "|---|---:|---|"]
    for item in representative_logs:
        content = item.get("content") or {}
        rows.append(
            f"| {item.get('agent_id', '-')} | {float(item.get('density') or 0.0):.2f} | "
            f"{str(content.get('action') or content.get('dialogue') or '未触发显著动作').replace('|', '/')} |"
        )
    if len(rows) == 2:
        rows.append("| - | 0.00 | 当前低流量状态下未产生代表性慢脑日志 |")

    return "\n\n".join(
        [
            "# 城市街道人群拥堵诊断报告",
            "## 摘要",
            (
                f"本次推演的右侧实时仿真涌现密度为 **{peak_density:.2f} 人/m²**。"
                f"仿真全程峰值为 **{float(summary_peak or peak_density):.2f} 人/m²**，"
                f"慢脑日志记录数为 **{trigger_count}**。当前返回的是降级报告，"
                "说明 RAG 生成链路暂时不可用，但基础数据链路已经打通。"
            ),
            "## 典型微观行为表",
            "\n".join(rows),
            "## 规范映射与整改方案",
            (
                "- 建议优先检查疏散净宽、入口对冲和局部瓶颈区的导流组织。\n"
                "- 若当前为低流量状态，建议提高双端输入后再次生成正式 RAG 报告。\n"
                f"- 本次降级原因：`{error_message}`"
            ),
        ]
    )

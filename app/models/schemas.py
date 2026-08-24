from typing import Any, Literal

from pydantic import BaseModel, Field


ScenarioName = Literal["baseline", "accident", "mitigation"]
DistributionName = Literal["poisson", "uniform"]
MitigationStrategy = Literal["none", "central_guardrail", "one_way_flow", "widen_exits"]


class InterventionConfig(BaseModel):
    type: MitigationStrategy
    label: str | None = None
    reason: str | None = None
    expected_effect: str | None = None
    overlay_spec: dict[str, Any] = Field(default_factory=dict)
    simulation_params: dict[str, Any] = Field(default_factory=dict)


class ComparisonMetric(BaseModel):
    label: str
    before: str
    after: str | None = None
    delta: str | None = None


class SimulationRequest(BaseModel):
    scenario: ScenarioName = "accident"
    max_agents: int = Field(default=200, ge=20, le=800)
    duration_steps: int = Field(default=120, ge=40, le=360)
    use_api: bool = False
    random_seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    api_budget: int | None = Field(default=None, ge=1, le=256)
    arrival_rate_north: float | None = Field(default=None, ge=0.1, le=12.0)
    arrival_rate_south: float | None = Field(default=None, ge=0.1, le=12.0)
    mitigation_strategy: MitigationStrategy | None = None
    intervention: InterventionConfig | None = None
    normal_pedestrian_ratio: int = Field(default=60, ge=0, le=100)
    group_family_ratio: int = Field(default=25, ge=0, le=100)
    vulnerable_ratio: int = Field(default=15, ge=0, le=100)


class HeatCell(BaseModel):
    x: float
    y: float
    width: float
    height: float
    density: float
    level: str


class AgentState(BaseModel):
    id: int
    x: float
    y: float
    direction: Literal["east", "west"]
    risk: str
    slow_brain_active: bool
    typology: str = "normal_pedestrian"
    broadcast_radius: float = Field(default=2.4, gt=0.0)
    profile_label: str = "常态行人"
    perception_summary: str = "前方可通行。"
    emotion_summary: str = "保持警觉，情绪基本稳定。"
    intention_summary: str = "继续沿当前方向稳步前进。"
    action_summary: str = "跟随局部空隙缓慢移动。"


class FrameStats(BaseModel):
    step: int
    simulated_seconds: float
    active_agents: int
    average_density: float
    peak_density: float
    risk_level: str


class Frame(BaseModel):
    step: int
    heatmap: list[HeatCell]
    agents: list[AgentState]
    stats: FrameStats


class SlowBrainLog(BaseModel):
    step: int
    agent_id: int
    severity: str
    density: float
    content: dict[str, Any]


class ScenarioMetadata(BaseModel):
    name: ScenarioName
    label: str
    arrival_rate_north: float
    arrival_rate_south: float
    description: str


class BootstrapResponse(BaseModel):
    app_name: str
    spatial_summary: dict
    density_summary: dict
    simulation_limits: dict
    source_summary: list[dict]
    scenarios: list[ScenarioMetadata]
    rag_summary: list[dict]
    llm_provider_ready: bool
    llm_provider_name: str
    llm_model_name: str
    cross_validation_summary: list[dict]
    engine_layout: dict


class SimulationSummary(BaseModel):
    scenario: ScenarioName
    max_agents_seen: int
    peak_density: float
    average_peak_density: float
    peak_density_series: list[float] = Field(default_factory=list)
    density_sample_interval_seconds: float = Field(default=0.5, gt=0.0)
    slow_brain_triggers: int
    dangerous_steps: int
    final_risk_level: str
    arrival_rate_north: float
    arrival_rate_south: float
    literature_target_min: float
    literature_target_max: float
    density_gap_to_target: float
    vortex_detected: bool
    deadlock_risk_detected: bool
    api_calls_used: int
    combined_arrival_rate: float
    corridor_capacity: float
    overload_ratio: float
    fruin_level: str
    mitigation_strategy: MitigationStrategy | None = None

    # 多维评估指标
    mean_velocity_danger_zone: float = Field(default=0.0, description="危险区平均速度 m/s")
    mean_velocity_safe_zone: float = Field(default=0.0, description="安全区平均速度 m/s")
    velocity_decay_ratio: float = Field(default=1.0, description="速度衰减比(危险区/安全区)")
    mean_dwell_time_danger: float = Field(default=0.0, description="平均危险滞留步数")
    conflict_count: int = Field(default=0, description="对向冲突次数")
    exit_pass_rate: float = Field(default=0.0, description="出口通过率")
    total_spawned: int = Field(default=0, description="总生成人数")
    total_exited: int = Field(default=0, description="总退出人数")
    risk_transitions: dict[str, int] = Field(
        default_factory=lambda: {"safe_to_warning": 0, "warning_to_danger": 0, "danger_to_fatal": 0},
        description="风险等级转换次数",
    )
    velocity_series: list[float] = Field(default_factory=list, description="每步平均速度序列")
    risk_level_series: list[str] = Field(default_factory=list, description="每步风险等级序列")


class SimulationResponse(BaseModel):
    scenario: ScenarioName
    frames: list[Frame]
    logs: list[SlowBrainLog]
    summary: SimulationSummary


class ReportRequest(BaseModel):
    scenario: ScenarioName
    frontend_peak_density: float = Field(ge=0.0, le=30.0)
    mitigation_strategy: MitigationStrategy | None = None
    intervention: InterventionConfig | None = None
    current_risk_level: str | None = None
    summary: SimulationSummary | None = None
    logs: list[SlowBrainLog]
    density_series: list[float] = Field(default_factory=list)
    baseline_peak_density: float | None = Field(default=None, ge=0.0, le=30.0)
    baseline_summary: SimulationSummary | None = None
    baseline_logs: list[SlowBrainLog] = Field(default_factory=list)
    baseline_density_series: list[float] = Field(default_factory=list)
    velocity_series: list[float] = Field(default_factory=list)
    baseline_velocity_series: list[float] = Field(default_factory=list)
    risk_level_series: list[str] = Field(default_factory=list)


class EngineRunRequest(BaseModel):
    duration_steps: int = Field(default=30, ge=5, le=300)
    dt: float = Field(default=0.2, gt=0.01, le=2.0)
    arrival_rate_left: float = Field(default=2.5, ge=0.0, le=20.0)
    arrival_rate_right: float = Field(default=2.5, ge=0.0, le=20.0)
    distribution: DistributionName = "poisson"
    use_slow_brain: bool = True


class EngineLogPreview(BaseModel):
    step_index: int
    agent_id: int
    density: float
    action: str
    rationale: str


class EngineRunSummary(BaseModel):
    duration_steps: int
    dt: float
    peak_density: float
    max_local_density: float
    frozen_step_count: int
    slow_brain_request_total: int
    slow_brain_log_total: int
    total_spawned: int
    total_exited: int
    final_active_agents: int


class EngineRunResponse(BaseModel):
    summary: EngineRunSummary
    latest_logs: list[EngineLogPreview]


class ReportItem(BaseModel):
    title: str
    article: str
    reason: str
    recommendation: str


class ReportComparison(BaseModel):
    before_peak_density: float
    after_peak_density: float
    reduction_ratio: float
    verdict: str


class ReportResponse(BaseModel):
    scenario: ScenarioName
    title: str
    risk_statement: str
    findings: list[str]
    code_references: list[ReportItem]
    comparison: ReportComparison

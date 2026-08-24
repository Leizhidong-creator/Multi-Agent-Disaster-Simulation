from __future__ import annotations

import asyncio
import math
import random
import re
import time
from dataclasses import dataclass, field

import numpy as np

from app.core.config import settings
from app.models.schemas import (
    AgentState,
    Frame,
    FrameStats,
    HeatCell,
    ScenarioMetadata,
    SimulationRequest,
    SimulationResponse,
    SimulationSummary,
    SlowBrainLog,
)
from app.services.data_loader import load_itaewon_parameters
from app.services.slow_brain import slow_brain_service


@dataclass
class InternalAgent:
    agent_id: int
    x: float
    y: float
    direction: str
    target_x: float
    target_y: float
    preferred_offset_y: float = 0.0
    aggressiveness: float = 1.0
    turbulence: float = 0.0
    personal_space: float = 0.52
    vx: float = 0.0
    vy: float = 0.0
    sway_phase: float = 0.0
    cluster_bias: float = 0.0
    triggered: bool = False
    slow_brain_active: bool = False
    # UCY/ETH anchored base speed
    preferred_speed: float = 1.34
    # Agent Typology
    typology: str = "normal_pedestrian"
    group_id: int | None = None
    broadcast_radius: float = 2.4
    last_utterance: str = ""
    last_trigger_step: int = -999
    skill_force_x: float = 0.0
    skill_force_y: float = 0.0
    support_until_step: int = -999
    help_beacon_until_step: int = -999
    climbed_out: bool = False
    # 拥堵记忆与滞留追踪
    congestion_memory: float = 0.0
    stalled_steps: int = 0
    local_blocked: bool = False
    last_fast_summary: str = ""
    last_slow_summary: str = ""
    # 个性化画像
    profile_label: str = ""  # 例如：'年轻女性#42'
    # 向量化临时力缓存（每步计算后重置）
    _repulsion_x: float = 0.0
    _repulsion_y: float = 0.0
    _head_on_pressure: float = 0.0
    _shear_force: float = 0.0
    _compression_wave: float = 0.0
    _cohesion_force_x: float = 0.0
    _cohesion_force_y: float = 0.0
    _beacon_response_y: float = 0.0
    _give_space_drag: float = 0.0
    _queueing_brake: float = 0.0


class SimulationService:
    def __init__(self) -> None:
        self.parameters = load_itaewon_parameters()
        self.parameter_index = self._build_parameter_index()
        self.spawner_configs = {item["id"]: item for item in self.parameters["spawner_config"]["configs"]}

        self.length = self._param_float("SP-003", default=45.0)
        width_min, width_max = self._param_range("SP-004", default=(3.2, 6.0))
        self.narrow_width = min(width_min, width_max)
        self.max_width = max(width_min, width_max)
        core_length, core_width = self._param_range("SP-001", default=(5.7, 3.2))
        self.core_length = max(core_length, core_width)
        self.core_width = min(core_length, core_width)
        self.core_area = self._param_float("SP-002", default=18.24)
        self.grid_resolution = 0.2

        fatal_min, fatal_max = self._param_range("DP-003", default=(12.0, 16.0))
        self.observed_peak_density = self._param_float("DP-002", default=16.4)
        self.fatal_density_min = min(fatal_min, fatal_max)
        self.fatal_density_max = max(fatal_min, fatal_max)
        self.critical_density = self._param_float("DP-004", default=5.0)
        self.stampede_density = self._param_float("DP-005", default=7.0)
        self.safe_density_limit = self._param_float("DP-006", default=4.0)

        self.flow_rate_min, self.flow_rate_max = self._param_range("FP-002", default=(1.0, 8.0))
        free_speed_min, free_speed_max = self._param_range("VP-001", default=(1.2, 1.3))
        self.free_speed = round((free_speed_min + free_speed_max) / 2.0, 3)
        self.congested_speed = self._param_float("VP-002", default=0.3)
        self.stop_density_threshold = self._param_float("VP-003", default=5.4)

        self.agent_radius = max(
            0.12,
            min(
                0.18,
                math.sqrt(1.0 / (math.pi * max(self.observed_peak_density, 1e-6))),
            ),
        )
        self.min_arrival_rate = 0.1
        # 修复：根据数据集FP-002：双向人流速率范围=1-8人/秒，提高上限
        self.max_arrival_rate = max(8.0, self.flow_rate_max)
        self.center_x = self.length / 2.0
        self.delta_time = 0.5
        self.local_radius = 0.463
        self.grid_width = self.grid_resolution
        self.grid_height = self.grid_resolution
        self.max_abs_y = self.max_width / 2
        self.scenario_seed = {"baseline": 11, "accident": 22, "mitigation": 33}
        self.corridor_capacity = round(self.safe_density_limit * self.narrow_width * self.congested_speed, 2)
        self.throat_start_x = max(0.0, self.center_x - (self.core_length / 2.0))
        self.throat_end_x = min(self.length, self.center_x + (self.core_length / 2.0))
        transition_span = max(6.0, (self.length - self.core_length) * 0.22)
        self.funnel_start_x = max(0.0, self.throat_start_x - transition_span)
        self.funnel_end_x = min(self.length, self.throat_end_x + transition_span)
        self.central_barrier_start_x = max(0.0, self.throat_start_x - 3.0)
        self.central_barrier_end_x = min(self.length, self.throat_end_x + 3.0)
        self.central_barrier_half_width = 0.18
        self.spawn_cluster_centers = {
            "east": [self.max_abs_y - self.agent_radius - 0.22],
            "west": [-self.max_abs_y + self.agent_radius + 0.22],
        }
        self.current_combined_arrival = 0.0
        self.current_overload_ratio = 1.0
        self.current_max_agents = 0

    def _build_parameter_index(self) -> dict[str, dict]:
        index: dict[str, dict] = {}
        for section in self.parameters.values():
            if not isinstance(section, dict):
                continue
            for item in section.get("parameters", []):
                item_id = item.get("id")
                if item_id:
                    index[item_id] = item
        return index

    def _param_value(self, param_id: str, default):
        item = self.parameter_index.get(param_id)
        if item is None:
            return default
        return item.get("value", default)

    def _extract_numbers(self, value) -> list[float]:
        if isinstance(value, (int, float)):
            return [float(value)]
        if isinstance(value, str):
            return [float(match) for match in re.findall(r"\d+(?:\.\d+)?", value)]
        return []

    def _param_float(self, param_id: str, default: float) -> float:
        value = self._param_value(param_id, default)
        if isinstance(value, (int, float)):
            return float(value)
        numbers = self._extract_numbers(value)
        return float(numbers[0]) if numbers else float(default)

    def _param_range(self, param_id: str, default: tuple[float, float]) -> tuple[float, float]:
        value = self._param_value(param_id, default)
        numbers = self._extract_numbers(value)
        if not numbers:
            return default
        if len(numbers) == 1:
            return float(numbers[0]), float(numbers[0])
        ordered = sorted(float(item) for item in numbers[:2])
        return ordered[0], ordered[1]

    def get_scenarios(self) -> list[ScenarioMetadata]:
        return [
            ScenarioMetadata(
                name="baseline",
                label="基准环境测试 (Base Environment)",
                arrival_rate_north=self._clamp_arrival_rate(self.spawner_configs["SC-001"]["arrival_rate_north"]),
                arrival_rate_south=self._clamp_arrival_rate(self.spawner_configs["SC-001"]["arrival_rate_south"]),
                description="用于展示安全密度下的顺畅通行。",
            ),
            ScenarioMetadata(
                name="accident",
                label="边界灾害注入测试 (Hazard Injection)",
                arrival_rate_north=self._clamp_arrival_rate(self.spawner_configs["SC-003"]["arrival_rate_north"]),
                arrival_rate_south=self._clamp_arrival_rate(self.spawner_configs["SC-003"]["arrival_rate_south"]),
                description="使用文献锚定的人流速率，复现中心窄巷拥堵死锁过程。",
            ),
            ScenarioMetadata(
                name="mitigation",
                label="物理干预二次演算 (Mitigation Simulation)",
                arrival_rate_north=self._clamp_arrival_rate(self.spawner_configs["SC-003"]["arrival_rate_north"]),
                arrival_rate_south=self._clamp_arrival_rate(self.spawner_configs["SC-003"]["arrival_rate_south"]),
                description="保持同等客流并切换多样化物理干预，验证护栏、单向导流与拓宽出口的减灾效果。",
            ),
        ]

    async def run(self, request: SimulationRequest) -> SimulationResponse:
        scenarios = {item.name: item for item in self.get_scenarios()}
        scenario = scenarios[request.scenario]
        arrival_rate_north = self._clamp_arrival_rate(
            request.arrival_rate_north if request.arrival_rate_north is not None else scenario.arrival_rate_north
        )
        arrival_rate_south = self._clamp_arrival_rate(
            request.arrival_rate_south if request.arrival_rate_south is not None else scenario.arrival_rate_south
        )

        mitigation_strategy = request.mitigation_strategy or "none"
        self.current_combined_arrival = arrival_rate_north + arrival_rate_south
        self.current_overload_ratio = max(0.1, self.current_combined_arrival / max(self.corridor_capacity, 1e-6))
        self.current_max_agents = request.max_agents

        population_distribution = self._normalize_population_distribution(
            {
                "normal_pedestrian": request.normal_pedestrian_ratio,
                "group_family": request.group_family_ratio,
                "vulnerable": request.vulnerable_ratio,
            }
        )
        target_mix = self._build_population_targets(request.max_agents, population_distribution)
        spawned_mix = {"normal_pedestrian": 0, "group_family": 0, "vulnerable": 0}

        seed = request.random_seed if request.random_seed is not None else self.scenario_seed[request.scenario]
        rng = random.Random(seed)
        agents: list[InternalAgent] = []
        logs: list[SlowBrainLog] = []
        frames: list[Frame] = []
        peak_values: list[float] = []
        dangerous_steps = 0
        vortex_steps = 0
        deadlock_steps = 0
        api_calls_used = 0
        api_budget_limit = request.api_budget if request.api_budget is not None else 1_000_000
        max_agents_seen = 0
        north_budget = 0.0
        south_budget = 0.0
        velocity_in_danger_zone: list[float] = []
        velocity_in_safe_zone: list[float] = []
        dwell_steps_per_agent: dict[int, int] = {}
        conflict_count = 0
        total_spawned = 0
        total_exited = 0
        risk_transitions: dict[str, int] = {"safe_to_warning": 0, "warning_to_danger": 0, "danger_to_fatal": 0}
        previous_risk_level = "safe"
        velocity_series: list[float] = []
        risk_level_series: list[str] = []
        # 热力图降频缓存：每3步算一次，中间复用
        _heatmap_cache: tuple[list[HeatCell], float, float] | None = None
        # LLM 总时间预算：超过后自动降级为本地模式，避免推演被慢 API 卡死
        _llm_time_budget = 30.0  # 秒
        _llm_time_used = 0.0
        _llm_disabled = False

        for step in range(request.duration_steps):
            north_budget += arrival_rate_north * self.delta_time
            south_budget += arrival_rate_south * self.delta_time
            active_capacity = max(0, request.max_agents - len(agents))
            if active_capacity <= 0:
                north_spawn_count = 0
                south_spawn_count = 0
            else:
                north_spawn_count = min(
                    active_capacity,
                    self._sample_spawn_count(
                        north_budget,
                        rng,
                        request.scenario,
                        step,
                        "east",
                    ),
                )
                north_budget = max(0.0, north_budget - north_spawn_count)
                active_capacity -= north_spawn_count

                if mitigation_strategy == "one_way_flow" and request.scenario == "mitigation":
                    south_spawn_count = 0
                else:
                    south_spawn_count = min(
                        active_capacity,
                        self._sample_spawn_count(
                            south_budget,
                            rng,
                            request.scenario,
                            step,
                            "west",
                        ),
                    )
                    south_budget = max(0.0, south_budget - south_spawn_count)

            self._spawn_side(
                north_spawn_count,
                "east",
                rng,
                request.scenario,
                agents,
                target_mix,
                spawned_mix,
            )
            self._spawn_side(
                south_spawn_count,
                "west",
                rng,
                request.scenario,
                agents,
                target_mix,
                spawned_mix,
            )

            local_densities = self._compute_local_densities(agents, request.scenario, mitigation_strategy)
            # 快慢双脑协同：密度超过阈值时冻结时间，自动触发慢脑LLM推理
            # 慢脑决策通过关键词映射到底层动作，影响当前步的Agent移动
            _effective_use_api = request.use_api and not _llm_disabled
            _step_start = time.monotonic()
            api_calls_used += await self._trigger_slow_brain(
                agents=agents,
                densities=local_densities,
                logs=logs,
                step=step,
                scenario=request.scenario,
                use_api=_effective_use_api,
                remaining_api_budget=max(0, api_budget_limit - api_calls_used),
                mitigation_strategy=mitigation_strategy,
            )
            _llm_time_used += time.monotonic() - _step_start
            if _llm_time_used > _llm_time_budget and not _llm_disabled:
                _llm_disabled = True
            self._update_agents(agents, local_densities, request.scenario, mitigation_strategy, rng, step)

            # Track exits before filtering
            total_spawned += north_spawn_count + south_spawn_count
            agents_before_count = len(agents)
            # 移除到达出口边界或已标记退出的Agent
            agents = [agent for agent in agents if not agent.climbed_out and 0.0 <= agent.x <= self.length]
            total_exited += agents_before_count - len(agents)

            # 每3步重新计算热力图，中间帧复用缓存
            if _heatmap_cache is None or step % 3 == 0:
                _heatmap_cache = self._compute_heatmap(agents, request.scenario, mitigation_strategy)
            heatmap, average_density, peak_density = _heatmap_cache
            vortex_detected = self._detect_vortex(agents)
            deadlock_detected = self._detect_deadlock(agents, local_densities)
            risk_level = self._risk_level(peak_density)
            if risk_level in {"warning", "danger", "fatal"}:
                dangerous_steps += 1
            if vortex_detected:
                vortex_steps += 1
            if deadlock_detected:
                deadlock_steps += 1
            peak_values.append(peak_density)
            max_agents_seen = max(max_agents_seen, len(agents))

            # --- Collect multi-dimensional metrics ---
            step_speeds: list[float] = []
            for agent in agents:
                d, _ = local_densities.get(agent.agent_id, (0.0, 0))
                agent_speed = math.hypot(agent.vx, agent.vy) / self.delta_time
                step_speeds.append(agent_speed)
                if d >= self.critical_density:
                    velocity_in_danger_zone.append(agent_speed)
                    dwell_steps_per_agent[agent.agent_id] = dwell_steps_per_agent.get(agent.agent_id, 0) + 1
                elif d < self.safe_density_limit:
                    velocity_in_safe_zone.append(agent_speed)
            mean_step_velocity = sum(step_speeds) / max(len(step_speeds), 1)
            velocity_series.append(round(mean_step_velocity, 3))
            risk_level_series.append(risk_level)

            # 向量化冲突检测：对向 agent 距离 < 0.5m
            if len(agents) > 1:
                _dirs = np.array([0 if a.direction == "east" else 1 for a in agents], dtype=np.int8)
                _xs = np.array([a.x for a in agents], dtype=np.float64)
                _ys = np.array([a.y for a in agents], dtype=np.float64)
                _opp = _dirs[:, None] != _dirs[None, :]
                _dist = np.hypot(_xs[:, None] - _xs[None, :], _ys[:, None] - _ys[None, :])
                np.fill_diagonal(_dist, np.inf)
                conflict_count += int(np.sum(_opp & (_dist < 0.5))) // 2

            if previous_risk_level != risk_level:
                trans_key = f"{previous_risk_level}_to_{risk_level}"
                if trans_key in risk_transitions:
                    risk_transitions[trans_key] += 1
            previous_risk_level = risk_level

            frames.append(
                Frame(
                    step=step,
                    heatmap=heatmap,
                    agents=[self._to_agent_state(agent, local_densities.get(agent.agent_id, (0.0, 0))[0]) for agent in agents],
                    stats=FrameStats(
                        step=step,
                        simulated_seconds=round((step + 1) * self.delta_time, 1),
                        active_agents=len(agents),
                        average_density=round(average_density, 2),
                        peak_density=round(peak_density, 2),
                        risk_level=risk_level,
                    ),
                )
            )

        mean_v_danger = (sum(velocity_in_danger_zone) / len(velocity_in_danger_zone)) if velocity_in_danger_zone else 0.0
        mean_v_safe = (sum(velocity_in_safe_zone) / len(velocity_in_safe_zone)) if velocity_in_safe_zone else 0.0
        velocity_decay = (mean_v_danger / mean_v_safe) if mean_v_safe > 0.01 else 0.0
        mean_dwell = (sum(dwell_steps_per_agent.values()) / len(dwell_steps_per_agent)) if dwell_steps_per_agent else 0.0
        exit_rate = (total_exited / total_spawned) if total_spawned > 0 else 0.0

        summary = SimulationSummary(
            scenario=request.scenario,
            max_agents_seen=max_agents_seen,
            peak_density=round(max(peak_values, default=0.0), 2),
            average_peak_density=round(sum(peak_values) / max(len(peak_values), 1), 2),
            peak_density_series=[round(value, 2) for value in peak_values],
            density_sample_interval_seconds=self.delta_time,
            slow_brain_triggers=len(logs),
            dangerous_steps=dangerous_steps,
            final_risk_level=frames[-1].stats.risk_level if frames else "safe",
            arrival_rate_north=round(arrival_rate_north, 2),
            arrival_rate_south=round(arrival_rate_south, 2),
            literature_target_min=self.fatal_density_min,
            literature_target_max=self.fatal_density_max,
            density_gap_to_target=round(max(0.0, self.fatal_density_min - max(peak_values, default=0.0)), 2),
            vortex_detected=vortex_steps > 0,
            deadlock_risk_detected=deadlock_steps > 0,
            api_calls_used=api_calls_used,
            combined_arrival_rate=round(arrival_rate_north + arrival_rate_south, 2),
            corridor_capacity=self.corridor_capacity,
            overload_ratio=round((arrival_rate_north + arrival_rate_south) / self.corridor_capacity, 2),
            fruin_level=self._fruin_level(max(peak_values, default=0.0)),
            mitigation_strategy=mitigation_strategy,
            mean_velocity_danger_zone=round(mean_v_danger, 3),
            mean_velocity_safe_zone=round(mean_v_safe, 3),
            velocity_decay_ratio=round(velocity_decay, 3),
            mean_dwell_time_danger=round(mean_dwell, 2),
            conflict_count=conflict_count,
            exit_pass_rate=round(exit_rate, 3),
            total_spawned=total_spawned,
            total_exited=total_exited,
            risk_transitions=risk_transitions,
            velocity_series=velocity_series,
            risk_level_series=risk_level_series,
        )

        return SimulationResponse(
            scenario=request.scenario,
            frames=frames,
            logs=logs,
            summary=summary,
        )

    def _spawn_side(
        self,
        count: int,
        direction: str,
        rng: random.Random,
        scenario: str,
        agents: list[InternalAgent],
        target_mix: dict[str, int],
        spawned_mix: dict[str, int],
    ) -> None:
        remaining = count
        while remaining > 0:
            typology = self._choose_typology(rng, remaining, target_mix, spawned_mix)
            group_quota_left = max(0, target_mix["group_family"] - spawned_mix["group_family"])
            if typology == "group_family" and remaining >= 2 and group_quota_left >= 2:
                group_remaining = group_quota_left
                group_size = min(remaining, min(4, group_remaining))
                group_id = rng.randint(1, 999999)
            else:
                typology = "normal_pedestrian" if typology == "group_family" else typology
                group_size = 1
                group_id = None

            base_agent = self._spawn_agent(
                self._get_next_id(agents),
                direction,
                rng,
                scenario,
                agents,
                typology,
            )
            if not base_agent:
                break

            if group_id is not None:
                base_agent.group_id = group_id

            agents.append(base_agent)
            spawned_mix[base_agent.typology] += 1
            remaining -= 1

            for _ in range(group_size - 1):
                member = self._spawn_agent(
                    self._get_next_id(agents),
                    direction,
                    rng,
                    scenario,
                    agents,
                    "group_family",
                )
                if member:
                    if group_id is not None:
                        member.group_id = group_id
                        member.x = base_agent.x + rng.uniform(-0.3, 0.3)
                        member.y = base_agent.y + rng.uniform(-0.3, 0.3)
                    agents.append(member)
                    spawned_mix[member.typology] += 1
                    remaining -= 1
                else:
                    break

    def _get_next_id(self, agents: list[InternalAgent]) -> int:
        return max([a.agent_id for a in agents], default=0) + 1

    def _spawn_agent(
        self,
        agent_id: int,
        direction: str,
        rng: random.Random,
        scenario: str,
        agents: list[InternalAgent],
        typology: str,
    ) -> InternalAgent | None:
        spawn_x, spawn_y = self._sample_spawn_point(direction, rng, scenario, agents)
        if spawn_x is None or spawn_y is None:
            return None

        aggressiveness = rng.uniform(0.88, 1.18) if scenario != "baseline" else rng.uniform(0.94, 1.08)
        turbulence = rng.uniform(0.04, 0.14) if scenario == "accident" else rng.uniform(0.01, 0.08)
        preferred_offset_y = rng.uniform(-0.55, 0.55) if scenario == "accident" else rng.uniform(-0.3, 0.3)
        target_band = self._target_band(direction, scenario, rng)
        sway_phase = rng.uniform(0.0, math.tau)
        cluster_bias = rng.uniform(-0.22, 0.22) if scenario == "accident" else rng.uniform(-0.12, 0.12)
        preferred_speed = self._preferred_speed_for_typology(rng, typology)
        broadcast_radius = self._broadcast_radius_for_typology(typology)
        profile_label = self._generate_profile_label(typology, agent_id, rng)

        if typology == "group_family":
            aggressiveness *= 0.9
            preferred_offset_y *= 0.8
        elif typology == "vulnerable":
            aggressiveness *= 0.78
            turbulence += 0.06
            cluster_bias *= 0.5

        if direction == "east":
            return InternalAgent(
                agent_id=agent_id,
                x=spawn_x,
                y=spawn_y,
                direction=direction,
                target_x=self.length + 1.0,
                target_y=target_band,
                preferred_offset_y=preferred_offset_y,
                aggressiveness=aggressiveness,
                turbulence=turbulence,
                personal_space=rng.uniform(self.agent_radius * 1.8, self.agent_radius * 2.5),
                sway_phase=sway_phase,
                cluster_bias=cluster_bias,
                preferred_speed=preferred_speed,
                typology=typology,
                broadcast_radius=broadcast_radius,
                profile_label=profile_label,
            )
        return InternalAgent(
            agent_id=agent_id,
            x=spawn_x,
            y=spawn_y,
            direction=direction,
            target_x=-1.0,
            target_y=target_band,
            preferred_offset_y=preferred_offset_y,
            aggressiveness=aggressiveness,
            turbulence=turbulence,
            personal_space=rng.uniform(self.agent_radius * 1.8, self.agent_radius * 2.5),
            sway_phase=sway_phase,
            cluster_bias=cluster_bias,
            preferred_speed=preferred_speed,
            typology=typology,
            broadcast_radius=broadcast_radius,
            profile_label=profile_label,
        )

    def _generate_profile_label(self, typology: str, agent_id: int, rng: random.Random) -> str:
        """生成个性化Agent标签，例如：'年轻女性#42'"""
        age_groups = ["年轻", "中年", "老年"]
        if typology == "normal_pedestrian":
            genders = ["女性", "男性"]
            age = rng.choices(age_groups, weights=[0.4, 0.4, 0.2], k=1)[0]
            gender = rng.choice(genders)
            return f"{age}{gender}#{agent_id}"
        elif typology == "group_family":
            group_types = ["情侣", "家庭", "朋友"]
            group = rng.choices(group_types, weights=[0.3, 0.4, 0.3], k=1)[0]
            return f"{group}群体#{agent_id}"
        elif typology == "vulnerable":
            vulnerable_types = [" elderly老人", "行动不便者", "带小孩的家长"]
            vuln_type = rng.choices(vulnerable_types, weights=[0.5, 0.3, 0.2], k=1)[0]
            return f"{vuln_type.strip()}#{agent_id}"
        return f"行人#{agent_id}"

    def _normalize_population_distribution(self, requested: dict[str, int]) -> dict[str, float]:
        cleaned = {
            "normal_pedestrian": max(0, int(requested.get("normal_pedestrian", 0))),
            "group_family": max(0, int(requested.get("group_family", 0))),
            "vulnerable": max(0, int(requested.get("vulnerable", 0))),
        }
        total = sum(cleaned.values())
        if total <= 0:
            return {
                "normal_pedestrian": 0.6,
                "group_family": 0.25,
                "vulnerable": 0.15,
            }
        return {key: value / total for key, value in cleaned.items()}

    def _build_population_targets(self, max_agents: int, distribution: dict[str, float]) -> dict[str, int]:
        targets = {
            key: int(round(max_agents * ratio))
            for key, ratio in distribution.items()
        }
        diff = max_agents - sum(targets.values())
        order = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
        idx = 0
        while diff != 0 and order:
            key = order[idx % len(order)][0]
            if diff > 0:
                targets[key] += 1
                diff -= 1
            elif targets[key] > 0:
                targets[key] -= 1
                diff += 1
            idx += 1
        return targets

    def _choose_typology(
        self,
        rng: random.Random,
        remaining: int,
        target_mix: dict[str, int],
        spawned_mix: dict[str, int],
    ) -> str:
        remaining_mix = {
            key: max(0, target_mix[key] - spawned_mix[key])
            for key in target_mix
        }
        if remaining < 2:
            remaining_mix["group_family"] = 0
        weighted: list[str] = []
        for key, value in remaining_mix.items():
            weighted.extend([key] * value)
        if not weighted:
            return "normal_pedestrian"
        return rng.choice(weighted)

    def _preferred_speed_for_typology(self, rng: random.Random, typology: str) -> float:
        if typology == "vulnerable":
            return max(0.35, rng.gauss(self.free_speed * 0.68, 0.12))
        if typology == "group_family":
            return max(0.55, rng.gauss(self.free_speed * 0.84, 0.12))
        return max(0.72, rng.gauss(self.free_speed, 0.14))

    def _clamp_arrival_rate(self, value: float | int) -> float:
        return round(max(self.min_arrival_rate, min(self.max_arrival_rate, float(value))), 2)

    def _overload_blend(self) -> float:
        return max(0.0, min(1.0, (self.current_overload_ratio - 1.0) / 1.5))

    def _core_pressure_blend(self, x_value: float, scenario: str, mitigation_strategy: str | None = None) -> float:
        if scenario != "accident":
            return 0.0
        if mitigation_strategy and mitigation_strategy != "none":
            return 0.0
        overload = self._overload_blend()
        if overload <= 0.0:
            return 0.0
        if self.throat_start_x <= x_value <= self.throat_end_x:
            return overload
        if self.funnel_start_x <= x_value <= self.funnel_end_x:
            return overload * 0.6
        return 0.0

    def _broadcast_radius_for_typology(self, typology: str) -> float:
        if typology == "vulnerable":
            return 2.8
        if typology == "group_family":
            return 2.5
        return 2.2

    def _profile_label(self, typology: str) -> str:
        mapping = {
            "normal_pedestrian": "常态行人",
            "group_family": "结伴群体",
            "vulnerable": "弱势群体",
        }
        return mapping.get(typology, "未知画像")

    def _can_spawn(self, agents: list[InternalAgent], x_anchor: float, y_anchor: float) -> bool:
        for agent in agents:
            if math.dist((agent.x, agent.y), (x_anchor, y_anchor)) < max(self.agent_radius * 2.08, agent.personal_space * 0.82):
                return False
        return True

    def _barrier_active(self, mitigation_strategy: str | None) -> bool:
        return mitigation_strategy == "central_guardrail"

    def _widen_exits_active(self, mitigation_strategy: str | None) -> bool:
        return mitigation_strategy == "widen_exits"

    def _within_barrier_segment(self, x_value: float) -> bool:
        return self.central_barrier_start_x <= x_value <= self.central_barrier_end_x

    def _barrier_bounds(self, direction: str) -> tuple[float, float]:
        if direction == "east":
            return self.central_barrier_half_width, self.max_abs_y
        return -self.max_abs_y, -self.central_barrier_half_width

    def _collect_heard_messages(self, source: InternalAgent, agents: list[InternalAgent]) -> list[str]:
        heard: list[str] = []
        for other in agents:
            if other.agent_id == source.agent_id or not other.last_utterance:
                continue
            distance = math.dist((source.x, source.y), (other.x, other.y))
            if distance > source.broadcast_radius:
                continue
            side = "左侧" if other.y < source.y else "右侧"
            tone = "高优先级呼救" if other.help_beacon_until_step >= other.last_trigger_step else "呼喊"
            other_profile = other.profile_label if other.profile_label else self._profile_label(other.typology)
            heard.append(f"{side} {other_profile}（{self._profile_label(other.typology)}）{tone}「{other.last_utterance}」")
        return heard[:4]

    def _compute_local_densities(self, agents: list[InternalAgent], scenario: str, mitigation_strategy: str = None) -> dict[int, tuple[float, int]]:
        del scenario, mitigation_strategy
        densities: dict[int, tuple[float, int]] = {}
        area = math.pi * (self.local_radius**2)
        if not agents:
            return densities

        # 空间分桶优化：将Agent按网格分桶，只对相邻桶做距离计算
        bucket_size = max(self.local_radius * 2, 2.0)
        buckets: dict[tuple[int, int], list[InternalAgent]] = {}
        for agent in agents:
            bx = int(agent.x // bucket_size)
            by = int(agent.y // bucket_size)
            key = (bx, by)
            if key not in buckets:
                buckets[key] = []
            buckets[key].append(agent)

        for agent in agents:
            bx = int(agent.x // bucket_size)
            by = int(agent.y // bucket_size)
            neighbor_count = 0
            # 只检查当前桶和相邻8个桶
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for other in buckets.get((bx + dx, by + dy), []):
                        if other.agent_id != agent.agent_id:
                            distance = math.dist((agent.x, agent.y), (other.x, other.y))
                            if distance <= self.local_radius:
                                neighbor_count += 1
            density_val = neighbor_count / area
            densities[agent.agent_id] = (density_val, neighbor_count)
        return densities

    def _compute_interaction_forces_vectorized(
        self,
        agents: list[InternalAgent],
        scenario: str,
        mitigation_strategy: str | None,
        step: int,
        densities: dict[int, tuple[float, int]],
    ) -> None:
        """用 numpy 广播一次性计算所有 agent 间的交互力，替代 O(n²) 纯 Python 循环。"""
        n = len(agents)
        if n <= 1:
            for a in agents:
                a._repulsion_x = a._repulsion_y = 0.0
                a._head_on_pressure = a._shear_force = a._compression_wave = 0.0
                a._cohesion_force_x = a._cohesion_force_y = 0.0
                a._beacon_response_y = a._give_space_drag = a._queueing_brake = 0.0
            return

        # 提取属性为 numpy 数组
        xs = np.array([a.x for a in agents], dtype=np.float64)
        ys = np.array([a.y for a in agents], dtype=np.float64)
        dirs = np.array([0 if a.direction == "east" else 1 for a in agents], dtype=np.int8)
        pspace = np.array([a.personal_space for a in agents], dtype=np.float64)
        vtypo = np.array([0 if a.typology == "normal_pedestrian" else (1 if a.typology == "group_family" else 2) for a in agents], dtype=np.int8)
        gids = np.array([a.group_id if a.group_id is not None else -1 for a in agents], dtype=np.int64)
        brad = np.array([a.broadcast_radius for a in agents], dtype=np.float64)
        hbeacon = np.array([a.help_beacon_until_step for a in agents], dtype=np.int32)
        supstep = np.array([a.support_until_step for a in agents], dtype=np.int32)
        same_dir = (dirs[:, None] == dirs[None, :])
        same_group_full = (vtypo[:, None] == 1) & (gids[:, None] == gids[None, :]) & (gids[:, None] != -1)

        # 计算核心区域压力混合值
        avg_x = (xs[:, None] + xs[None, :]) * 0.5
        pressure_blend = np.zeros((n, n), dtype=np.float64)
        if scenario == "accident" and (not mitigation_strategy or mitigation_strategy == "none"):
            overload = self._overload_blend()
            if overload > 0.0:
                in_throat = (avg_x >= self.throat_start_x) & (avg_x <= self.throat_end_x)
                in_funnel = (avg_x >= self.funnel_start_x) & (avg_x <= self.funnel_end_x)
                pressure_blend[in_throat] = overload
                pressure_blend[in_funnel & ~in_throat] = overload * 0.6

        # 距离矩阵
        dx = xs[:, None] - xs[None, :]
        dy = ys[:, None] - ys[None, :]
        dist = np.hypot(dx, dy)
        np.fill_diagonal(dist, np.inf)

        # 交互半径
        pspace_i = pspace[:, None]
        pspace_j = pspace[None, :]
        interact_r = np.maximum(pspace_i, pspace_j) + (0.62 - 0.16 * pressure_blend)
        close_mask = (dist > 0.01) & (dist < interact_r)

        # --- 斥力 ---
        safe_dist = np.maximum(dist, 1e-9)
        pressure = np.maximum(0.0, interact_r - dist)
        dweight = np.where(same_dir, 0.26, 0.56)
        pressure = np.where(same_group_full, pressure * 0.4, pressure)
        pressure = np.where((supstep[:, None] >= step) & same_group_full, pressure * 0.28, pressure)
        vuln_i = (vtypo[:, None] == 2)
        pressure = np.where(vuln_i, pressure * 1.18, pressure)

        rep_x = np.where(close_mask, (dx / safe_dist) * pressure * dweight, 0.0)
        lat_w = 0.28 + np.abs(dy) * 0.1
        lat_w = np.where(vtypo[:, None] == 2, lat_w * 1.35, lat_w)
        rep_y = np.where(close_mask, (dy / safe_dist) * pressure * lat_w, 0.0)

        # --- 对向交互：对向压力、剪切力、压缩波 ---
        opp_mask = ~same_dir
        opp_close = opp_mask & (np.abs(dx) < 1.5) & (np.abs(dy) < 1.0)
        head_on = np.where(opp_close, 0.18 + np.maximum(0.0, 1.0 - dist) * 0.15, 0.0)
        shear = np.where(close_mask & opp_mask, (-dy / safe_dist) * pressure * 0.22, 0.0)
        shear = np.where(opp_close, shear + np.where(ys[:, None] >= ys[None, :], 0.16, -0.16) * np.maximum(0.0, 1.1 - dist), shear)
        comp_wave = np.where(close_mask & opp_mask, np.maximum(0.0, 1.0 - dist) * 0.22, 0.0)

        # --- 排队制动（同向、前方近距离） ---
        same_dir_close = same_dir & (dist > 0) & (dist < np.inf)
        forward_gap = np.where(dirs[:, None] == 0, xs[None, :] - xs[:, None], xs[:, None] - xs[None, :])
        same_lane = np.abs(dy) < (0.18 * 2.2)  # agent_radius ≈ 0.18
        qbrake = np.where(same_dir_close & (forward_gap > 0) & (forward_gap < 0.72) & same_lane, (0.72 - forward_gap) * 1.15, 0.0)

        # --- 群体凝聚力 ---
        group_coh_mask = same_group_full & (dist > 0.4)
        coh_x = np.where(group_coh_mask, (-dx / safe_dist) * 0.08, 0.0)
        coh_y = np.where(group_coh_mask, (-dy / safe_dist) * 0.08, 0.0)

        # --- 求救信标响应 ---
        beacon_active = hbeacon[None, :] >= step
        beacon_dist_mask = dist < np.maximum(1.0, brad[:, None])
        beacon_mask = beacon_active & beacon_dist_mask
        beacon_y_shift = np.where(ys[:, None] >= ys[None, :], 0.14, -0.14)
        beacon_y_shift = np.where(vtypo[:, None] == 2, beacon_y_shift * 1.2, beacon_y_shift)
        beacon_y_shift = np.where(vtypo[:, None] == 1, beacon_y_shift * 0.8, beacon_y_shift)
        gspace = np.broadcast_to(np.where(vtypo[:, None] == 2, 0.07, 0.05), (n, n))

        # 信标相关力：只对激活的信标邻居求和
        beacon_shift_sum = np.where(beacon_mask, beacon_y_shift, 0.0).sum(axis=1)
        beacon_drag_sum = np.where(beacon_mask, gspace, 0.0).sum(axis=1)

        # 沿 axis=1 求和得到每个 agent 的合力
        for i, agent in enumerate(agents):
            agent._repulsion_x = float(rep_x[i].sum())
            agent._repulsion_y = float(rep_y[i].sum())
            agent._head_on_pressure = float(head_on[i].sum())
            agent._shear_force = float(shear[i].sum())
            agent._compression_wave = float(comp_wave[i].sum())
            agent._cohesion_force_x = float(coh_x[i].sum())
            agent._cohesion_force_y = float(coh_y[i].sum())
            agent._beacon_response_y = float(beacon_shift_sum[i])
            agent._give_space_drag = float(beacon_drag_sum[i])
            agent._queueing_brake = float(qbrake[i].sum())

    def _resolve_collisions_vectorized(
        self,
        agents: list[InternalAgent],
        scenario: str,
        mitigation_strategy: str | None,
        previous_positions: dict[int, tuple[float, float]],
    ) -> None:
        """用 numpy 向量化碰撞检测与解算，替代纯 Python 双重循环。"""
        n = len(agents)
        if n <= 1:
            if scenario == "mitigation":
                self._resolve_intervention_collisions(agents, mitigation_strategy)
            return

        xs = np.array([a.x for a in agents], dtype=np.float64)
        ys = np.array([a.y for a in agents], dtype=np.float64)

        # 预计算压力混合值
        avg_x_matrix = (xs[:, None] + xs[None, :]) * 0.5
        pressure_blend = np.zeros((n, n), dtype=np.float64)
        if scenario == "accident" and (not mitigation_strategy or mitigation_strategy == "none"):
            overload = self._overload_blend()
            if overload > 0.0:
                in_throat = (avg_x_matrix >= self.throat_start_x) & (avg_x_matrix <= self.throat_end_x)
                in_funnel = (avg_x_matrix >= self.funnel_start_x) & (avg_x_matrix <= self.funnel_end_x)
                pressure_blend[in_throat] = overload
                pressure_blend[in_funnel & ~in_throat] = overload * 0.6

        # 第一轮：重叠解算（最多4轮迭代）
        for _ in range(4):
            dx = xs[:, None] - xs[None, :]
            dy = ys[:, None] - ys[None, :]
            dist = np.hypot(dx, dy)
            np.fill_diagonal(dist, np.inf)

            min_dist = self.agent_radius * (2.02 - 0.62 * pressure_blend)
            overlap = min_dist - dist
            overlap_mask = (dist < min_dist)

            if not overlap_mask.any():
                break

            # 处理零距离
            zero_mask = dist < 1e-6
            if zero_mask.any():
                ids = np.array([a.agent_id for a in agents])
                even_mask = (ids[:, None] + ids[None, :]) % 2 == 0
                dx = np.where(zero_mask & (dist < 1e-6), np.where(even_mask, 1.0, -1.0), dx)
                dy = np.where(zero_mask & (dist < 1e-6), np.where(ids[:, None] % 2 == 0, 0.2, -0.2), dy)
                dist = np.hypot(dx, dy)
                np.fill_diagonal(dist, np.inf)
                overlap = np.maximum(0.0, min_dist - dist)
                overlap_mask = dist < min_dist

            safe_dist = np.maximum(dist, 1e-9)
            safe_dist = np.where(np.isinf(dist), 1.0, safe_dist)
            nx = np.nan_to_num(dx / safe_dist)
            ny = np.nan_to_num(dy / safe_dist)
            sep = np.nan_to_num(overlap * 0.5)

            # 只处理上三角避免重复
            tri_mask = overlap_mask & (np.arange(n)[:, None] < np.arange(n)[None, :])
            sx = np.where(tri_mask, nx * sep, 0.0)
            sy = np.where(tri_mask, ny * sep, 0.0)
            move_x = sx.sum(axis=1) - sx.sum(axis=0)
            move_y = sy.sum(axis=1) - sy.sum(axis=0)

            xs -= move_x
            ys -= move_y
            # 限制在走廊内
            for i, agent in enumerate(agents):
                agent.x = float(xs[i])
                agent.y = float(ys[i])
                agent.vx *= 0.42
                agent.vy *= 0.42
                self._clamp_agent_position(agent, scenario, mitigation_strategy)
                xs[i] = agent.x
                ys[i] = agent.y

        # 第二轮：位置回退防穿透
        dx2 = xs[:, None] - xs[None, :]
        dy2 = ys[:, None] - ys[None, :]
        dist2 = np.hypot(dx2, dy2)
        np.fill_diagonal(dist2, np.inf)
        min_dist2 = self.agent_radius * (2.02 - 0.62 * pressure_blend) * 0.98
        near_mask = dist2 < min_dist2

        for i, agent in enumerate(agents):
            if not near_mask[i].any():
                continue
            j = np.where(near_mask[i])[0]
            if len(j) == 0:
                continue
            j = j[0]
            other = agents[j]
            agent_prev = previous_positions.get(agent.agent_id, (agent.x, agent.y))
            other_prev = previous_positions.get(other.agent_id, (other.x, other.y))
            agent_shift = math.dist(agent_prev, (agent.x, agent.y))
            other_shift = math.dist(other_prev, (other.x, other.y))
            blocked, blocked_prev = (agent, agent_prev) if agent_shift >= other_shift else (other, other_prev)
            blocked.x, blocked.y = blocked_prev
            blocked.vx = 0.0
            blocked.vy = 0.0
            self._clamp_agent_position(blocked, scenario, mitigation_strategy)

        if scenario == "mitigation":
            self._resolve_intervention_collisions(agents, mitigation_strategy)

    def _backward_pressure_wave_vectorized(
        self,
        agents: list[InternalAgent],
        densities: dict[int, tuple[float, int]],
        step: int,
    ) -> None:
        """用 numpy 向量化后向压力波传播。"""
        n = len(agents)
        if n <= 1:
            return

        xs = np.array([a.x for a in agents], dtype=np.float64)
        dirs = np.array([0 if a.direction == "east" else 1 for a in agents], dtype=np.int8)
        stall = np.array([a.stalled_steps for a in agents], dtype=np.int32)
        cmem = np.array([a.congestion_memory for a in agents], dtype=np.float64)
        dens = np.array([densities.get(a.agent_id, (0.0, 0))[0] for a in agents], dtype=np.float64)

        # 找出需要发射压力波的 agent（高密度 + 连续滞留）
        emitter_mask = (dens >= self.critical_density) & (stall >= 3)
        if not emitter_mask.any():
            return

        dx = xs[:, None] - xs[None, :]  # receiver - emitter
        dy_abs = np.abs(np.array([a.y for a in agents])[:, None] - np.array([a.y for a in agents])[None, :])

        # 只对后方 agent 传播
        backward_mask = np.zeros((n, n), dtype=bool)
        east_emitter = emitter_mask & (dirs == 0)
        west_emitter = emitter_mask & (dirs == 1)
        if east_emitter.any():
            backward_mask |= (dx[:, :] < 0) & east_emitter[None, :]
        if west_emitter.any():
            backward_mask |= (dx[:, :] > 0) & west_emitter[None, :]

        wave_radius = 2.5 + cmem * 1.5
        in_range = np.abs(dx) <= wave_radius[:, None]
        lateral_ok = dy_abs <= 1.5
        valid = backward_mask & in_range & lateral_ok

        if not valid.any():
            return

        wave_strength = np.where(valid, (1.0 - np.abs(dx) / np.maximum(wave_radius[:, None], 1e-6)) * 0.12 * np.minimum(1.0, stall[:, None] / 5.0), 0.0)
        backward_sign = np.where(dirs == 0, -1.0, 1.0)
        force = wave_strength * backward_sign[:, None]

        total_force = force.sum(axis=1)
        for i, agent in enumerate(agents):
            agent.skill_force_x += float(total_force[i])

    async def _trigger_slow_brain(
        self,
        *,
        agents: list[InternalAgent],
        densities: dict[int, tuple[float, int]],
        logs: list[SlowBrainLog],
        step: int,
        scenario: str,
        use_api: bool,
        remaining_api_budget: int,
        mitigation_strategy: str | None = None,
    ) -> int:
        trigger_threshold = self.critical_density
        pending_requests: list[tuple[InternalAgent, float, int, list[str]]] = []
        for agent in agents:
            density, neighbors = densities.get(agent.agent_id, (0.0, 0))
            if density >= trigger_threshold and step - agent.last_trigger_step >= 12:
                pending_requests.append(
                    (
                        agent,
                        density,
                        neighbors,
                        self._collect_heard_messages(agent, agents),
                    )
                )

        if not pending_requests:
            return 0

        api_target_ids = self._select_api_log_targets(
            pending_requests=pending_requests,
            remaining_api_budget=remaining_api_budget,
            use_api=use_api,
        )

        # 并发限制 + 单次超时 + 整步超时预算
        semaphore = asyncio.Semaphore(6)

        async def _call_one(agent, density, neighbors, heard_messages):
            async with semaphore:
                if agent.agent_id not in api_target_ids:
                    return {
                        "agent": agent,
                        "density": density,
                        "content": self._build_scene_reasoner_log(
                            agent=agent,
                            density=density,
                            neighbors=neighbors,
                            heard_messages=heard_messages,
                            step=step,
                            scenario=scenario,
                            mitigation_strategy=mitigation_strategy,
                            source="scene_reasoner",
                        ),
                        "resolved": False,
                        "used_api": False,
                    }
                try:
                    content = await asyncio.wait_for(
                        slow_brain_service.generate_reasoning(
                            agent_id=agent.agent_id,
                            local_density=density,
                            scenario=scenario,
                            use_api=use_api,
                            typology=agent.typology,
                            mitigation_strategy=mitigation_strategy,
                            x=agent.x,
                            y=agent.y,
                            vx=agent.vx,
                            vy=agent.vy,
                            neighbor_count=neighbors,
                            heard_messages=heard_messages,
                            broadcast_radius=agent.broadcast_radius,
                        ),
                        timeout=settings.llm_timeout_seconds,
                    )
                    return {
                        "agent": agent,
                        "density": density,
                        "content": content,
                        "resolved": True,
                        "used_api": True,
                    }
                except Exception as exc:
                    return {
                        "agent": agent,
                        "density": density,
                        "content": self._build_scene_reasoner_log(
                            agent=agent,
                            density=density,
                            neighbors=neighbors,
                            heard_messages=heard_messages,
                            step=step,
                            scenario=scenario,
                            mitigation_strategy=mitigation_strategy,
                            source="scene_reasoner",
                            api_error=str(exc),
                        ),
                        "resolved": False,
                        "used_api": True,
                    }

        # 用 as_completed 实时处理，整步允许更长等待，避免为了追求速度而伪造认知结果
        tasks = [
            asyncio.create_task(_call_one(agent, d, n, h))
            for agent, d, n, h in pending_requests
        ]
        completed_count = 0
        try:
            for task in asyncio.as_completed(tasks, timeout=settings.slow_brain_step_timeout_seconds):
                result = await task
                agent = result["agent"]
                density = result["density"]
                content = result["content"]
                resolved = result["resolved"] and content.get("source") == "llm_api"
                used_api = result["used_api"]
                agent.last_trigger_step = step
                if resolved:
                    agent.triggered = True
                    agent.slow_brain_active = True
                    agent.last_utterance = str(content.get("dialogue") or content.get("action") or "").strip()
                    agent.last_slow_summary = str(content.get("perception") or content.get("intention") or "")[:50]
                    self._apply_action_mapping(agent, content, agents, density, step)
                else:
                    agent.slow_brain_active = False
                    agent.last_utterance = str(content.get("dialogue") or content.get("action") or "").strip()
                    agent.last_slow_summary = str(content.get("perception") or content.get("intention") or "")[:50]
                logs.append(
                    SlowBrainLog(
                        step=step,
                        agent_id=agent.agent_id,
                        severity="fatal" if density >= self.stampede_density else "warning",
                        density=round(density, 2),
                        content=content,
                    )
                )
                if used_api:
                    completed_count += 1
        except (asyncio.TimeoutError, TimeoutError):
            # 整步超时，跳过未完成的请求
            for t in tasks:
                if not t.done():
                    t.cancel()
        finally:
            await asyncio.gather(*tasks, return_exceptions=True)

        return completed_count

    def _select_api_log_targets(
        self,
        *,
        pending_requests: list[tuple[InternalAgent, float, int, list[str]]],
        remaining_api_budget: int,
        use_api: bool,
    ) -> set[int]:
        if not use_api or remaining_api_budget <= 0 or not slow_brain_service.provider_ready:
            return set()
        critical_pool_size = min(
            len(pending_requests),
            max(3, math.ceil(len(pending_requests) * 0.4)),
        )
        target_count = min(
            remaining_api_budget,
            max(1, math.ceil(critical_pool_size * 0.7)),
            4,
        )
        ranked = sorted(
            pending_requests,
            key=lambda item: self._api_log_priority(
                agent=item[0],
                density=item[1],
                neighbors=item[2],
                heard_messages=item[3],
            ),
            reverse=True,
        )
        return {agent.agent_id for agent, _, _, _ in ranked[:target_count]}

    def _api_log_priority(
        self,
        *,
        agent: InternalAgent,
        density: float,
        neighbors: int,
        heard_messages: list[str],
    ) -> float:
        score = density * 3.2
        score += neighbors * 0.28
        score += len(heard_messages) * 0.9
        score += agent.congestion_memory * 2.2
        score += agent.stalled_steps * 0.45
        if agent.typology == "vulnerable":
            score += 2.4
        elif agent.typology == "group_family":
            score += 1.2
        if self.throat_start_x <= agent.x <= self.throat_end_x:
            score += 1.8
        elif self.funnel_start_x <= agent.x <= self.funnel_end_x:
            score += 1.0
        return score

    def _build_scene_reasoner_log(
        self,
        *,
        agent: InternalAgent,
        density: float,
        neighbors: int,
        heard_messages: list[str],
        step: int,
        scenario: str,
        mitigation_strategy: str | None,
        source: str,
        api_error: str | None = None,
    ) -> dict:
        rng = random.Random((self.scenario_seed.get("accident", 22) * 1000003) + (step * 7919) + (agent.agent_id * 101))
        profile = agent.profile_label if agent.profile_label else self._profile_label(agent.typology)
        direction_label = "东侧" if agent.direction == "east" else "西侧"
        density_level = self._risk_level(density)
        in_core = self.throat_start_x <= agent.x <= self.throat_end_x
        near_funnel = self.funnel_start_x <= agent.x <= self.funnel_end_x
        heard_summary = heard_messages[0] if heard_messages else ""
        speed = math.hypot(agent.vx, agent.vy) / self.delta_time
        stall = agent.stalled_steps
        has_group = agent.typology == "group_family" and agent.group_id is not None
        is_vuln = agent.typology == "vulnerable"

        # ── 感知层：按身份×密度×位置×状态组合 ──
        pressure_pool = {
            "fatal": [
                "我整个人被挤得双脚快离地了，左右两侧的人像墙壁一样贴着我的肩膀和手臂，视线只能从前面后脑勺的缝隙里看到一小条灰暗的天。",
                "我已经分不清哪些推力来自前方、哪些来自背后，身体被迫随着人流的节奏左右摇摆，完全失去了自主控制。",
                "胸口被压得喘不上气，我能清晰感觉到身后那个人的呼吸喷在我后颈上，每吸一口气都要用力顶开贴在我胸前的手臂。",
                "周围已经没有任何空隙了，我的书包被挤得变了形，有人的手肘一直顶着我的肋骨，疼得我只能侧着身子硬扛。",
                "我听见身边有人在哭，有人在喊「别推了」，但声音很快就被淹没在人群嘈杂的喘息和脚步声里，压迫感从四面八方涌来。",
                "脚底下好像踩到了什么东西软软的，我不敢低头看，因为一低头脸就会撞到前面那个人的后背，只能拼命维持站姿。",
            ],
            "danger": [
                "人流越来越密，我身边的人都开始侧着身子挪动，前面每隔几秒就会传来一阵突然的挤压波，把所有人往后推一小步。",
                "我已经能清楚感觉到左右两侧的人在互相推搡，有人试图从我旁边挤过去，但根本没有空间让任何人超越。",
                "前方好像出了什么事，人群突然停下来了，后面的人还在往前涌，我被夹在中间，身体不由自主地往前倾。",
                "我面前那个人一直在低头看手机，根本没注意到前面已经停了，我只能用手轻轻挡住他继续往前冲的身体。",
                "空气变得又闷又热，我闻到周围混合着汗味和香水的味道，有人的头发蹭在我脸上，我只能偏过头去。",
                "我能听到前方传来零星的喊叫声，但完全听不清在喊什么，这种不知道发生了什么的感觉比拥挤本身更让人焦虑。",
            ],
            "warning": [
                "人流开始变密了，原本还能正常走路的速度突然慢下来，前面的人好像在减速，我也只能跟着放慢脚步。",
                "身边的人越来越多，原本隔着手臂的距离现在已经被压缩到贴着肩膀了，我开始留意周围有没有可以侧移的空间。",
                "我注意到前方大约二三十米的地方人群密度明显更高，那边好像有人在停下来拍照或者等人，堵住了后面的通行。",
                "巷道两侧的灯光有点暗，我看不太清楚前面具体是什么情况，只能跟着人流的方向慢慢往前挪。",
                "我本来在和朋友边走边聊天，但人流突然变密了，我们不得不肩并肩贴着走，话题也中断了。",
                "前面有几个人停下来系鞋带或者弯腰捡东西，后面的人不得不绕开他们，人流节奏被打乱了。",
            ],
            "safe": [
                "目前人流还不算太密，我能看到前方大约十几米的范围，行人的间距还算正常，偶尔需要侧身避让对面来的人。",
                "巷道里的气氛还算轻松，前面有人在拍照，后面有人在聊天，我按照正常步速往前走着。",
                "我注意到巷道越往前越窄，不过目前通行还算顺畅，前面的人流虽然密集但还在移动。",
            ],
        }
        pressure_phrase = self._pick_phrase(rng, pressure_pool.get(density_level, pressure_pool["warning"]))

        # ── 身体感受：按身份分组，每组大量变体 ──
        body_pool = {
            "vulnerable": [
                "我的膝盖开始发软了，每走一步都要用力撑住才能不往下蹲，旁边有人的胳膊肘碰到了我的腰，我整个人晃了一下。",
                "我紧紧攥着手里的拐杖/雨伞，用它在前面试探有没有落脚的空间，但人群太密了，连抬手的余地都很小。",
                "我能感觉到自己的心跳很快，太阳穴突突地跳，每呼吸一次胸腔都像被什么东西压着，额头上全是汗。",
                "脚下的地面不太平整，我好几次差点被绊倒，每次失衡都让我心跳加速，因为我很清楚一旦摔倒就很难再站起来。",
                "我旁边一个年轻人的背包一直挤着我的脸，我想侧头躲开但根本动不了，只能尽量把头往另一边偏。",
                "我的手一直在发抖，不知道是冷还是害怕，我试着深呼吸让自己冷静下来，但周围太闷了，吸进去的都是热气。",
            ],
            "group_family": [
                "我一只手紧紧拉着同伴的手腕，另一只手在前面挡着人流，每次被挤开一点我都会立刻回头看同伴还在不在身后。",
                "我们两个人被挤得只能侧着身子并排走，我一直在用身体给同伴挡出一点空间，但越来越难做到了。",
                "同伴在我身后喊了一句什么，我没听清，回头看的时候差点被人流冲散，赶紧伸手抓住她的衣袖。",
                "我感觉到同伴的手心全是汗，但谁都不敢松手，前面突然一个挤压波过来，我们两个同时往后退了半步。",
                "我一直在数身边过了几个人，同时用余光确认同伴的位置，只要她在我视线范围内我就不至于太慌。",
                "我们原本在讨论去哪家店吃饭，现在完全没心思了，我只想着怎么带着同伴安全从这段拥挤的巷道里出去。",
            ],
            "normal_pedestrian": [
                "我的步伐被打断了，前面那个人突然停下来，我不得不急刹车，身体往前倾了一下才稳住，背后立刻有人贴上来了。",
                "我的呼吸开始变急促了，每走两三步就要停下来等一下，这种走走停停的节奏让我的腿开始发酸。",
                "我把背包转到胸前抱着，这样至少不会被挤得失去平衡，但抱着东西走路更不方便了，手臂一直在使劲。",
                "我一直在观察前面人群的头顶和肩膀来判断移动方向，因为视线已经被完全挡住了，只能靠感觉跟着走。",
                "身边一个高个子的人胳膊一直在我头顶晃，我只能缩着脖子走，脖子已经开始僵了。",
                "我试着用手机看看导航还有多远，但举起来就被旁边的人撞了一下，差点把手机掉了，赶紧塞回口袋。",
            ],
        }
        body_phrase = self._pick_phrase(rng, body_pool.get(agent.typology, body_pool["normal_pedestrian"]))

        # ── 位置描述：细化到具体位置感受 ──
        if in_core:
            loc_pool = [
                "我现在正好卡在巷道最窄的那一段，两侧墙壁近得伸手就能摸到，人流在这里被压缩成一条几乎没有横向空间的细流。",
                "这段核心瓶颈区的天花板好像也比别处低，空气更闷，我感觉自己像被塞进了一个不断缩小的管道里。",
                "我能看到前方十几米处巷道突然变宽了，但就是过不去，所有人都堵在这个收口处，像瓶子里的水怎么倒都倒不出来。",
            ]
        elif near_funnel:
            loc_pool = [
                "我正在往巷道最窄的那段走，能明显感觉到两侧的空间在收窄，人流的速度也在变慢，像河水进入瓶颈一样。",
                "前方的巷道开始收窄了，人群开始往中间聚拢，原本还能侧身移动的空间正在快速消失。",
                "我刚好在漏斗区的入口，前面的人已经开始挤了，但后面的人还不知道，还在正常速度往前涌，压力就是这么来的。",
            ]
        else:
            loc_pool = [
                f"我还在靠近{direction_label}的通道里，离核心拥堵区还有一段距离，但已经能感觉到前方传过来的减速信号了。",
                f"我所在的位置人流密度还不算极端，但前面的趋势越来越不好，我想加快速度在彻底堵死之前通过。",
                f"从{direction_label}方向过来的人还在不断涌入，我被裹挟在人流中往前走，想停下来都很难。",
            ]
        location_phrase = self._pick_phrase(rng, loc_pool)

        # ── 听到的声音 ──
        if heard_summary:
            heard_pool = [
                f"耳边突然传来一句「{heard_summary}」，声音很近，就在我右后方，让我一下子紧张起来。",
                f"我听到有人喊了句「{heard_summary}」，声音被人群的嘈杂淹没了一半，但我还是听清了，心里一沉。",
                f"旁边有人用力喊了一声「{heard_summary}」，我循声看过去但只能看到一片后脑勺，根本找不到是谁在喊。",
                f"那句「{heard_summary}」一直在我脑子里回响，虽然我不确定是不是在对我说，但周围确实已经有人控制不住情绪了。",
            ]
        else:
            heard_pool = [
                "周围全是脚步声、喘气声和偶尔的咳嗽声，偶尔有人低声抱怨几句，但大多数人都沉默着只顾低头往前挪。",
                "我能听到远处好像有警笛的声音，但很模糊，不确定是不是从巷道外面传进来的，这种不确定感让人更不安。",
                "有人在我身后打了好几个喷嚏，空气太闷了，我甚至能闻到旁边人衣服上的烟味和汗味混在一起。",
                "我隐约听到前面有人在用对讲机说话，可能是在维持秩序，但声音太小了完全听不清在说什么。",
            ]
        heard_phrase = self._pick_phrase(rng, heard_pool)

        perception = f"{pressure_phrase}{location_phrase}我身边大约贴着 {neighbors} 个人，局部密度已经达到 {density:.2f} 人/m²。{heard_phrase}"

        # ── 情绪层：按身份×密度组合，融入身体感受 ──
        emotion_pool = {
            ("fatal", "vulnerable"): [
                "我的眼眶开始发酸了，有种想哭但又不敢哭出来的憋屈感，我知道现在如果情绪崩溃只会让处境更危险。",
                "我脑子里突然闪过新闻里踩踏事故的画面，一股寒意从脚底窜上来，我拼命告诉自己要冷静但手已经在抖了。",
            ],
            ("fatal", "group_family"): [
                "我最怕的不是自己出事，而是和同伴被人流冲散之后她一个人在这种环境里怎么办，这个念头让我比任何时候都慌。",
                "我能感觉到同伴在我身后也在发抖，我想安慰她但自己声音都在颤，只能说「没事的，跟着我」但其实我也不知道往哪走。",
            ],
            ("fatal", "normal_pedestrian"): [
                "说实话我已经有点后悔走进来了，现在想退也退不出去，前面的人墙和后面涌来的人流把我钉死在这个位置上。",
                "我能感觉到自己的肾上腺素在飙升，整个人进入了一种高度警觉的状态，每一根神经都在告诉我这里很危险。",
            ],
            ("danger", "vulnerable"): [
                "我心里一直在默念「再坚持一下就过去了」，但身体已经开始发出力竭的信号了，腿越来越沉，呼吸越来越短。",
                "我尽量不去想最坏的结果，但焦虑还是像潮水一样一阵一阵地涌上来，我只能把注意力集中在脚下每一步上。",
            ],
            ("danger", "group_family"): [
                "我一直在用身体语言告诉同伴「别怕，跟着我」，但其实我自己心里也没底，只是不能表现出来让她更紧张。",
                "同伴的手攥得我手腕都疼了，但我不打算让她松开，这是我们之间唯一的联系，松开了可能就再也挤不到一起了。",
            ],
            ("danger", "normal_pedestrian"): [
                "我开始认真考虑是不是应该想办法往墙边靠，至少一侧有墙的话不会被四面八方的力同时挤压。",
                "脑子里在快速盘算着：前面还有多远、人流的速度是加快还是减慢、身边有没有人看起来快要撑不住了。",
            ],
            ("warning", "vulnerable"): [
                "我现在还能控制自己的步伐，但已经开始紧张了，我知道再往前走可能就不是我能应付的程度了。",
                "我有想过现在转身回去，但回头看了看后面的人流，发现回头的路也已经被堵住了，只能硬着头皮继续走。",
            ],
            ("warning", "group_family"): [
                "我跟同伴说「走慢点，别急」，但其实是在提醒自己不要被人群的节奏带着走，要保持自己的判断。",
                "目前还能跟同伴保持并排走，但我已经注意到身边的空间在变窄，等会儿可能就要改成前后走了。",
            ],
            ("warning", "normal_pedestrian"): [
                "我开始留意周围有没有可以侧移的空间了，虽然现在还没到危险的程度，但提前留好退路总没坏处。",
                "有点烦躁，前面走得太慢了，但我也不敢催，毕竟大家都在同一条巷道里，催也没用。",
            ],
            ("safe", "vulnerable"): [
                "现在还算能正常走，但我知道这种窄巷子一旦人多起来就会很麻烦，所以我尽量贴着墙边走。",
                "我走得比较慢，时不时要侧身让后面的人先过，虽然有点不好意思但也不想被人群裹着走。",
            ],
            ("safe", "group_family"): [
                "我们边走边聊，还在讨论等会儿去哪，但我已经注意到前面的人越来越密了。",
                "同伴说前面好像很多人，我说应该没事吧，但其实心里已经开始有点打鼓了。",
            ],
            ("safe", "normal_pedestrian"): [
                "目前一切正常，就是人比想象的多，可能因为今天是什么活动吧，大家都在往同一个方向走。",
                "我还在正常步速走着，偶尔看看手机确认方向，巷道两侧有些小店，气氛还挺热闹的。",
            ],
        }
        emotion_key = (density_level, agent.typology)
        emotion_phrase = self._pick_phrase(rng, emotion_pool.get(emotion_key, emotion_pool.get((density_level, "normal_pedestrian"), ["我保持警觉，随时关注着周围的变化。"])))

        # ── 意图层：按身份×密度×滞留状态组合 ──
        if stall >= 4:
            intent_pool = [
                f"我已经在这个位置站了 {stall} 步了完全动不了，现在只想着怎么不被人流推倒，前进已经不是优先选项了。",
                "原地滞留了太久，我的腿开始发麻了，我在试着侧移哪怕半步也好，至少换一个能稍微喘口气的站位。",
            ]
        elif is_vuln:
            intent_pool = [
                "我现在最想做的就是贴着墙边慢慢走，不跟人流正面对冲，哪怕绕远一点也比被挤在中间强。",
                "我决定不再试图跟上前面人的速度了，按照自己能承受的节奏走，谁催我我都不会加速。",
                "我在找一个稍微宽敞一点的地方停下来喘口气，哪怕只是停几秒也好，让心跳先慢下来再说。",
                "如果前面再出现一次大的挤压波，我就直接往最近的墙边靠，不再犹豫了，安全第一。",
            ]
        elif has_group:
            intent_pool = [
                "我打算拉着同伴往右边靠，那边看起来空间稍微大一点，而且离墙壁近，至少有一侧是安全的。",
                "我在观察前面的人流方向，想找一个对向人流最少的路径，带着同伴从侧面慢慢绕过这段最堵的地方。",
                "我跟同伴说「跟着我走，别走散了」，然后开始侧身往边缘移动，不想继续被人流裹在中间了。",
                "只要前面出现一小块空隙我就会带着同伴赶紧补上去，但绝对不会硬挤，万一挤散了就得不偿失了。",
                "我现在放弃继续往前的想法了，先带着同伴退到一个不那么挤的地方，等前面通了再走。",
            ]
        else:
            intent_pool = [
                "我在观察左右两侧哪边的人流稍微松一点，一旦看准了就立刻侧移过去，不想继续卡在这个位置。",
                "我决定改变策略，不再跟着大部队正面前进，而是往墙边靠沿着边缘走，虽然慢一点但至少能动。",
                "前面那个人一直挡着不走，我在想要不要从他右边绕过去，右边看起来有一条手臂宽的缝隙。",
                "我打算在这里等一等，等人流自然松动了再走，硬挤只会让情况更糟。",
                "我在算还有多少距离能通过这段最堵的地方，目测前面大概还有二三十米，但以现在的速度可能要走很久。",
                "我想掉头往回走了，但回头一看后面也已经堵死了，现在是前后都动不了，只能想办法侧移。",
            ]
        intention = self._pick_phrase(rng, intent_pool)

        # ── 对话/呼喊层：按身份×密度×听到的内容组合，大量变体 ──
        if heard_summary:
            dial_pool = [
                "别再往里挤了，前面已经没有空间了！",
                "慢一点，先稳住，不要把人往前顶！",
                "靠边一点，我这边已经快站不住了！",
                "后面的人能不能先停一下！前面已经走不动了！",
                "别推了！真的别推了！会出事的！",
                "前面的人能不能动一动啊，别站着不动！",
                "求求你们别挤了，我旁边有人快要摔倒了！",
                "大家冷静一下，越挤越走不动！",
                "我喊了好几遍了别推了，有没有人听得到啊！",
                "靠右边走！都靠右边走！别堵在中间！",
            ]
        elif is_vuln:
            dial_pool = [
                "慢一点，我站不太稳，别再推了。",
                "先让我缓一下，前面真的太挤了。",
                "我走不快，你们从旁边过吧，别挤我。",
                "对不起让一下，我需要扶一下墙……",
                "我有点不舒服，能不能让我先到边上歇一下？",
                "别挤我，我腿脚不好走不快……",
                "前面能不能慢一点，我跟不上……",
                "有人能帮我一下吗，我快要站不住了……",
            ]
        elif has_group:
            dial_pool = [
                "别松手，跟着我往侧边一点点挪。",
                "你先别急，贴着我这边走，不要被挤散。",
                "我在这边，你往我这边靠！",
                "别走那边，太挤了，跟我从这边绕！",
                "抓紧我，前面好像又堵了！",
                "你先别动，等我看看哪边能走！",
                "往右靠一点，右边空间大一些！",
                "别急别急，等一下再走，先稳住！",
            ]
        else:
            dial_pool = [
                "前面别再顶了，大家慢一点。",
                "这边已经堵住了，别一起往中间挤。",
                "能别停下来拍照吗？后面全堵了！",
                "借过借过，让我从右边过去一下。",
                "别挤了行不行，大家都走不动！",
                "前面到底什么情况啊，怎么突然停了？",
                "大家稍微往两边靠一靠，中间留个通道！",
                "后面的人先别往前涌了，前面已经满了！",
                "能不能别在路中间停下来系鞋带啊！",
                "这到底要堵到什么时候……",
            ]
        dialogue = self._pick_phrase(rng, dial_pool)

        # ── 动作层：按身份×密度×位置×滞留状态组合 ──
        if is_vuln:
            if density_level in ("fatal", "danger"):
                act_pool = [
                    "我把身体重心压低，双手交叉护在胸前，用小碎步一点点往墙边挪，每挪一步都要先确认脚下是稳的。",
                    "我侧过身子用肩膀对着人流方向，这样被推的时候至少不会正面失去平衡，然后一点一点往边缘蹭。",
                    "我放弃了前进的想法，现在就专注于不被推倒，用一只手扶着旁边人的背包保持平衡，另一只手护住自己的肋骨。",
                    "我蹲低了一点让重心更稳，用脚尖试探着前方有没有落脚空间，有的话就挪半步，没有就原地等着。",
                ]
            else:
                act_pool = [
                    "我贴着右边的墙壁慢慢走，一只手轻轻扶着墙面保持平衡，不去跟中间的人流抢位置。",
                    "我放慢了步伐，跟前面的人保持一小段距离，给自己留出反应的空间，万一前面突然停了不至于撞上去。",
                    "我侧身让后面的人先过去，然后跟在他们后面慢慢走，不着急，反正快也快不了多少。",
                ]
        elif has_group:
            if density_level in ("fatal", "danger"):
                act_pool = [
                    "我用一只手紧紧握住同伴的手腕，另一只手在前面挡着人流给我们开路，身体微微侧过来给同伴留出一点呼吸空间。",
                    "我把同伴拉到我身后，自己在前面当人肉盾牌挡着挤压，同时用身体语言告诉她跟着我的脚步走。",
                    "我跟同伴背靠背站了一会儿缓了口气，然后重新调整方向，我走前面她走后面，用最小的步伐往前挪。",
                    "我抓住同伴的胳膊把她往墙边推，自己挡在外侧面对人流，一边挪一边回头看她有没有跟上。",
                ]
            else:
                act_pool = [
                    "我跟同伴肩并肩走着，我走靠中间那一侧，让她靠墙那边，有情况我可以第一时间挡一下。",
                    "我拉着同伴的手腕走在前面，每走几步就回头看一眼确认她还在，遇到缝隙就侧身让她先过。",
                    "我放慢速度跟同伴保持同样的节奏，不让她掉队，遇到前面减速就提前用手势提醒她停下来。",
                ]
        else:
            if density_level in ("fatal", "danger"):
                act_pool = [
                    "我收紧核心、压低重心，用碎步跟着前面那个人的节奏走，他停我就停，他动我就动，绝不多抢半步。",
                    "我侧过身子从两个人之间的缝隙里挤过去，虽然肩膀被夹了一下但总算往前挪了半米。",
                    "我放弃了正面突围，转而往右边靠墙的方向侧移，一步一步地蹭，每一步都很小但至少在动。",
                    "我停下来深吸一口气观察了一下局势，发现左边好像有一条稍微松一点的通道，开始往那边挪。",
                    "我把背包甩到前面当盾牌，用它在前面开一点空间，同时身体紧跟着往前挤。",
                    "我弯下腰降低重心，用手撑着前面那个人的背包稳住自己，等前面松动了再往前挪。",
                ]
            else:
                act_pool = [
                    "我保持正常步速跟着人流走，遇到前面减速就稍微侧移一下绕过去，不去正面硬挤。",
                    "我跟着前面那个人走，保持大约半米的距离，他快我就快他慢我就慢，像一条小鱼跟在大鱼后面。",
                    "我一边走一边观察前方的人流密度，看到前面有空隙就加快两步补上去，没有就耐心等着。",
                    "我靠右边走留出左边的空间给对面来的人，这样双向人流不会正面冲撞，通行效率反而更高。",
                ]
        action = self._pick_phrase(rng, act_pool)

        # ── 移动策略提示 ──
        hint_pool = [
            "保持微小侧移，避开正前方的高压拥堵带。",
            "优先沿墙或侧后方寻找半步级别的空隙。",
            "跟随局部空隙移动，为可能出现的回压预留调整空间。",
            "向最近的墙壁方向侧移，减少四面受力。",
            "紧贴前人节奏，不做任何多余动作。",
            "放弃前进，先稳住站位再说。",
            "从边缘绕行，避免正面冲撞。",
            "小碎步前进，随时准备急停。",
        ]
        movement_hint = self._pick_phrase(rng, hint_pool)

        if scenario == "mitigation" and mitigation_strategy and mitigation_strategy != "none":
            mitigation_fragments = self._mitigation_log_fragments(
                agent=agent,
                mitigation_strategy=mitigation_strategy,
                rng=rng,
            )
            if mitigation_fragments.get("perception"):
                perception = f"{perception}{mitigation_fragments['perception']}"
            if mitigation_fragments.get("emotion"):
                emotion_phrase = f"{emotion_phrase}{mitigation_fragments['emotion']}"
            if mitigation_fragments.get("intention"):
                intention = f"{intention}{mitigation_fragments['intention']}"
            if mitigation_fragments.get("dialogue"):
                dialogue = mitigation_fragments["dialogue"]
            if mitigation_fragments.get("action"):
                action = mitigation_fragments["action"]
            if mitigation_fragments.get("movement_hint"):
                movement_hint = mitigation_fragments["movement_hint"]

        return {
            "agent_id": agent.agent_id,
            "source": source,
            "generation_status": "narrative",
            "api_error": api_error or "",
            "typology": agent.typology,
            "profile_label": profile,
            "local_density": round(density, 2),
            "position": {"x": round(agent.x, 2), "y": round(agent.y, 2)},
            "neighbor_count": neighbors,
            "heard_messages": heard_messages[:4],
            "perception": perception,
            "emotion": emotion_phrase,
            "intention": intention,
            "dialogue": dialogue,
            "action": action,
            "movement_hint": movement_hint,
        }

    def _mitigation_strategy_label(self, mitigation_strategy: str | None) -> str:
        mapping = {
            "central_guardrail": "中央护栏分流",
            "one_way_flow": "单向导流",
            "widen_exits": "出口拓宽",
        }
        return mapping.get(str(mitigation_strategy or ""), "干预措施")

    def _mitigation_log_fragments(
        self,
        *,
        agent: InternalAgent,
        mitigation_strategy: str,
        rng: random.Random,
    ) -> dict[str, str]:
        typology = agent.typology
        label = self._mitigation_strategy_label(mitigation_strategy)

        fragments = {
            "central_guardrail": {
                "normal_pedestrian": {
                    "perception": [
                        f"中间那道{label}把对向人流隔开后，我前面不再一直迎着另一股人流硬顶，正面冲撞明显少了。",
                    ],
                    "emotion": [
                        "虽然还是挤，但少了对向硬顶之后，我能感觉到局势比刚才更可控一点。",
                    ],
                    "intention": [
                        f"我准备顺着{label}这一侧连续补步，不再去跟对向人流抢中线位置。",
                    ],
                    "dialogue": [
                        "护栏把人流分开了，别再往中间挤，顺着这一侧慢慢走！",
                    ],
                    "action": [
                        f"我顺着{label}这一侧小步连续前进，尽量不再和对向人流发生正面顶撞。",
                    ],
                    "movement_hint": [
                        "沿护栏一侧连续补步前进，避开中线对冲带。",
                    ],
                },
                "group_family": {
                    "perception": [
                        f"{label}把两股人流分开后，我和同伴不用同时防着对向的人撞进来，队形比之前稳得多。",
                    ],
                    "emotion": [
                        "护栏把人流隔开后，我至少不用一边护着同伴一边扛迎面冲击，心里稍微稳了一点。",
                    ],
                    "intention": [
                        f"我准备让同伴贴着{label}或墙边走，我自己在外侧护着，这样不容易被人流拆开。",
                    ],
                    "dialogue": [
                        "你贴着护栏这边跟着我走，别松手，这边比刚才稳！",
                    ],
                    "action": [
                        f"我把同伴护在靠{label}的一侧，自己走在外侧一点点往前挪，保持队形不散。",
                    ],
                    "movement_hint": [
                        "让同伴走内侧，自己走外侧，沿护栏方向缓慢前移。",
                    ],
                },
                "vulnerable": {
                    "perception": [
                        f"{label}立起来后，横着拍过来的那股力小了一截，我贴着边慢慢挪的时候身体更容易站稳。",
                    ],
                    "emotion": [
                        "侧向推挤减轻后，我终于没有刚才那种随时会被撞歪的慌张感了。",
                    ],
                    "intention": [
                        f"我决定借着{label}分开的这点空间贴边慢慢走，只要不再被横着撞到就行。",
                    ],
                    "dialogue": [
                        "我靠着护栏慢慢走就行，别再从侧面挤我了……",
                    ],
                    "action": [
                        f"我贴着{label}和边缘慢慢走，先稳住身体，再找下一步落脚空间。",
                    ],
                    "movement_hint": [
                        "贴着护栏或墙边稳步移动，避免横向受力。",
                    ],
                },
            },
            "one_way_flow": {
                "normal_pedestrian": {
                    "perception": [
                        f"{label}之后，前面的移动方向更统一了，迎面顶回来的那种阻力少了不少。",
                    ],
                    "emotion": [
                        "方向统一之后，我的紧张感没有刚才那么尖锐了，至少不用一直防迎面的人。",
                    ],
                    "intention": [
                        f"我准备顺着{label}给出的方向走，不再逆着最拥挤的那股流线去抢位置。",
                    ],
                    "action": [
                        f"我跟着统一流向前进，借着{label}后的顺行节奏一点点通过拥挤段。",
                    ],
                    "movement_hint": [
                        "顺着单一流向前进，减少横向换道和迎面冲撞。",
                    ],
                },
                "group_family": {
                    "perception": [
                        f"{label}让周围人基本朝同一个方向走，我和同伴不用再一边防走散一边躲迎面的人。",
                    ],
                    "emotion": [
                        "同向流动后，我带着同伴前进时心里有底一点，不再那么怕被迎面冲散。",
                    ],
                    "intention": [
                        f"我打算带着同伴顺着{label}方向慢慢走，减少临时换道带来的拉扯。",
                    ],
                    "action": [
                        f"我拉着同伴顺着{label}后的队列移动，不再频繁左右换位。",
                    ],
                    "movement_hint": [
                        "顺着单一流向同步前进，保持同伴队形稳定。",
                    ],
                },
                "vulnerable": {
                    "perception": [
                        f"{label}之后，正面冲撞几乎没有了，我最怕的那种突然被人迎头撞一下的感觉缓和了。",
                    ],
                    "emotion": [
                        "迎面碰撞少了之后，我能把注意力更多放在脚下，而不是一直担心被顶翻。",
                    ],
                    "intention": [
                        f"我现在只想跟着单一流向慢慢走，别再出现迎面冲撞就好。",
                    ],
                    "action": [
                        f"我放慢速度贴着边顺行，通过{label}形成的单一流向减轻迎面受力。",
                    ],
                    "movement_hint": [
                        "沿单向流线贴边缓行，优先保持身体稳定。",
                    ],
                },
            },
            "widen_exits": {
                "normal_pedestrian": {
                    "perception": [
                        f"靠近出口时我能感觉到{label}后的口门更开了，前面那种排队完全卡死的感觉缓下来一些。",
                    ],
                    "emotion": [
                        "出口前那种死死卡住的烦躁感缓了一点，我能感觉到队伍终于开始松动。",
                    ],
                    "intention": [
                        f"我准备借着{label}后的开口往前补位，尽快通过出口前那段排队区。",
                    ],
                    "action": [
                        f"我顺着{label}后的更宽出口前进，抓住排队间隙连续通过。",
                    ],
                    "movement_hint": [
                        "沿更开阔的出口前区缓慢通过，减少在口门前急停。",
                    ],
                },
                "group_family": {
                    "perception": [
                        f"{label}后，临近出口的堆积没有刚才那么死，我和同伴不用一直卡在最后那几步。",
                    ],
                    "emotion": [
                        "出口变宽后，我和同伴终于不用一直堵在最后几步，心里没那么急了。",
                    ],
                    "intention": [
                        f"我打算带着同伴趁出口开阔一些时同步往前走，别再被卡在门口前。",
                    ],
                    "action": [
                        f"我拉着同伴靠向出口较宽的位置，小步同步通过，避免在口门前再次停死。",
                    ],
                    "movement_hint": [
                        "沿更开阔的出口前区同步前进，保持同伴并列或前后紧跟。",
                    ],
                },
                "vulnerable": {
                    "perception": [
                        f"出口被放宽后，前面那团人堵成一团的压迫感减轻了，我终于能看清下一步该落在哪。",
                    ],
                    "emotion": [
                        "前方开阔一些后，我的呼吸都顺了一点，至少不再像刚才那样挤得完全没落脚空间。",
                    ],
                    "intention": [
                        f"我想趁着{label}后的排队松动慢慢往前过，不再和别人抢最后那一点口门。",
                    ],
                    "action": [
                        f"我放慢速度稳定地朝更宽的出口方向走，每一步都比刚才更能找到落脚点。",
                    ],
                    "movement_hint": [
                        "沿更宽的出口方向缓慢通过，优先保证落脚稳定。",
                    ],
                },
            },
        }

        strategy_fragments = fragments.get(mitigation_strategy, {})
        profile_fragments = strategy_fragments.get(typology, {})
        return {key: self._pick_phrase(rng, values) for key, values in profile_fragments.items() if values}

    def _pick_phrase(self, rng: random.Random, options):
        return rng.choice(options) if options else ""

    def _update_agents(
        self,
        agents: list[InternalAgent],
        densities: dict[int, tuple[float, int]],
        scenario: str,
        mitigation_strategy: str,
        rng: random.Random,
        step: int,
    ) -> None:
        previous_positions = {agent.agent_id: (agent.x, agent.y) for agent in agents}
        # 预计算：哪些Agent在当前步被阻塞（位移极小）
        blocked_set: set[int] = set()
        for agent in agents:
            prev = previous_positions.get(agent.agent_id, (agent.x, agent.y))
            displacement = math.dist(prev, (agent.x, agent.y))
            if displacement < 0.02 and densities.get(agent.agent_id, (0.0, 0))[0] >= self.safe_density_limit:
                blocked_set.add(agent.agent_id)

        # 向量化预计算所有 agent 间的交互力（替代 O(n²) 纯 Python 循环）
        self._compute_interaction_forces_vectorized(agents, scenario, mitigation_strategy, step, densities)

        for agent in agents:
            density, _ = densities.get(agent.agent_id, (0.0, 0))
            density_ratio = max(0.0, min(density / max(self.stop_density_threshold, 1e-6), 1.0))
            overload_blend = self._overload_blend()

            # 更新拥堵记忆与滞留状态
            if density >= self.safe_density_limit:
                agent.congestion_memory = min(1.0, agent.congestion_memory + 0.08)
                if agent.agent_id in blocked_set:
                    agent.stalled_steps += 1
                else:
                    agent.stalled_steps = max(0, agent.stalled_steps - 1)
            else:
                agent.congestion_memory = max(0.0, agent.congestion_memory - 0.12)
                agent.stalled_steps = max(0, agent.stalled_steps - 2)
            agent.local_blocked = agent.stalled_steps >= 3

            # --- Piecewise Weidmann-style speed-density model (v2: steeper decay) ---
            if density < 1.5:
                speed = agent.preferred_speed
            elif density < 3.0:
                blend = (density - 1.5) / 1.5
                speed = agent.preferred_speed * (1.0 - blend * 0.5)
            elif density < self.stop_density_threshold:
                decay_rate = -math.log(max(self.congested_speed / agent.preferred_speed, 0.01)) / max(self.stop_density_threshold - 3.0, 1.0)
                speed = agent.preferred_speed * 0.5 * math.exp(-decay_rate * (density - 3.0))
            else:
                speed = max(0.008, self.congested_speed * math.exp(-0.45 * (density - self.stop_density_threshold)))

            # --- Body compression at extreme densities ---
            if density > 4.0:
                speed *= math.exp(-0.30 * (density - 4.0))

            # --- Environmental speed modifiers ---
            env_factor = 1.0
            if agent.support_until_step >= step:
                env_factor *= 0.84
            if agent.slow_brain_active and density >= 6.0:
                env_factor *= 0.85
            if self.throat_start_x <= agent.x <= self.throat_end_x:
                if scenario == "accident":
                    env_factor *= 0.72 - (0.5 * overload_blend)
                elif mitigation_strategy == "widen_exits":
                    env_factor *= 0.9 - (0.12 * overload_blend)
                else:
                    env_factor *= 0.85 - (0.45 * overload_blend)
            elif self.funnel_start_x <= agent.x <= self.funnel_end_x:
                if scenario == "accident":
                    env_factor *= 0.9 - (0.24 * overload_blend)
                else:
                    env_factor *= 0.96 - (0.2 * overload_blend)
            if density >= self.critical_density:
                env_factor *= max(0.15, 1.0 - ((density - self.critical_density) * 0.12))
            if self.current_overload_ratio > 1.0 and abs(agent.x - self.center_x) <= (self.core_length * 0.7):
                env_factor *= max(0.15, 1.0 - (0.28 * overload_blend))
            # 排队回压传播：连续滞留的Agent会向后方传播减速效应
            if agent.stalled_steps >= 2:
                back_pressure = min(0.35, agent.stalled_steps * 0.06) * (1.0 + agent.congestion_memory * 0.5)
                env_factor *= max(0.15, 1.0 - back_pressure)
            # 局部停滞扩散：高拥堵记忆会降低周边速度
            if agent.congestion_memory > 0.4:
                spread_factor = 1.0 - (agent.congestion_memory - 0.4) * 0.2
                env_factor *= max(0.2, spread_factor)

            env_factor = max(0.08, env_factor)
            speed *= env_factor

            # --- Agent-specific modifier (applied last) ---
            speed *= max(0.7, min(1.3, agent.aggressiveness))

            destination_dx = agent.target_x - agent.x
            destination_dy = (agent.target_y + agent.preferred_offset_y) - agent.y
            destination_norm = max(1e-6, math.hypot(destination_dx, destination_dy))
            destination_x = destination_dx / destination_norm
            destination_y = destination_dy / destination_norm
            # 从向量化缓存读取交互力
            repulsion_x = agent._repulsion_x
            repulsion_y = agent._repulsion_y
            head_on_pressure = agent._head_on_pressure
            shear_force = agent._shear_force
            compression_wave = agent._compression_wave
            cohesion_force_x = agent._cohesion_force_x
            cohesion_force_y = agent._cohesion_force_y
            beacon_response_y = agent._beacon_response_y
            give_space_drag = agent._give_space_drag
            queueing_brake = agent._queueing_brake
            retreat_force_x = 0.0
            wall_spread_force_y = 0.0  # 新增：墙壁扩散力
            core_attraction_force_x = 0.0  # 新增：核心区域吸引力

            desired_lane = self._lane_center(agent.direction, agent.x, scenario, mitigation_strategy)
            target_pull = (agent.target_y + agent.preferred_offset_y) - agent.y
            lane_force = (desired_lane - agent.y) * 0.055 + target_pull * 0.045 + beacon_response_y
            local_wave = math.sin((step * 0.55) + agent.sway_phase + (agent.x * 0.16))
            lateral_turbulence = rng.uniform(-agent.turbulence, agent.turbulence) + (local_wave * agent.turbulence * 0.42)

            # 新增：墙壁扩散力 - 高密度时人群向两侧墙壁扩散
            # 根据数据集DP-004：临界危险密度=5人/平方米
            # 当密度超过安全密度上限时，增加向墙壁的扩散力
            if density >= self.safe_density_limit:
                current_half_width = self._corridor_half_width(agent.x, mitigation_strategy)
                # 计算agent到中心的距离比例
                dist_to_center_ratio = abs(agent.y) / max(current_half_width, 0.1)
                # 如果agent在中心区域（距离中心<40%），增加向墙壁的力
                if dist_to_center_ratio < 0.4:
                    # 扩散力强度与密度成正比
                    spread_strength = min(0.35, (density - self.safe_density_limit) * 0.08)
                    # 方向：向最近的墙壁
                    wall_direction = 1.0 if agent.y >= 0 else -1.0
                    wall_spread_force_y = wall_direction * spread_strength
                # 如果已经在墙壁附近（距离中心>70%），减少扩散力
                elif dist_to_center_ratio > 0.7:
                    wall_spread_force_y = 0.0

            # 核心区域吸引力：事故场景下生效，强度根据密度动态调整
            if scenario == "accident":
                if self.throat_start_x <= agent.x <= self.throat_end_x:
                    dist_to_core_center = abs(agent.x - self.center_x)
                    core_pressure_blend = self._core_pressure_blend(agent.x, scenario, mitigation_strategy)
                    # 根据密度调整吸引力强度
                    density_factor = min(1.0, density / self.critical_density) if self.critical_density > 0 else 0.5
                    # 大幅增强吸引力系数
                    stay_strength = (0.80 + (0.50 * core_pressure_blend)) * density_factor
                    center_lock = (self.center_x - agent.x) * (0.15 + (0.10 * core_pressure_blend)) * density_factor
                    core_attraction_force_x = (-agent.vx * stay_strength) + center_lock

            # 出口滑出力：靠近出口的Agent获得向出口方向的额外推力
            forward_sign = 1.0 if agent.direction == "east" else -1.0
            exit_zone_start = self.length - 10.0
            if agent.direction == "east" and agent.x > exit_zone_start:
                exit_pull = 0.25 * ((agent.x - exit_zone_start) / 10.0)
                core_attraction_force_x += exit_pull
            elif agent.direction == "west" and agent.x < 10.0:
                exit_pull = 0.25 * ((10.0 - agent.x) / 10.0)
                core_attraction_force_x -= exit_pull
            if scenario == "accident":
                bottleneck_ratio = 1.0 - (self._corridor_half_width(agent.x, mitigation_strategy) / self.max_abs_y)
                lateral_turbulence += rng.uniform(-0.08, 0.08) * min(1.0, density / 4.2)
                lane_force += agent.cluster_bias * 0.06
                compression_wave *= 1.0 + bottleneck_ratio * 2.4
                shear_force *= 1.0 + bottleneck_ratio * 1.8
            if self.current_overload_ratio > 1.0 and self.funnel_start_x <= agent.x <= self.funnel_end_x:
                compression_wave *= 1.0 + (0.85 * overload_blend)
                head_on_pressure *= 1.0 + (0.65 * overload_blend)
                shear_force *= 1.0 + (0.45 * overload_blend)
            if scenario == "mitigation" and mitigation_strategy == "central_guardrail":
                # 中央护栏：大幅减少对向压力和剪切力，人群被分到两侧
                shear_force *= 0.35
                head_on_pressure *= 0.25
                # 添加护栏斥力：靠近护栏时被推开
                if self._within_barrier_segment(agent.x):
                    barrier_distance = abs(agent.y) - self.central_barrier_half_width
                    if barrier_distance < 0.5:
                        repulsion_strength = 0.8 * (1.0 - barrier_distance / 0.5)
                        if agent.y > 0:
                            agent.vy += repulsion_strength
                        else:
                            agent.vy -= repulsion_strength
            if scenario == "mitigation" and mitigation_strategy == "one_way_flow":
                # 单向流动：大幅减少对向压力，西向人群被强制减速
                shear_force *= 0.15
                head_on_pressure *= 0.05
                if agent.direction == "west":
                    speed *= 0.4  # 西向人群速度大幅降低
            if scenario == "mitigation" and mitigation_strategy == "widen_exits":
                # 拓宽出口：减少压缩波，提升疏散效率
                compression_wave *= 0.65
                head_on_pressure *= 0.6
                speed *= 1.15  # 出口变宽，速度提升
            speed *= max(0.03, 1.0 - head_on_pressure - give_space_drag - min(0.55, queueing_brake))

            # --- Backward retreat force: stalled agents try to retreat ---
            forward_sign = 1.0 if agent.direction == "east" else -1.0
            if density >= self.stampede_density and agent.stalled_steps >= 4:
                retreat_magnitude = min(0.45, 0.08 * agent.stalled_steps + 0.15 * agent.congestion_memory)
                if abs(agent.x - self.center_x) <= (self.core_length * 0.9):
                    retreat_magnitude *= 0.2
                retreat_force_x = -forward_sign * retreat_magnitude
            elif density >= self.critical_density and agent.stalled_steps >= 6:
                retreat_magnitude = min(0.25, 0.04 * agent.stalled_steps)
                if abs(agent.x - self.center_x) <= (self.core_length * 0.9):
                    retreat_magnitude *= 0.25
                retreat_force_x = -forward_sign * retreat_magnitude

            forward_push_x = (destination_x * speed) - (compression_wave * 0.45 * destination_x)
            forward_push_y = destination_y * speed * 0.38
            forward_noise = rng.uniform(-0.05, 0.05) * (0.2 + density_ratio) * max(agent.turbulence, 0.05)
            desired_vx = forward_push_x + repulsion_x + cohesion_force_x + forward_noise + agent.skill_force_x + retreat_force_x + core_attraction_force_x
            desired_vy = forward_push_y + lane_force + repulsion_y + cohesion_force_y + lateral_turbulence + shear_force + agent.skill_force_y + wall_spread_force_y
            inertia = 0.36 if scenario == "accident" else 0.24
            agent.vx = (agent.vx * inertia) + (desired_vx * (1.0 - inertia))
            agent.vy = (agent.vy * inertia) + (desired_vy * (1.0 - inertia))
            agent.x += agent.vx * self.delta_time
            agent.y += agent.vy * self.delta_time

            self._clamp_agent_position(agent, scenario, mitigation_strategy)

            # 核心区域退出阻力：高密度时适当减速但不锁死
            if self.throat_start_x <= agent.x <= self.throat_end_x:
                core_density, _ = densities.get(agent.agent_id, (0.0, 0))
                if core_density >= self.critical_density:
                    dist_to_center = abs(agent.x - self.center_x)
                    half_core = self.core_length / 2.0
                    # 降低退出阻力，让Agent能更顺畅离开
                    exit_resistance = 0.20 * (1.0 - dist_to_center / max(half_core, 1.0))
                    agent.vx *= max(0.35, 1.0 - exit_resistance)

            if scenario == "mitigation" and mitigation_strategy == "one_way_flow":
                # 单向流动：西向人群被强制减速，东向人群速度提升
                if agent.direction == "west":
                    speed *= 0.3  # 西向人群速度大幅降低
                else:
                    speed *= 1.12  # 东向人群速度提升

            current_half_width = self._corridor_half_width(agent.x, mitigation_strategy)
            if abs(agent.y) >= current_half_width - (self.agent_radius + 0.01):
                agent.vy *= 0.28
            agent.skill_force_x *= 0.58
            agent.skill_force_y *= 0.58

        self._backward_pressure_wave_vectorized(agents, densities, step)
        self._resolve_collisions_vectorized(agents, scenario, mitigation_strategy, previous_positions)

        # 出口检测：到达边界附近即标记退出
        exit_threshold = 0.5  # 调整阈值到0.5m
        for agent in agents:
            if agent.x <= exit_threshold or agent.x >= self.length - exit_threshold:
                agent.climbed_out = True

    def _clamp_agent_position(self, agent: InternalAgent, scenario: str, mitigation_strategy: str) -> None:
        agent.x = max(self.agent_radius, min(self.length - self.agent_radius, agent.x))
        current_half_width = self._corridor_half_width(agent.x, mitigation_strategy)
        if scenario == "mitigation" and self._barrier_active(mitigation_strategy) and self._within_barrier_segment(agent.x):
            lane_min, lane_max = self._barrier_bounds(agent.direction)
            agent.y = max(lane_min + self.agent_radius, min(lane_max - self.agent_radius, agent.y))
        agent.y = max(-current_half_width + self.agent_radius, min(current_half_width - self.agent_radius, agent.y))

    def _resolve_collisions(
        self,
        agents: list[InternalAgent],
        scenario: str,
        mitigation_strategy: str,
        previous_positions: dict[int, tuple[float, float]],
    ) -> None:
        for _ in range(4):
            any_overlap = False
            for index, agent in enumerate(agents):
                for other in agents[index + 1 :]:
                    pressure_blend = self._core_pressure_blend((agent.x + other.x) * 0.5, scenario, mitigation_strategy)
                    minimum_distance = self.agent_radius * (2.02 - (0.62 * pressure_blend))
                    dx = other.x - agent.x
                    dy = other.y - agent.y
                    distance = math.hypot(dx, dy)
                    if distance >= minimum_distance:
                        continue
                    any_overlap = True
                    if distance < 1e-6:
                        dx = 1.0 if (agent.agent_id + other.agent_id) % 2 == 0 else -1.0
                        dy = 0.2 if agent.agent_id % 2 == 0 else -0.2
                        distance = math.hypot(dx, dy)
                    overlap = minimum_distance - distance
                    nx = dx / distance
                    ny = dy / distance
                    separation = overlap * 0.5
                    agent.x -= nx * separation
                    agent.y -= ny * separation
                    other.x += nx * separation
                    other.y += ny * separation
                    self._clamp_agent_position(agent, scenario, mitigation_strategy)
                    self._clamp_agent_position(other, scenario, mitigation_strategy)
                    agent.vx *= 0.42
                    agent.vy *= 0.42
                    other.vx *= 0.42
                    other.vy *= 0.42
            if not any_overlap:
                break

        for index, agent in enumerate(agents):
            for other in agents[index + 1 :]:
                pressure_blend = self._core_pressure_blend((agent.x + other.x) * 0.5, scenario, mitigation_strategy)
                minimum_distance = self.agent_radius * (2.02 - (0.62 * pressure_blend))
                distance = math.dist((agent.x, agent.y), (other.x, other.y))
                if distance >= minimum_distance * 0.98:
                    continue
                agent_previous = previous_positions.get(agent.agent_id, (agent.x, agent.y))
                other_previous = previous_positions.get(other.agent_id, (other.x, other.y))
                agent_shift = math.dist(agent_previous, (agent.x, agent.y))
                other_shift = math.dist(other_previous, (other.x, other.y))
                blocked = agent if agent_shift >= other_shift else other
                blocked_previous = previous_positions.get(blocked.agent_id, (blocked.x, blocked.y))
                blocked.x, blocked.y = blocked_previous
                blocked.vx = 0.0
                blocked.vy = 0.0
                self._clamp_agent_position(blocked, scenario, mitigation_strategy)

        # 干预设施碰撞检测
        if scenario == "mitigation":
            self._resolve_intervention_collisions(agents, mitigation_strategy)

    def _resolve_intervention_collisions(
        self,
        agents: list[InternalAgent],
        mitigation_strategy: str,
    ) -> None:
        """处理人群与干预设施的碰撞检测"""
        if mitigation_strategy == "central_guardrail":
            # 中央护栏碰撞检测：人群不能穿过护栏
            for agent in agents:
                if not self._within_barrier_segment(agent.x):
                    continue
                # 东向人群只能在护栏右侧，西向人群只能在护栏左侧
                if agent.direction == "east" and agent.y < self.central_barrier_half_width + self.agent_radius:
                    # 被护栏推开
                    agent.y = self.central_barrier_half_width + self.agent_radius + 0.05
                    agent.vy = abs(agent.vy) * 0.3  # 反弹
                elif agent.direction == "west" and agent.y > -(self.central_barrier_half_width + self.agent_radius):
                    # 被护栏推开
                    agent.y = -(self.central_barrier_half_width + self.agent_radius) - 0.05
                    agent.vy = -abs(agent.vy) * 0.3  # 反弹

        elif mitigation_strategy == "one_way_flow":
            # 单向流动方向约束：西向人群被强制减速
            for agent in agents:
                if agent.direction == "west":
                    # 西向人群被强制减速，模拟单向流动
                    agent.vx *= 0.3
                    agent.vy *= 0.5
                    # 添加反向阻力
                    agent.vx -= 0.15 if agent.vx > 0 else -0.15

    def _apply_action_mapping(
        self,
        agent: InternalAgent,
        content: dict,
        agents: list[InternalAgent],
        density: float,
        step: int,
    ) -> None:
        action_text = " ".join(
            [
                str(content.get("action") or ""),
                str(content.get("dialogue") or ""),
                str(content.get("movement_hint") or ""),
            ]
        ).strip()
        if not action_text:
            return

        if re.search(r"(救|喊|呼救|求助|help)", action_text, re.IGNORECASE):
            self._shout_for_help(agent, step)

        if re.search(r"(推|挤|冲|撞|顶|扒开)", action_text, re.IGNORECASE):
            self._push(agent, agents, str(content.get("movement_hint") or ""))
            return

        if agent.typology == "group_family" and re.search(r"(一起|跟着|拉住|护住|别走散|同伴|家人|扶着)", action_text, re.IGNORECASE):
            self._follow(agent, agents, step)
            return

        if re.search(r"(贴墙|沿墙|侧身|避让|让开|腾出|扶稳|稳住|慢一点)", action_text, re.IGNORECASE):
            self._yield_sideways(agent)
            if density >= 8.5:
                self._seek_edge_escape(agent, density, step)

    def _shout_for_help(self, agent: InternalAgent, step: int) -> None:
        if not agent.last_utterance:
            agent.last_utterance = "救命，给我一点空间！"
        agent.help_beacon_until_step = step + 6
        agent.skill_force_x -= 0.04 if agent.direction == "east" else -0.04

    def _follow(self, agent: InternalAgent, agents: list[InternalAgent], step: int) -> None:
        if agent.group_id is None:
            return
        agent.support_until_step = step + 6
        agent.skill_force_x -= 0.08 if agent.direction == "east" else -0.08
        for other in agents:
            if other.group_id == agent.group_id and other.agent_id != agent.agent_id:
                other.skill_force_y += 0.04 if other.y >= agent.y else -0.04

    def _push(self, agent: InternalAgent, agents: list[InternalAgent], movement_hint: str) -> None:
        push_x, push_y = self._movement_hint_vector(agent, movement_hint)
        agent.skill_force_x += push_x * 0.45
        agent.skill_force_y += push_y * 0.36
        for other in agents:
            if other.agent_id == agent.agent_id:
                continue
            distance = math.dist((agent.x, agent.y), (other.x, other.y))
            if distance < 0.95:
                other.skill_force_x -= push_x * 0.1
                other.skill_force_y -= push_y * 0.08

    def _yield_sideways(self, agent: InternalAgent) -> None:
        edge_sign = 1.0 if agent.y >= 0 else -1.0
        agent.skill_force_y += edge_sign * (0.18 if agent.typology == "vulnerable" else 0.12)
        agent.skill_force_x -= 0.03 if agent.direction == "east" else -0.03

    def _seek_edge_escape(self, agent: InternalAgent, density: float, step: int) -> None:
        if agent.climbed_out or density < 8.5:
            return
        current_half_width = self._corridor_half_width(agent.x, None)
        wall_gap = current_half_width - abs(agent.y)
        chance = abs(math.sin((agent.agent_id * 0.73) + (step * 0.31)))
        if wall_gap <= 0.55 and chance >= 0.88:
            agent.climbed_out = True
            edge_sign = 1.0 if agent.y >= 0 else -1.0
            agent.y = edge_sign * (current_half_width - 0.08)
            agent.x += 1.0 if agent.direction == "east" else -1.0
            agent.skill_force_x += 0.35 if agent.direction == "east" else -0.35
            agent.skill_force_y += edge_sign * 0.18

    def _backward_pressure_wave(self, agents: list[InternalAgent], densities: dict[int, tuple[float, int]], step: int) -> None:
        """Propagate backward pressure from stalled agents to agents behind them."""
        for agent in agents:
            density, _ = densities.get(agent.agent_id, (0.0, 0))
            if density < self.critical_density or agent.stalled_steps < 3:
                continue

            backward_sign = -1.0 if agent.direction == "east" else 1.0
            wave_radius = 2.5 + agent.congestion_memory * 1.5

            for other in agents:
                if other.agent_id == agent.agent_id:
                    continue
                dx = other.x - agent.x
                if agent.direction == "east" and dx > 0:
                    continue
                if agent.direction == "west" and dx < 0:
                    continue

                distance = abs(dx)
                dy = abs(other.y - agent.y)
                if distance > wave_radius or dy > 1.5:
                    continue

                wave_strength = (1.0 - distance / wave_radius) * 0.12 * min(1.0, agent.stalled_steps / 5.0)
                other.skill_force_x += backward_sign * wave_strength

    def _movement_hint_vector(self, agent: InternalAgent, hint: str) -> tuple[float, float]:
        text = hint.lower()
        forward = 1.0 if agent.direction == "east" else -1.0
        lateral = 0.0
        if "left" in text or "左" in hint:
            lateral -= 1.0
        if "right" in text or "右" in hint:
            lateral += 1.0
        longitudinal = forward
        if "back" in text or "后" in hint or "退" in hint:
            longitudinal = -forward
        if "stop" in text or "停" in hint:
            longitudinal = 0.0
        return longitudinal, lateral

    def _compute_heatmap(self, agents: list[InternalAgent], scenario: str, mitigation_strategy: str) -> tuple[list[HeatCell], float, float]:
        """用 numpy 向量化热力图计算，替代 grid×agent 双重循环。"""
        del scenario
        x_steps = int(self.length / self.grid_width)
        y_steps = int(self.max_width / self.grid_height)
        sample_radius = self.local_radius
        sample_area = math.pi * (sample_radius ** 2)

        # 构建网格中心点坐标
        x_centers = np.arange(x_steps) * self.grid_width + self.grid_width / 2
        y_centers = np.arange(y_steps) * self.grid_height + self.grid_height / 2 - self.max_abs_y
        grid_x, grid_y = np.meshgrid(x_centers, y_centers, indexing="ij")  # shape: (x_steps, y_steps)
        grid_x_flat = grid_x.ravel()
        grid_y_flat = grid_y.ravel()
        n_cells = len(grid_x_flat)

        # 标记走廊外和护栏内的网格
        corridor_hw = np.array([self._corridor_half_width(float(x), mitigation_strategy) for x in grid_x_flat])
        barrier_active = self._barrier_active(mitigation_strategy)
        in_barrier_mask = np.zeros(n_cells, dtype=bool)
        if barrier_active:
            in_barrier_seg = np.array([self._within_barrier_segment(float(x)) for x in grid_x_flat])
            in_barrier_mask = in_barrier_seg & (np.abs(grid_y_flat) <= self.central_barrier_half_width)
        outside_mask = (np.abs(grid_y_flat) > corridor_hw) | in_barrier_mask

        # 计算 agent 到每个网格的距离
        if agents:
            agent_pos = np.array([[a.x, a.y] for a in agents], dtype=np.float64)  # (n_agents, 2)
            grid_pos = np.column_stack([grid_x_flat, grid_y_flat])  # (n_cells, 2)
            # 广播计算距离矩阵: (n_cells, n_agents)
            dist = np.linalg.norm(grid_pos[:, None, :] - agent_pos[None, :, :], axis=2)
            counts = np.sum(dist <= sample_radius, axis=1)
            density_flat = counts / sample_area
        else:
            density_flat = np.zeros(n_cells, dtype=np.float64)

        # 走廊外密度置零
        density_flat[outside_mask] = 0.0

        # 构建 HeatCell 列表
        heatmap: list[HeatCell] = []
        densities_list: list[float] = []
        for idx in range(n_cells):
            xi = idx // y_steps
            yi = idx % y_steps
            d = float(density_flat[idx])
            densities_list.append(d)
            heatmap.append(HeatCell(
                x=round(xi * self.grid_width, 2),
                y=round(-self.max_abs_y + yi * self.grid_height, 2),
                width=self.grid_width,
                height=self.grid_height,
                density=round(d, 2),
                level=self._risk_level(d),
            ))

        if not densities_list:
            return heatmap, 0.0, 0.0

        # 核心区域密度
        if agents:
            agent_xs = np.array([a.x for a in agents])
            agent_ys = np.array([a.y for a in agents])
            in_core = (np.abs(agent_xs - self.center_x) <= self.core_length / 2.0) & (np.abs(agent_ys) <= self.core_width / 2.0)
            core_density = float(np.sum(in_core)) / max(self.core_area, 1e-6)
        else:
            core_density = 0.0

        peak_density = max(max(densities_list), core_density)
        return heatmap, sum(densities_list) / len(densities_list), peak_density

    def _corridor_half_width(self, x_value: float, mitigation_strategy: str = None) -> float:
        if x_value <= self.funnel_start_x or x_value >= self.funnel_end_x:
            base_half_width = self.max_abs_y
        elif self.throat_start_x <= x_value <= self.throat_end_x:
            base_half_width = self.narrow_width / 2
        elif x_value < self.throat_start_x:
            blend = (x_value - self.funnel_start_x) / max(self.throat_start_x - self.funnel_start_x, 1e-6)
            width = self.max_width - ((self.max_width - self.narrow_width) * blend)
            base_half_width = width / 2
        else:
            blend = (x_value - self.throat_end_x) / max(self.funnel_end_x - self.throat_end_x, 1e-6)
            width = self.narrow_width + ((self.max_width - self.narrow_width) * blend)
            base_half_width = width / 2

        if self._widen_exits_active(mitigation_strategy):
            if x_value <= 8.0 or x_value >= 37.0:
                base_half_width += 0.95
            elif self.throat_start_x <= x_value <= self.throat_end_x:
                base_half_width += 0.35
        return min(base_half_width, self.max_abs_y + 1.05)

    def _lane_center(self, direction: str, x_value: float, scenario: str, mitigation_strategy: str = None) -> float:
        half_width = self._corridor_half_width(x_value, mitigation_strategy)
        if scenario == "mitigation" and self._barrier_active(mitigation_strategy) and self._within_barrier_segment(x_value):
            lane_bias = min(1.18, half_width * 0.8)
            return lane_bias if direction == "east" else -lane_bias
        if scenario == "mitigation" and mitigation_strategy == "one_way_flow":
            return 0.12 if direction == "east" else -0.12
        if scenario == "accident":
            # 修复：增大lane_bias范围，让人群能够向两侧扩散占满走廊
            # 根据数据集SP-004：巷道宽度3.2m-6m，需要让人群占满整个宽度
            lane_bias = min(0.85, half_width * 0.45)
            # 高密度时人群应该向两侧墙壁扩散，而不是挤在中间
            lane_bias *= max(0.6, 1.0 - (self._overload_blend() * 0.3))
            return lane_bias if direction == "east" else -lane_bias
        lane_bias = min(0.65, half_width * 0.35)
        if self.current_overload_ratio > 1.0:
            lane_bias *= 1.0 - (self._overload_blend() * 0.5)
        return lane_bias if direction == "east" else -lane_bias

    def _sample_spawn_count(
        self,
        budget: float,
        rng: random.Random,
        scenario: str,
        step: int,
        direction: str,
    ) -> int:
        if budget < 0.25:
            return 0
        pulse = self._crowd_tide_multiplier(step, direction, scenario)
        burst_bias = self._value_noise((step * 0.65) + (0.0 if direction == "east" else 7.0))
        effective_budget = budget * pulse
        base = int(effective_budget)
        fractional = max(0.0, effective_budget - base)
        count = base
        if rng.random() < fractional:
            count += 1
        if scenario == "accident":
            if burst_bias > 0.7 and budget > 1.2:
                count += 1
            if burst_bias > 0.86 and budget > 1.8:
                count += 1
        return min(count, max(1, int(budget * 1.2) + 1))

    def _sample_spawn_point(
        self,
        direction: str,
        rng: random.Random,
        scenario: str,
        agents: list[InternalAgent],
    ) -> tuple[float | None, float | None]:
        if direction == "east":
            x_min, x_max = 0.25, 0.85
        else:
            x_min, x_max = self.length - 0.85, self.length - 0.25

        y_center = self._sample_spawn_band(direction, scenario, rng)
        for _ in range(14):
            spawn_x = rng.uniform(x_min, x_max)
            spawn_half_width = self._corridor_half_width(spawn_x, None)
            spawn_y = y_center + rng.uniform(-0.08, 0.08)
            spawn_y = max(-spawn_half_width + self.agent_radius, min(spawn_half_width - self.agent_radius, spawn_y))
            if self._can_spawn(agents, spawn_x, spawn_y):
                return spawn_x, spawn_y
        return None, None

    def _sample_spawn_band(self, direction: str, scenario: str, rng: random.Random) -> float:
        if scenario in {"baseline", "accident"} and self.current_overload_ratio > 1.0:
            center_pull = 1.0 - self._overload_blend()
            edge_center = self.spawn_cluster_centers[direction][0]
            return (edge_center * center_pull) + (rng.uniform(-0.12, 0.12) * (1.0 - center_pull))
        edge_center = self.spawn_cluster_centers[direction][0]
        return edge_center + rng.uniform(-0.06, 0.06)

    def _target_band(self, direction: str, scenario: str, rng: random.Random) -> float:
        if scenario == "mitigation":
            return 0.76 if direction == "east" else -0.76
        if self.current_overload_ratio > 1.0:
            # 修复：增大目标带范围，让人群能够向墙壁方向移动
            # 根据数据集SP-004：巷道宽度3.2m-6m，半宽1.6m-3m
            center_span = max(0.4, 0.55 * (1.0 - (self._overload_blend() * 0.3)))
            return rng.uniform(-center_span, center_span)
        if scenario == "accident":
            # 修复：增大事故场景的目标带范围，让人群分散到整个走廊
            return rng.uniform(-0.55, 0.55)
        return 0.42 if direction == "east" else -0.42

    def _crowd_tide_multiplier(self, step: int, direction: str, scenario: str) -> float:
        if scenario == "baseline":
            return 1.0
        phase = 0.0 if direction == "east" else 1.7
        slow_wave = 1.0 + (0.24 * math.sin((step * 0.52) + phase))
        fast_wave = 1.0 + (0.18 * math.sin((step * 1.13) + (phase * 1.9)))
        noise_wave = 0.9 + (0.35 * self._value_noise((step * 0.41) + phase + 3.0))
        tide = slow_wave * fast_wave * noise_wave
        if scenario == "accident":
            early_surge = 1.0 + (0.22 * max(0.0, 1.0 - (step / 70.0)))
            return max(0.72, min(2.08, tide * early_surge))
        return max(0.8, min(1.25, tide))

    def _value_noise(self, sample: float) -> float:
        left = math.floor(sample)
        right = left + 1
        fraction = sample - left
        smooth = fraction * fraction * (3.0 - (2.0 * fraction))
        left_value = self._hash_noise(left)
        right_value = self._hash_noise(right)
        return left_value + ((right_value - left_value) * smooth)

    def _hash_noise(self, index: int) -> float:
        value = math.sin((index * 127.1) + (index * index * 0.0137)) * 43758.5453
        return value - math.floor(value)

    def _risk_level(self, density: float) -> str:
        if density >= self.fatal_density_min:
            return "fatal"
        if density >= self.critical_density:
            return "danger"
        if density >= self.safe_density_limit:
            return "warning"
        return "safe"

    def _to_agent_state(self, agent: InternalAgent, density: float) -> AgentState:
        summaries = self._generate_agent_summary(agent, density)
        return AgentState(
            id=agent.agent_id,
            x=round(agent.x, 2),
            y=round(agent.y, 2),
            direction="east" if agent.direction == "east" else "west",
            risk=self._risk_level(density),
            slow_brain_active=agent.slow_brain_active,
            typology=agent.typology,
            broadcast_radius=round(agent.broadcast_radius, 2),
            profile_label=summaries["profile"],
            perception_summary=summaries["perception"],
            emotion_summary=summaries["emotion"],
            intention_summary=summaries["intention"],
            action_summary=summaries["action"],
        )

    def _generate_agent_summary(self, agent: InternalAgent, density: float) -> dict[str, str]:
        profile = agent.profile_label if agent.profile_label else self._profile_label(agent.typology)
        risk = self._risk_level(density)
        speed = math.hypot(agent.vx, agent.vy) / self.delta_time
        direction_label = "东行" if agent.direction == "east" else "西行"
        rng = random.Random(agent.agent_id * 31 + int(density * 100))

        # 如果有慢脑摘要，优先使用
        if agent.last_slow_summary:
            fallback_emotion = rng.choice([
                "紧张上升，担心被挤倒", "焦虑弥漫，呼吸变得急促",
                "警觉度飙升，全身紧绷", "不安加剧，但仍努力保持镇定",
            ]) if density >= self.critical_density else rng.choice([
                "保持警觉，情绪基本稳定", "略有紧张，但可控",
                "警觉地观察四周", "情绪平稳，随时准备应变",
            ])
            fallback_intention = rng.choice([
                f"沿{direction_label}方向寻找通行空间",
                f"试图从侧面脱离拥堵区",
                f"继续{direction_label}，寻找缝隙前进",
            ]) if density >= self.safe_density_limit else rng.choice([
                f"继续{direction_label}稳步前进",
                f"沿当前方向保持前进",
            ])
            fallback_action = agent.last_utterance[:25] if agent.last_utterance else rng.choice([
                "跟随局部空隙缓慢移动", "侧身避让，小步前进",
                "观察前方节奏，伺机移动",
            ])
            return {
                "profile": profile,
                "perception": agent.last_slow_summary[:30],
                "emotion": fallback_emotion,
                "intention": fallback_intention,
                "action": fallback_action,
            }

        # 按身份×密度组合生成多样化标签
        if density >= self.stampede_density:
            if agent.typology == "vulnerable":
                perception = rng.choice(["被人群完全吞没，视线里全是后背", "身体被四面八方的力挤压，几乎站不稳", "双脚快离地了，完全失去自主行动能力"])
                emotion = rng.choice(["极度恐惧，拼命想抓住什么", "恐慌蔓延，眼眶发酸", "吓得浑身发抖，但不敢哭出来"])
                intention = rng.choice(["只想活下来，前进已经不重要了", "拼命想往墙边靠但根本动不了", "试图护住胸口保持呼吸"])
                action = rng.choice(["双手护胸，用尽全力维持站姿", "蜷缩身体减少受力面积", "紧紧抓住旁边人的衣服不放"])
            elif agent.typology == "group_family":
                perception = rng.choice(["人流像潮水一样把我们裹在中间", "和同伴被挤得只能侧身贴着走", "周围全是人，同伴的身影时隐时现"])
                emotion = rng.choice(["最怕和同伴走散，比自己出事更慌", "一边护着同伴一边强撑着不倒", "心提到嗓子眼，手心全是冷汗"])
                intention = rng.choice(["死也不能松开同伴的手", "用身体给同伴挡出一点空间", "带着同伴往边缘方向一点点蹭"])
                action = rng.choice(["一只手紧握同伴手腕，另一只手挡人流", "把同伴护在身后自己面对挤压", "和同伴背靠背互相支撑"])
            else:
                perception = rng.choice(["被挤得喘不上气，周围全是人墙", "身体完全不受控制地随人流摆动", "视线被挡死，只能看到前面人的后脑勺"])
                emotion = rng.choice(["肾上腺素飙升，高度警觉", "后悔走进来但现在退不出去", "恐惧感一阵阵袭来"])
                intention = rng.choice(["先活下来再说，不指望能前进", "护住要害等待挤压波过去", "想办法侧移到压力小的区域"])
                action = rng.choice(["收紧核心压低重心碎步移动", "侧身用肩膀扛着人流压力", "放弃前进专注维持平衡"])
        elif density >= self.critical_density:
            if agent.typology == "vulnerable":
                perception = rng.choice(["人群越来越密，呼吸开始困难", "两侧的人贴着我的肩膀，膝盖开始发软", "每走一步都要用力撑住，很怕摔倒"])
                emotion = rng.choice(["焦虑加剧，手心冒汗", "心里很慌但不敢表现出来", "努力控制呼吸让自己冷静"])
                intention = rng.choice(["想贴着墙边慢慢走", "找一个稍微宽敞的地方喘口气", "按自己能承受的节奏走，不跟人流"])
                action = rng.choice(["一手扶墙一手护住身侧", "放慢步伐给自己留反应空间", "侧身让后面的人先过"])
            elif agent.typology == "group_family":
                perception = rng.choice(["人流把我们挤得只能肩并肩挪动", "同伴被挤得一直在回头看我", "空间越来越小，快没法并排走了"])
                emotion = rng.choice(["担心同伴撑不住", "攥着同伴的手不敢松", "一边走一边确认同伴还在身后"])
                intention = rng.choice(["拉着同伴往墙边靠", "改成前后走减少横向占位", "找缝隙带着同伴侧移"])
                action = rng.choice(["握着同伴手腕走在前面", "用身体给同伴挡出空间", "放慢速度跟同伴保持同节奏"])
            else:
                perception = rng.choice(["前方人群密集，移动越来越困难", "挤压波一波接一波，身体不由自主前倾", "身边的人开始互相推搡"])
                emotion = rng.choice(["开始认真考虑往墙边靠", "盘算着还有多远能通过", "有些烦躁但不敢催"])
                intention = rng.choice(["往墙边靠减少四面受力", "从侧面绕过最堵的区域", "等人流松动了再走"])
                action = rng.choice(["侧身从缝隙中挤过去", "碎步跟着前面人的节奏", "放弃正面突围改走边缘"])
        elif density >= self.safe_density_limit:
            if agent.typology == "vulnerable":
                if agent.local_blocked:
                    perception = rng.choice(["前面堵住了，只能停下来等", "前方不动了，我也不敢往前挤"])
                    emotion = rng.choice(["有点紧张但还在控制范围内", "不耐烦但只能等着"])
                    intention = rng.choice(["等前面通了再走", "贴着墙边等，不跟人挤"])
                    action = rng.choice(["原地等待，扶着墙保持平衡", "左右张望寻找侧移空间"])
                else:
                    perception = rng.choice(["人流开始变密了，要小心", "身边的人越来越多，要注意安全"])
                    emotion = rng.choice(["开始紧张了", "有点不安但还能应付"])
                    intention = rng.choice(["贴着墙边慢慢走", "放慢步伐留出反应空间"])
                    action = rng.choice(["侧身避让，保持低速", "扶墙缓步前行"])
            elif agent.typology == "group_family":
                if agent.local_blocked:
                    perception = rng.choice(["前面堵了，跟同伴说等一下", "走不动了，先稳住"])
                    emotion = rng.choice(["有点急但不能表现出来", "还好同伴在身边"])
                    intention = rng.choice(["跟同伴一起等", "先稳住再说"])
                    action = rng.choice(["拉住同伴原地等待", "跟同伴肩并肩站稳"])
                else:
                    perception = rng.choice(["人流变密了，跟同伴贴紧走", "还能并排走但空间在变窄"])
                    emotion = rng.choice(["提醒同伴注意脚下", "保持警觉"])
                    intention = rng.choice(["跟同伴保持并排", "注意不走散"])
                    action = rng.choice(["拉着同伴的手腕走", "放慢速度跟同伴同步"])
            else:
                if agent.local_blocked:
                    perception = rng.choice(["前方拥堵，暂时走不动", "前面的人停了，后面还在涌"])
                    emotion = rng.choice(["有些不耐烦", "烦躁但只能等"])
                    intention = rng.choice(["等人流松动", "观察有没有侧移空间"])
                    action = rng.choice(["原地等待左右张望", "低头看手机打发时间"])
                else:
                    perception = rng.choice(["人流较多但还能走", "前方密度在上升但还能移动"])
                    emotion = rng.choice(["略有紧张但可控", "保持警觉观察四周"])
                    intention = rng.choice([f"继续{direction_label}避开密集区", "跟着人流节奏走"])
                    action = rng.choice(["跟随前方人群缓慢移动", "保持步速不掉队"])
        else:
            if agent.typology == "vulnerable":
                if speed < 0.3:
                    perception = rng.choice(["目前还算通畅", "人流不密，可以正常走"])
                    emotion = rng.choice(["情绪平稳", "放松但保持注意"])
                    intention = rng.choice([f"继续{direction_label}稳步前进", "贴着墙边安心走"])
                    action = rng.choice(["正常步速行走", "偶尔侧身让后面的人先过"])
                else:
                    perception = rng.choice(["前方可通行", "人流正常"])
                    emotion = rng.choice(["保持警觉", "情绪基本稳定"])
                    intention = rng.choice([f"继续{direction_label}", "保持当前方向"])
                    action = rng.choice(["缓慢移动", "跟着人流走"])
            elif agent.typology == "group_family":
                if speed < 0.3:
                    perception = rng.choice(["跟同伴边走边聊", "气氛还算轻松"])
                    emotion = rng.choice(["心情不错", "放松"])
                    intention = rng.choice(["继续跟同伴一起走", "享受这段还算顺畅的路"])
                    action = rng.choice(["边走边聊天", "正常步速前进"])
                else:
                    perception = rng.choice(["前方可通行", "人流正常"])
                    emotion = rng.choice(["保持警觉", "留意同伴位置"])
                    intention = rng.choice([f"继续{direction_label}", "跟同伴保持同步"])
                    action = rng.choice(["跟着人流走", "保持步速"])
            else:
                if speed < 0.3:
                    perception = rng.choice(["前方基本通畅", "人流稀疏"])
                    emotion = rng.choice(["保持警觉，情绪基本稳定", "放松地走着"])
                    intention = rng.choice([f"继续沿{direction_label}方向稳步前进", "保持当前节奏"])
                    action = rng.choice(["正常步速行走", "轻松前进"])
                else:
                    perception = rng.choice(["前方可通行", "人流正常但前方有减速趋势"])
                    emotion = rng.choice(["保持警觉", "略有紧张"])
                    intention = rng.choice([f"继续沿{direction_label}方向前进", "保持前进"])
                    action = rng.choice(["跟随局部空隙缓慢移动", "跟着前面的人走"])

        return {
            "profile": profile,
            "perception": perception,
            "emotion": emotion,
            "intention": intention,
            "action": action,
        }

    def _fruin_level(self, density: float) -> str:
        if density < 0.31:
            return "A"
        if density < 0.43:
            return "B"
        if density < 0.72:
            return "C"
        if density < 1.08:
            return "D"
        if density < 2.17:
            return "E"
        return "F"

    def _detect_vortex(self, agents: list[InternalAgent]) -> bool:
        east_center_count = 0
        west_center_count = 0
        for agent in agents:
            if 18.0 <= agent.x <= 27.0 and abs(agent.y) <= 0.9:
                if agent.direction == "east":
                    east_center_count += 1
                else:
                    west_center_count += 1
        return east_center_count >= 6 and west_center_count >= 6

    def _detect_deadlock(self, agents: list[InternalAgent], densities: dict[int, tuple[float, int]]) -> bool:
        stuck_count = 0
        for agent in agents:
            if 18.0 <= agent.x <= 27.0 and densities.get(agent.agent_id, (0.0, 0))[0] >= 5.2:
                stuck_count += 1
        return stuck_count >= 10


simulation_service = SimulationService()

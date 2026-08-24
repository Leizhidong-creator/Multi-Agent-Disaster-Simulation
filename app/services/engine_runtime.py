from __future__ import annotations

from app.engine.llm import LLMDecisionMaker
from app.engine.sandbox import AgentSpawner, SandboxEnvironment
from app.models.schemas import EngineLogPreview, EngineRunRequest, EngineRunResponse, EngineRunSummary


class EngineRuntimeService:
    def describe_layout(self) -> dict:
        env = SandboxEnvironment(spawner=None)
        return env.get_layout_profile()

    async def run(self, request: EngineRunRequest) -> EngineRunResponse:
        env = SandboxEnvironment(
            spawner=AgentSpawner(
                arrival_rate_left=request.arrival_rate_left,
                arrival_rate_right=request.arrival_rate_right,
                distribution=request.distribution,
                seed=42,
            )
        )
        decision_maker = LLMDecisionMaker() if request.use_slow_brain else None

        peak_density = 0.0
        max_local_density = 0.0
        frozen_step_count = 0
        slow_brain_request_total = 0
        slow_brain_log_total = 0
        total_spawned = 0
        total_exited = 0
        latest_logs: list[EngineLogPreview] = []

        for _ in range(request.duration_steps):
            if decision_maker is None:
                snapshot = env.step(request.dt)
            else:
                snapshot = await env.step_async(request.dt, decision_maker=decision_maker)

            peak_density = max(peak_density, snapshot.peak_density)
            max_local_density = max(max_local_density, snapshot.max_local_density)
            total_spawned += snapshot.spawned_agents
            total_exited += snapshot.exited_agents
            slow_brain_request_total += snapshot.slow_brain_request_count
            slow_brain_log_total += len(snapshot.slow_brain_logs)
            if snapshot.frozen_this_step:
                frozen_step_count += 1
            if snapshot.slow_brain_logs:
                latest_logs.extend(
                    EngineLogPreview(
                        step_index=entry.step_index,
                        agent_id=entry.agent_id,
                        density=entry.density,
                        action=entry.action,
                        rationale=entry.rationale,
                    )
                    for entry in snapshot.slow_brain_logs
                )
                latest_logs = latest_logs[-8:]

        return EngineRunResponse(
            summary=EngineRunSummary(
                duration_steps=request.duration_steps,
                dt=request.dt,
                peak_density=round(peak_density, 3),
                max_local_density=round(max_local_density, 3),
                frozen_step_count=frozen_step_count,
                slow_brain_request_total=slow_brain_request_total,
                slow_brain_log_total=slow_brain_log_total,
                total_spawned=total_spawned,
                total_exited=total_exited,
                final_active_agents=len(env.agents),
            ),
            latest_logs=latest_logs,
        )


engine_runtime_service = EngineRuntimeService()

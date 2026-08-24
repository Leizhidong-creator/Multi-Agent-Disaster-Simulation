from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.engine.sandbox import AgentSpawner, SandboxEnvironment


@dataclass(slots=True)
class StubDecision:
    agent_id: int
    action: str
    rationale: str
    displacement: tuple[float, float]


class StubDecisionMaker:
    async def decide_many(self, requests: list[dict]) -> list[StubDecision]:
        tasks = [self._decide_single(request) for request in requests]
        return list(await asyncio.gather(*tasks))

    async def _decide_single(self, request: dict) -> StubDecision:
        await asyncio.sleep(0)
        density = float(request["density"])
        agent_id = int(request["agent_id"])
        position = request.get("position") or (0.0, 0.0)
        y_pos = float(position[1])
        lateral = -0.28 if y_pos > 1.6 else 0.28
        if density >= 7.0:
            action = "step_back"
            displacement = (-0.35, lateral * 0.5)
            rationale = "density spike detected, create breathing space before re-entering the flow"
        elif y_pos > 1.6:
            action = "shift_left"
            displacement = (0.15, -0.32)
            rationale = "move away from central head-on pressure"
        else:
            action = "shift_right"
            displacement = (0.15, 0.32)
            rationale = "move away from central head-on pressure"
        return StubDecision(
            agent_id=agent_id,
            action=action,
            rationale=rationale,
            displacement=displacement,
        )


async def main() -> None:
    sync_env = SandboxEnvironment(
        spawner=AgentSpawner(
            arrival_rate_left=5.0,
            arrival_rate_right=5.0,
            distribution="poisson",
            seed=7,
        )
    )
    sync_snapshot = None
    for _ in range(5):
        sync_snapshot = sync_env.step(0.2)
    print(
        "sync",
        sync_snapshot.step_index,
        sync_snapshot.active_agents,
        sync_snapshot.peak_density,
    )

    async_env = SandboxEnvironment(
        spawner=AgentSpawner(
            arrival_rate_left=7.0,
            arrival_rate_right=7.0,
            distribution="poisson",
            seed=9,
        )
    )
    decision_maker = StubDecisionMaker()
    async_snapshot = None
    slow_log_count = 0
    for _ in range(12):
        async_snapshot = await async_env.step_async(0.2, decision_maker=decision_maker)
        slow_log_count += len(async_snapshot.slow_brain_logs)
    print(
        "async",
        async_snapshot.step_index,
        async_snapshot.active_agents,
        async_snapshot.peak_density,
        slow_log_count,
    )


if __name__ == "__main__":
    asyncio.run(main())

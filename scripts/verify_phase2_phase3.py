from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.engine.sandbox import Agent, AgentSpawner, SandboxEnvironment


@dataclass(slots=True)
class StubDecision:
    agent_id: int
    action: str
    rationale: str
    displacement: tuple[float, float]


class StubDecisionMaker:
    def __init__(self) -> None:
        self.request_batches: list[int] = []

    async def decide_many(self, requests: list[dict]) -> list[StubDecision]:
        self.request_batches.append(len(requests))
        await asyncio.sleep(0)
        return [
            StubDecision(
                agent_id=int(request["agent_id"]),
                action="shift_right",
                rationale="stub slow-brain decision for verification",
                displacement=(0.15, 0.35),
            )
            for request in requests
        ]


def verify_local_perception() -> None:
    env = SandboxEnvironment(spawner=None)
    anchor = Agent(agent_id=1, x=0.75, y=1.6, target=env.right_exit)
    near = Agent(agent_id=2, x=1.15, y=1.62, target=env.right_exit)
    far = Agent(agent_id=3, x=3.9, y=1.6, target=env.right_exit)
    env.register_agent(anchor)
    env.register_agent(near)
    env.register_agent(far)

    perception = json.loads(anchor.get_local_perception(env))
    nearby_ids = [item["id"] for item in perception["nearby_agents"]]
    assert 2 in nearby_ids, "局域感知未包含近邻 Agent"
    assert 3 not in nearby_ids, "局域感知错误泄露了远处 Agent"
    assert isinstance(perception["local_obstacles"], list), "局部障碍物字段格式错误"
    assert perception["view_radius_m"] == 1.5, "视野半径未正确序列化"
    print("phase2.local_perception ok", len(perception["local_obstacles"]), nearby_ids)


async def verify_async_slow_brain() -> None:
    env = SandboxEnvironment(
        slow_brain_threshold=2.5,
        density_radius_m=0.75,
        spawner=AgentSpawner(
            arrival_rate_left=9.0,
            arrival_rate_right=9.0,
            distribution="uniform",
            seed=17,
        ),
    )
    decision_maker = StubDecisionMaker()
    frozen_hits = 0
    request_hits = 0
    log_hits = 0

    for _ in range(16):
        snapshot = await env.step_async(0.2, decision_maker=decision_maker)
        if snapshot.frozen_this_step:
            frozen_hits += 1
        if snapshot.slow_brain_request_count > 0:
            request_hits += snapshot.slow_brain_request_count
        if snapshot.slow_brain_logs:
            log_hits += len(snapshot.slow_brain_logs)

    assert frozen_hits > 0, "慢脑触发后未记录物理时间冻结"
    assert request_hits > 0, "慢脑请求数始终为 0"
    assert log_hits > 0, "慢脑日志未生成"
    assert decision_maker.request_batches, "异步决策器未被调用"
    print("phase3.async_slow_brain ok", frozen_hits, request_hits, log_hits, decision_maker.request_batches[-3:])


def verify_spawner_distribution() -> None:
    env = SandboxEnvironment(
        spawner=AgentSpawner(
            arrival_rate_left=4.0,
            arrival_rate_right=3.0,
            distribution="poisson",
            seed=21,
        )
    )
    total_spawned = 0
    for _ in range(10):
        snapshot = env.step(0.2)
        total_spawned += snapshot.spawned_agents
    assert total_spawned > 0, "泊松分布客流生成器未生成任何 Agent"
    print("phase1.spawner ok", total_spawned, snapshot.active_agents, snapshot.max_local_density)


async def main() -> None:
    verify_local_perception()
    verify_spawner_distribution()
    await verify_async_slow_brain()
    print("phase2_phase3 verification passed")


if __name__ == "__main__":
    asyncio.run(main())

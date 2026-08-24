from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.desktop.main_window import ZhiyanMainWindow, create_application
from app.engine.sandbox import AgentSpawner, SandboxEnvironment


async def build_snapshot() -> tuple[SandboxEnvironment, object]:
    env = SandboxEnvironment(
        slow_brain_threshold=2.8,
        density_radius_m=0.75,
        spawner=AgentSpawner(
            arrival_rate_left=8.0,
            arrival_rate_right=7.0,
            distribution="uniform",
            seed=11,
        ),
    )
    for _ in range(10):
        snapshot = env.step(0.2)
    return env, snapshot


async def main() -> None:
    env, snapshot = await build_snapshot()
    app = create_application()
    window = ZhiyanMainWindow()
    window.canvas.render_snapshot(snapshot, env)
    window._toggle_mitigation_overlay(True)
    window.canvas.render_snapshot(snapshot, env)
    app.processEvents()

    profile = env.get_layout_profile()
    assert profile["scene_name"], "场景语义配置为空"
    assert len(profile["corridor_polygon"]) >= 4, "平面拓扑多边形不足"
    assert window.canvas.show_mitigation is True, "整改叠加层未启用"
    assert snapshot.active_agents > 0, "桌面验证快照中没有 Agent"

    print(
        "phase5.desktop ok",
        profile["scene_name"],
        snapshot.active_agents,
        snapshot.peak_density,
        len(profile["mitigation_barriers"]),
    )


if __name__ == "__main__":
    asyncio.run(main())

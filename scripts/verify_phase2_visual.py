from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

from app.models.schemas import SimulationRequest
from app.services.simulation import simulation_service


OUTPUT_PATH = ROOT_DIR / "artifacts" / "phase2_visual_distribution.png"


def _agent_color(agent: object) -> str:
    if getattr(agent, "slow_brain_active", False):
        return "#b46a6a"
    if getattr(agent, "direction", "") == "east":
        return "#7170ff"
    return "#b7c0cb"


def _draw_corridor(ax: plt.Axes) -> None:
    x_values = [index * 0.25 for index in range(int(simulation_service.length / 0.25) + 1)]
    upper = [simulation_service._corridor_half_width(x) for x in x_values]
    lower = [-value for value in upper]
    ax.plot(x_values, upper, color="#d0d6e0", linewidth=1.0)
    ax.plot(x_values, lower, color="#d0d6e0", linewidth=1.0)
    ax.fill_between(x_values, lower, upper, color="#17181a", alpha=0.95)
    ax.axvspan(18.0, 27.0, color="#6f3f3f", alpha=0.12)


async def main() -> None:
    request = SimulationRequest(
        scenario="accident",
        max_agents=96,
        duration_steps=60,
        use_api=False,
        arrival_rate_north=2.5,
        arrival_rate_south=2.5,
    )
    response = await simulation_service.run(request)
    output_dir = OUTPUT_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    target_steps = [0, 11, 23, 35, 47, 59]
    figure, axes = plt.subplots(2, 3, figsize=(16, 8), facecolor="#0a0a0a")
    figure.suptitle(
        "Itaewon crowd distribution audit (duration_steps=60)",
        color="#f7f8f8",
        fontsize=14,
    )

    for ax, step in zip(axes.flatten(), target_steps, strict=False):
        frame = response.frames[step]
        agents = frame.agents
        x_values = [agent.x for agent in agents]
        y_values = [agent.y for agent in agents]
        colors = [_agent_color(agent) for agent in agents]

        ax.set_facecolor("#0a0a0a")
        _draw_corridor(ax)
        ax.scatter(x_values, y_values, c=colors, s=26, alpha=0.82, linewidths=0.0)
        ax.set_xlim(0.0, simulation_service.length)
        ax.set_ylim(-simulation_service.max_abs_y, simulation_service.max_abs_y)
        ax.set_title(
            f"step={step:02d} peak={frame.stats.peak_density:.2f}",
            color="#f7f8f8",
            fontsize=11,
        )
        ax.tick_params(colors="#8a8f98", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#8a8f98")
            spine.set_linewidth(0.8)
        ax.set_xlabel("corridor x (m)", color="#8a8f98", fontsize=8)
        ax.set_ylabel("lateral y (m)", color="#8a8f98", fontsize=8)

    figure.tight_layout(rect=(0.0, 0.02, 1.0, 0.95))
    figure.savefig(OUTPUT_PATH, dpi=180, facecolor=figure.get_facecolor())
    plt.close(figure)

    peak_frame = max(response.frames, key=lambda item: item.stats.peak_density)
    peak_agents = peak_frame.agents
    center_cluster = [agent for agent in peak_agents if 18.0 <= agent.x <= 27.0 and abs(agent.y) <= 1.2]
    print(
        "phase2.visual ok",
        f"saved={OUTPUT_PATH}",
        f"peak_step={peak_frame.step}",
        f"peak_density={peak_frame.stats.peak_density:.2f}",
        f"center_cluster={len(center_cluster)}",
        f"slow_brain_triggers={response.summary.slow_brain_triggers}",
    )


if __name__ == "__main__":
    asyncio.run(main())

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
import numpy as np
from matplotlib.lines import Line2D

from app.models.schemas import SimulationRequest
from app.services.simulation import simulation_service


OUTPUT_PATH = ROOT_DIR / "docs" / "assets" / "crowd-distribution-audit.png"


def _draw_corridor(ax: plt.Axes) -> None:
    x_values = [index * 0.25 for index in range(int(simulation_service.length / 0.25) + 1)]
    upper = [simulation_service._corridor_half_width(x) for x in x_values]
    lower = [-value for value in upper]
    ax.fill_between(x_values, lower, upper, color="#F5F7FA", zorder=0)
    ax.plot(x_values, upper, color="#657180", linewidth=1.15, zorder=4)
    ax.plot(x_values, lower, color="#657180", linewidth=1.15, zorder=4)
    ax.axvspan(18.0, 27.0, color="#E69F00", alpha=0.08, zorder=1)


def _density_grid(agents: list[object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_values = [agent.x for agent in agents]
    y_values = [agent.y for agent in agents]
    return np.histogram2d(
        x_values,
        y_values,
        bins=(45, 24),
        range=((0.0, simulation_service.length), (-simulation_service.max_abs_y, simulation_service.max_abs_y)),
    )


async def main() -> None:
    request = SimulationRequest(
        scenario="accident",
        max_agents=96,
        duration_steps=60,
        use_api=False,
        random_seed=22,
        arrival_rate_north=4.5,
        arrival_rate_south=4.5,
    )
    response = await simulation_service.run(request)
    output_dir = OUTPUT_PATH.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    target_steps = [0, 19, 39, 59]
    selected_frames = [response.frames[step] for step in target_steps]
    density_grids = [_density_grid(frame.agents) for frame in selected_frames]
    density_max = max(float(grid[0].max()) for grid in density_grids)

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 10,
            "axes.edgecolor": "#A8B2C1",
            "axes.labelcolor": "#344054",
            "xtick.color": "#667085",
            "ytick.color": "#667085",
        }
    )
    figure, axes = plt.subplots(1, 4, figsize=(18, 4.6), sharex=True, sharey=True, facecolor="white")
    figure.suptitle(
        "Spatial Evolution through the Bottleneck",
        x=0.06,
        y=0.98,
        ha="left",
        color="#17202A",
        fontsize=20,
        fontweight="bold",
    )
    figure.text(0.06, 0.905, "Fixed-seed crowd simulation · 96 Agent capacity · 60 steps", color="#667085", fontsize=11.5)

    for index, (ax, step, frame, density_data) in enumerate(zip(axes, target_steps, selected_frames, density_grids, strict=True)):
        agents = frame.agents
        heat, x_edges, y_edges = density_data
        ax.set_facecolor("white")
        _draw_corridor(ax)
        ax.imshow(
            heat.T,
            extent=(x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]),
            origin="lower",
            aspect="auto",
            cmap="YlOrRd",
            vmin=0.0,
            vmax=max(density_max, 1.0),
            alpha=0.20,
            interpolation="bilinear",
            zorder=2,
        )
        groups = (
            ([agent for agent in agents if agent.direction == "east" and not agent.slow_brain_active], "#0072B2", "o"),
            ([agent for agent in agents if agent.direction == "west" and not agent.slow_brain_active], "#7B8794", "s"),
            ([agent for agent in agents if agent.slow_brain_active], "#D55E00", "D"),
        )
        for group, color, marker in groups:
            ax.scatter(
                [agent.x for agent in group],
                [agent.y for agent in group],
                c=color,
                marker=marker,
                s=28,
                alpha=0.88,
                edgecolors="white",
                linewidths=0.45,
                zorder=5,
            )
        ax.set_xlim(0.0, simulation_service.length)
        ax.set_ylim(-simulation_service.max_abs_y, simulation_service.max_abs_y)
        ax.set_title(
            f"{chr(97 + index)}   t = {step}  |  peak = {frame.stats.peak_density:.2f}",
            loc="left",
            color="#17202A",
            fontsize=12,
            fontweight="bold",
            pad=10,
        )
        ax.text(22.5, 2.70, "Bottleneck Region", color="#A45713", fontsize=8.5, ha="center", va="top", zorder=6)
        ax.annotate("", xy=(12.5, 2.45), xytext=(4.0, 2.45), arrowprops={"arrowstyle": "->", "color": "#0072B2", "lw": 1.4})
        ax.annotate("", xy=(32.5, -2.45), xytext=(41.0, -2.45), arrowprops={"arrowstyle": "->", "color": "#7B8794", "lw": 1.4})
        ax.set_xlabel("Corridor position x (m)", fontsize=9.5)
        if index == 0:
            ax.set_ylabel("Lateral position y (m)", fontsize=9.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=8.5)

    legend_handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#0072B2", markeredgecolor="white", markersize=7, label="Eastbound"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#7B8794", markeredgecolor="white", markersize=7, label="Westbound"),
    ]
    if any(agent.slow_brain_active for frame in selected_frames for agent in frame.agents):
        legend_handles.append(
            Line2D([0], [0], marker="D", color="none", markerfacecolor="#D55E00", markeredgecolor="white", markersize=7, label="Slow Brain activated")
        )
    figure.legend(handles=legend_handles, loc="lower center", bbox_to_anchor=(0.53, 0.01), ncol=3, frameon=False, fontsize=10)
    figure.text(0.945, 0.035, "Heat layer: local occupancy", ha="right", color="#667085", fontsize=9.5)
    figure.tight_layout(rect=(0.04, 0.10, 0.99, 0.84), w_pad=1.4)
    figure.savefig(OUTPUT_PATH, dpi=220, facecolor="white", bbox_inches="tight", pad_inches=0.12)
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

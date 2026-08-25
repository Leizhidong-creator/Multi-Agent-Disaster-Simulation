"""Generate deterministic publication assets for the project README.

All quantitative figures read checked-in JSON results. The script has no
network dependency and never reads environment variables or API credentials.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
ICONS = ASSETS / "icons"
RESULTS = ROOT / "docs" / "results"

COLORS = {
    "ink": "#17202A",
    "muted": "#667085",
    "line": "#A8B2C1",
    "paper": "#FFFFFF",
    "panel": "#F7F9FC",
    "blue": "#2878B5",
    "blue_dark": "#174A73",
    "blue_pale": "#EAF3FA",
    "teal": "#148A8A",
    "teal_pale": "#E7F5F3",
    "orange": "#C96732",
    "orange_pale": "#FFF1E8",
    "red": "#B94444",
    "red_pale": "#FBECEC",
    "green": "#2E7D5B",
    "green_pale": "#EAF5EF",
}


def _configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Noto Sans SC", "DejaVu Sans"],
            "font.size": 15,
            "axes.titlesize": 21,
            "axes.labelsize": 14,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": COLORS["line"],
            "axes.linewidth": 0.9,
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "text.color": COLORS["ink"],
            "figure.facecolor": COLORS["paper"],
            "axes.facecolor": COLORS["paper"],
            "savefig.facecolor": COLORS["paper"],
            "savefig.edgecolor": "none",
            "svg.hashsalt": "zhiyan-conference-readme-v2",
            "svg.fonttype": "path",
        }
    )


def _save_figure(fig: plt.Figure, stem: str, *, transparent: bool = False) -> None:
    svg_path = ASSETS / f"{stem}.svg"
    fig.savefig(
        svg_path,
        bbox_inches="tight",
        pad_inches=0.14,
        transparent=transparent,
        metadata={"Date": None, "Creator": "Zhiyan Agent asset generator"},
    )
    fig.savefig(
        ASSETS / f"{stem}.png",
        dpi=220,
        bbox_inches="tight",
        pad_inches=0.14,
        transparent=transparent,
        metadata={"Software": "Zhiyan Agent asset generator"},
    )
    svg_path.write_text(
        "\n".join(
            line.rstrip()
            for line in svg_path.read_text(encoding="utf-8").splitlines()
        )
        + "\n",
        encoding="utf-8",
    )
    plt.close(fig)


def _box(
    ax: plt.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    edge: str,
    face: str,
    radius: float = 0.12,
    linewidth: float = 1.4,
    linestyle: str = "-",
) -> FancyBboxPatch:
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        linewidth=linewidth,
        edgecolor=edge,
        facecolor=face,
        linestyle=linestyle,
    )
    ax.add_patch(patch)
    return patch


def _arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: str = COLORS["line"],
    width: float = 1.8,
    style: str = "-|>",
    connectionstyle: str = "arc3",
    linestyle: str = "-",
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle=style,
            mutation_scale=14,
            linewidth=width,
            color=color,
            connectionstyle=connectionstyle,
            linestyle=linestyle,
            shrinkA=3,
            shrinkB=3,
        )
    )


def build_wordmark() -> None:
    serif_path = font_manager.findfont("Source Han Serif SC", fallback_to_default=False)
    serif = font_manager.FontProperties(fname=serif_path, weight="heavy")
    sans = font_manager.FontProperties(family="Segoe UI", weight="semibold")

    fig, ax = plt.subplots(figsize=(16, 3.8))
    fig.patch.set_alpha(0)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 3.8)
    ax.axis("off")

    ax.text(
        1.0,
        2.2,
        "智演",
        fontproperties=serif,
        fontsize=92,
        color=COLORS["ink"],
        va="center",
    )
    ax.text(
        6.35,
        2.08,
        "AGENT",
        fontproperties=sans,
        fontsize=69,
        color=COLORS["blue_dark"],
        va="center",
    )

    bolt = Polygon(
        [(5.52, 3.05), (6.22, 3.05), (5.78, 2.20), (6.36, 2.20), (5.30, 0.82), (5.62, 1.85), (5.04, 1.85)],
        closed=True,
        facecolor=COLORS["orange"],
        edgecolor="none",
    )
    ax.add_patch(bolt)
    ax.plot(
        [0.96, 2.05, 2.26, 2.49, 2.76, 3.05, 3.24, 4.08, 4.42, 4.66, 4.89, 5.08],
        [0.58, 0.58, 0.72, 0.35, 0.94, 0.26, 0.58, 0.58, 0.78, 0.39, 0.58, 0.58],
        color=COLORS["blue"],
        linewidth=3.1,
        solid_capstyle="round",
        solid_joinstyle="round",
    )
    ax.plot([6.48, 14.95], [0.58, 0.58], color=COLORS["line"], linewidth=1.3)
    ax.text(
        6.48,
        0.82,
        "FAST-SLOW MULTI-AGENT CROWD INTELLIGENCE",
        fontproperties=sans,
        fontsize=13,
        color=COLORS["muted"],
        va="bottom",
    )
    _save_figure(fig, "zhiyan-wordmark", transparent=True)


def build_section_icons() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    paths = {
        "abstract": '<path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/>',
        "method": '<circle cx="5" cy="12" r="2"/><circle cx="12" cy="5" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="12" cy="19" r="2"/><path d="m6.5 10.5 4-4m3 0 4 4m0 3-4 4m-3 0-4-4"/>',
        "contributions": '<path d="m12 3 2.2 5.1 5.5.5-4.2 3.7 1.2 5.4-4.7-2.8-4.7 2.8 1.2-5.4-4.2-3.7 5.5-.5z"/>',
        "results": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
        "demo": '<rect x="3" y="4" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3zM8 21h8"/>',
        "reproduction": '<path d="M4 13a8 8 0 0 1 14-5M20 11a8 8 0 0 1-14 5"/><path d="M18 4v4h-4M6 20v-4h4"/>',
        "structure": '<rect x="9" y="3" width="6" height="4" rx="1"/><rect x="3" y="17" width="6" height="4" rx="1"/><rect x="15" y="17" width="6" height="4" rx="1"/><path d="M12 7v5M6 17v-2h12v2"/>',
        "limitations": '<path d="M12 3 2.8 20h18.4z"/><path d="M12 9v5M12 17h.01"/>',
        "author": '<circle cx="12" cy="8" r="4"/><path d="M4 21c.8-4 3.5-6 8-6s7.2 2 8 6"/>',
        "references": '<path d="M4 4h7a3 3 0 0 1 3 3v13a3 3 0 0 0-3-3H4z"/><path d="M20 4h-3a3 3 0 0 0-3 3v13a3 3 0 0 1 3-3h3z"/>',
    }
    template = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#2878B5" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="{label}">
  <title>{label}</title>
  {paths}
</svg>
"""
    for name, path_markup in paths.items():
        (ICONS / f"{name}.svg").write_text(
            template.format(label=name, paths=path_markup), encoding="utf-8"
        )


def build_method_architecture() -> None:
    """Build a compact English-only pipeline figure for the README."""
    fig, ax = plt.subplots(figsize=(18.5, 7.0))
    ax.set_xlim(0, 18.5)
    ax.set_ylim(0, 7.0)
    ax.axis("off")

    blue = "#0072B2"
    sky = "#56B4E9"
    amber = "#E69F00"
    vermillion = "#D55E00"
    green = "#009E73"
    light_blue = "#EDF6FB"
    light_amber = "#FFF7E6"
    light_green = "#ECF8F3"
    gray = "#5D6876"
    light_gray = "#F4F6F8"
    border = "#AAB4C0"

    def section_label(x: float, y: float, letter: str, title: str, width: float) -> None:
        ax.text(x, y, letter, fontsize=16, fontweight="bold", color=COLORS["ink"], va="center")
        ax.text(x + 0.38, y, title, fontsize=15, fontweight="bold", color=COLORS["ink"], va="center")
        ax.plot([x, x + width], [y - 0.28, y - 0.28], color=border, linewidth=0.8)

    def module(
        x: float,
        y: float,
        width: float,
        height: float,
        title: str,
        subtitle: str,
        *,
        edge: str = border,
        face: str = COLORS["paper"],
        title_size: float = 12.5,
    ) -> None:
        _box(ax, x, y, width, height, edge=edge, face=face, radius=0.06, linewidth=1.1)
        ax.text(x + width / 2, y + height - 0.34, title, fontsize=title_size, fontweight="bold", ha="center", va="center", linespacing=0.92)
        if subtitle:
            ax.text(x + width / 2, y + 0.27, subtitle, fontsize=9.4, color=gray, ha="center", va="center")

    section_label(0.35, 6.55, "a", "Continuous Crowd Dynamics", 11.35)
    section_label(8.25, 3.62, "b", "Event-triggered Evidence Reasoning", 7.40)
    section_label(15.90, 6.55, "c", "Counterfactual Evaluator", 2.25)

    module(0.45, 4.15, 1.65, 1.55, "Scene Tokens", "", edge=blue, face=light_blue)
    for index, label in enumerate(("Geometry", "Profiles", "Boundary")):
        y = 5.16 - index * 0.33
        ax.add_patch(Circle((0.68, y), 0.055, facecolor=blue, edgecolor="none"))
        ax.text(0.83, y, label, fontsize=9.3, color=gray, va="center")

    _box(ax, 2.61, 4.02, 2.55, 1.80, edge=blue, face=COLORS["paper"], radius=0.05, linewidth=1.15)
    ax.text(3.885, 5.49, "Interaction Encoder", fontsize=12.5, fontweight="bold", ha="center", va="center")
    for layer in range(4):
        x = 2.91 + layer * 0.42
        face = light_blue if layer % 2 == 0 else COLORS["paper"]
        _box(ax, x, 4.43, 0.70, 0.70, edge=sky, face=face, radius=0.03, linewidth=0.9)
        for row in range(2):
            for column in range(2):
                ax.add_patch(Circle((x + 0.22 + column * 0.26, 4.64 + row * 0.25), 0.042, facecolor=blue, edgecolor="none"))
    ax.text(4.88, 5.03, "× L", fontsize=10.5, color=blue, fontweight="bold", ha="center")
    ax.text(3.885, 4.20, r"$N(i)$  ·  $f_{ij}$  ·  collision", fontsize=9.4, color=gray, ha="center")

    module(5.70, 4.15, 2.45, 1.55, "Temporal Rollout", "state transition", edge=blue, face=COLORS["paper"])
    state_labels = (r"$X_t$", r"$X_{t+1}$", r"$\cdots$", r"$X_{t+H}$")
    for index, label in enumerate(state_labels):
        x = 5.94 + index * 0.51
        _box(ax, x, 4.66, 0.42, 0.45, edge=sky, face=light_blue, radius=0.04, linewidth=0.9)
        ax.text(x + 0.21, 4.885, label, fontsize=9.3, fontweight="bold", ha="center", va="center")
        if index < len(state_labels) - 1:
            _arrow(ax, (x + 0.42, 4.885), (x + 0.50, 4.885), color=sky, width=0.9)

    gate = Polygon(
        [(9.10, 5.78), (9.82, 4.92), (9.10, 4.06), (8.38, 4.92)],
        closed=True,
        facecolor=light_amber,
        edgecolor=amber,
        linewidth=1.25,
    )
    ax.add_patch(gate)
    ax.text(9.10, 5.12, "Risk Gate", fontsize=11.5, fontweight="bold", ha="center", va="center")
    ax.text(9.10, 4.73, r"$r_t > \tau$", fontsize=10.5, color=vermillion, ha="center", va="center")

    module(10.34, 4.15, 1.46, 1.55, "Crowd State", "", edge=blue, face=light_blue)
    for index, label in enumerate(("density", "velocity", "conflict")):
        ax.text(11.07, 5.13 - index * 0.28, label, fontsize=9.0, color=gray, ha="center", va="center")
    ax.text(11.07, 4.31, r"$D_t$ · $V_t$ · $C_t$", fontsize=8.8, color=gray, ha="center", va="center")

    _arrow(ax, (2.10, 4.92), (2.61, 4.92), color=blue, width=1.5)
    _arrow(ax, (5.16, 4.92), (5.70, 4.92), color=blue, width=1.5)
    _arrow(ax, (8.15, 4.92), (8.38, 4.92), color=blue, width=1.5)
    _arrow(ax, (9.82, 4.92), (10.34, 4.92), color=blue, width=1.5)

    module(8.34, 1.35, 1.52, 1.42, "Risk Context", r"$q_r = \{D,V,C\}$", edge=vermillion, face=light_amber)
    module(10.26, 1.35, 1.70, 1.42, "Evidence\nRetriever", "top-k + metadata", edge=amber, face=COLORS["paper"], title_size=10.8)
    module(12.36, 1.35, 1.74, 1.42, "Evidence\nReasoner", r"$q_r \leftrightarrow K$", edge=amber, face=COLORS["paper"], title_size=10.8)
    module(14.50, 1.35, 1.20, 1.42, "Strategy", r"$\pi_\theta(z)$", edge=amber, face=light_amber)

    ax.plot([9.10, 9.10], [4.06, 2.77], color=vermillion, linewidth=1.25)
    _arrow(ax, (9.10, 2.77), (9.10, 2.70), color=vermillion, width=1.25)
    ax.text(9.30, 3.34, "trigger", fontsize=9.0, color=vermillion, va="center")
    _arrow(ax, (9.86, 2.06), (10.26, 2.06), color=amber, width=1.3)
    _arrow(ax, (11.96, 2.06), (12.36, 2.06), color=amber, width=1.3)
    _arrow(ax, (14.10, 2.06), (14.50, 2.06), color=amber, width=1.3)

    _box(ax, 10.34, 0.34, 1.55, 0.58, edge=border, face=light_gray, radius=0.04, linewidth=0.9)
    ax.text(11.115, 0.63, "Evidence Store  K", fontsize=9.6, fontweight="bold", color=gray, ha="center", va="center")
    _arrow(ax, (11.115, 0.92), (11.115, 1.35), color=border, width=1.0, linestyle="--")

    _box(ax, 16.02, 1.18, 2.16, 4.70, edge=green, face=light_green, radius=0.06, linewidth=1.2)
    ax.text(17.10, 5.50, "Matched Seed", fontsize=11.8, fontweight="bold", color=green, ha="center")
    ax.text(17.10, 5.17, "s = constant", fontsize=9.5, color=gray, ha="center")
    module(16.30, 4.03, 1.60, 0.82, "Baseline", r"$\pi_0$", edge=green, face=COLORS["paper"])
    module(16.30, 2.93, 1.60, 0.82, "Intervention", r"$\pi_1$", edge=green, face=COLORS["paper"])
    _box(ax, 16.30, 1.55, 1.60, 0.98, edge=green, face=COLORS["paper"], radius=0.04, linewidth=1.0)
    ax.text(17.10, 2.19, "Paired Δ", fontsize=11.0, fontweight="bold", ha="center")
    ax.text(17.10, 1.83, "density · risk · flow", fontsize=8.8, color=gray, ha="center")
    _arrow(ax, (17.10, 4.03), (17.10, 3.75), color=green, width=1.1)
    _arrow(ax, (17.10, 2.93), (17.10, 2.53), color=green, width=1.1)

    ax.plot([11.80, 15.80, 15.80, 16.02], [4.92, 4.92, 4.44, 4.44], color=blue, linewidth=1.25)
    _arrow(ax, (15.80, 4.44), (16.30, 4.44), color=blue, width=1.25)
    ax.plot([15.70, 15.86, 15.86], [2.06, 2.06, 3.34], color=amber, linewidth=1.25)
    _arrow(ax, (15.86, 3.34), (16.30, 3.34), color=amber, width=1.25)

    ax.text(0.45, 0.55, "Fast path", fontsize=9.4, color=blue, fontweight="bold")
    ax.plot([1.20, 2.25], [0.60, 0.60], color=blue, linewidth=1.6)
    ax.text(2.58, 0.55, "Triggered path", fontsize=9.4, color=amber, fontweight="bold")
    ax.plot([3.72, 4.77], [0.60, 0.60], color=amber, linewidth=1.6)
    ax.text(5.10, 0.55, "Paired evaluation", fontsize=9.4, color=green, fontweight="bold")
    ax.plot([6.53, 7.58], [0.60, 0.60], color=green, linewidth=1.6)

    _save_figure(fig, "method-architecture")


def build_results_overview() -> None:
    interventions = json.loads((RESULTS / "interventions.json").read_text(encoding="utf-8"))
    benchmark = json.loads((RESULTS / "benchmark.json").read_text(encoding="utf-8"))
    calibration = json.loads((RESULTS / "historical-calibration.json").read_text(encoding="utf-8"))

    labels = ["中央护栏", "单向导流", "出口拓宽"]
    reductions = [item["reduction_ratio"] * 100 for item in interventions["strategies"]]
    target = calibration["target_peak_density_people_per_m2"]
    reproduced = calibration["calibrated_peak_density_people_per_m2"]
    relative_error = calibration["relative_calibration_error"] * 100

    fig = plt.figure(figsize=(16, 8.4))
    grid = fig.add_gridspec(
        2,
        3,
        width_ratios=(1.45, 1, 1),
        height_ratios=(1.12, 0.88),
        left=0.055,
        right=0.985,
        bottom=0.12,
        top=0.79,
        hspace=0.42,
        wspace=0.28,
    )
    fig.suptitle("实验结果与证据层级 / Results & Evidence", x=0.055, y=0.98, ha="left", fontsize=25, fontweight="bold", color=COLORS["ink"])
    fig.text(0.055, 0.925, "可复现实验结果与项目规模统计分区呈现，避免将工程留档误读为模型精度", fontsize=14, color=COLORS["muted"])

    ax_intervention = fig.add_subplot(grid[:, 0])
    positions = np.arange(len(labels))
    bars = ax_intervention.barh(positions, reductions, color=["#79A9CE", COLORS["teal"], "#79A9CE"], height=0.54)
    ax_intervention.set_title("A  干预效果 / Intervention", loc="left", fontsize=18, fontweight="bold", pad=18)
    ax_intervention.text(0.0, 1.01, "相对 Baseline 的峰值密度降幅", transform=ax_intervention.transAxes, fontsize=12.5, color=COLORS["muted"], va="bottom")
    ax_intervention.set_yticks(positions, labels)
    ax_intervention.invert_yaxis()
    ax_intervention.set_xlim(0, 27)
    ax_intervention.set_xlabel("Peak-density reduction (%)")
    ax_intervention.grid(axis="x", color="#E5EAF0", linewidth=0.9)
    ax_intervention.set_axisbelow(True)
    ax_intervention.spines["left"].set_visible(False)
    ax_intervention.tick_params(axis="y", length=0, labelsize=14)
    for bar, value in zip(bars, reductions):
        ax_intervention.text(value + 0.55, bar.get_y() + bar.get_height() / 2, f"−{value:.2f}%", va="center", fontsize=14, fontweight="bold", color=COLORS["ink"])
    ax_intervention.text(0.0, -0.14, "n = 3 fixed seeds · 300 Agent capacity · 120 steps", transform=ax_intervention.transAxes, fontsize=11, color=COLORS["muted"])

    ax_calibration = fig.add_subplot(grid[0, 1])
    ax_calibration.set_title("B  历史场景复现 / Calibration", loc="left", fontsize=18, fontweight="bold", pad=18)
    ax_calibration.plot([target, reproduced], [1, 0], color=COLORS["blue"], linewidth=2.2, marker="o", markersize=9)
    ax_calibration.set_yticks([1, 0], ["历史目标", "仿真复现"])
    ax_calibration.set_xlim(16.20, 16.48)
    ax_calibration.set_xlabel("峰值密度（人 / m²）")
    ax_calibration.grid(axis="x", color="#E5EAF0", linewidth=0.9)
    ax_calibration.set_axisbelow(True)
    ax_calibration.spines["left"].set_visible(False)
    ax_calibration.tick_params(axis="y", length=0)
    ax_calibration.text(target + 0.012, 1, f"{target:.2f}", va="center", fontsize=13, fontweight="bold")
    ax_calibration.text(reproduced + 0.012, 0, f"{reproduced:.2f}", va="center", fontsize=13, fontweight="bold")
    ax_calibration.text(0.98, 0.53, f"{relative_error:.2f}%", transform=ax_calibration.transAxes, fontsize=27, fontweight="bold", color=COLORS["blue"], ha="right")
    ax_calibration.text(0.98, 0.41, "relative reproduction error", transform=ax_calibration.transAxes, fontsize=10.5, color=COLORS["muted"], ha="right")

    ax_throughput = fig.add_subplot(grid[0, 2])
    ax_throughput.axis("off")
    ax_throughput.set_title("C  仿真吞吐 / Throughput", loc="left", fontsize=18, fontweight="bold", pad=18)
    _box(ax_throughput, 0.02, 0.08, 0.96, 0.78, edge=COLORS["teal"], face=COLORS["teal_pale"], radius=0.04, linewidth=1.2)
    ax_throughput.text(0.50, 0.60, f'{benchmark["steps_per_second"]:.2f}', transform=ax_throughput.transAxes, fontsize=34, fontweight="bold", color=COLORS["teal"], ha="center", va="center")
    ax_throughput.text(0.50, 0.41, "simulation steps / s", transform=ax_throughput.transAxes, fontsize=12.5, color=COLORS["ink"], ha="center", va="center")
    ax_throughput.text(0.50, 0.21, f'{benchmark["agents"]} capacity · {benchmark["max_agents_seen"]} max active · {benchmark["steps"]} steps', transform=ax_throughput.transAxes, fontsize=10.5, color=COLORS["muted"], ha="center", va="center")

    ax_knowledge = fig.add_subplot(grid[1, 1:])
    ax_knowledge.set_xlim(0, 10)
    ax_knowledge.set_ylim(0, 3)
    ax_knowledge.axis("off")
    ax_knowledge.set_title("D  知识库规模 / Knowledge Base Statistics", loc="left", fontsize=18, fontweight="bold", pad=12)
    ax_knowledge.text(0, 2.64, "项目规模统计，不表示检索准确率", fontsize=12.5, color=COLORS["muted"], va="top")
    funnel = (
        (0.0, 1.05, 3.2, "93", "Retrievable Items", COLORS["blue_pale"], COLORS["blue"]),
        (3.55, 1.05, 2.75, "52", "Reviewed", COLORS["teal_pale"], COLORS["teal"]),
        (6.65, 1.05, 2.25, "25", "Golden Evidence", COLORS["orange_pale"], COLORS["orange"]),
    )
    for index, (x, y, width, value, label, face, edge) in enumerate(funnel):
        _box(ax_knowledge, x, y, width, 1.12, edge=edge, face=face, radius=0.08, linewidth=1.2)
        ax_knowledge.text(x + width / 2, y + 0.70, value, fontsize=22, fontweight="bold", color=edge, va="center", ha="center")
        ax_knowledge.text(x + width / 2, y + 0.25, label, fontsize=11.2, color=COLORS["ink"], va="center", ha="center")
        if index < len(funnel) - 1:
            _arrow(ax_knowledge, (x + width, y + 0.56), (funnel[index + 1][0], y + 0.56), color=COLORS["line"], width=1.5)
    ax_knowledge.text(0, 0.52, "Machine-readable evidence: docs/results/*.json", fontsize=11, color=COLORS["muted"])

    _save_figure(fig, "results-overview")


if __name__ == "__main__":
    _configure()
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_wordmark()
    build_section_icons()
    build_method_architecture()
    build_results_overview()

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
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(
        0.25,
        8.63,
        "智演 Agent 方法架构 / Method Architecture",
        fontsize=25,
        fontweight="bold",
        color=COLORS["ink"],
        va="top",
    )
    ax.text(
        0.25,
        8.22,
        "高频群体演化定位风险，证据增强慢脑生成策略，同种子反事实复跑验证效果",
        fontsize=14,
        color=COLORS["muted"],
        va="top",
    )

    _box(ax, 0.25, 3.25, 2.35, 4.15, edge=COLORS["blue"], face=COLORS["blue_pale"])
    ax.text(0.52, 7.05, "01  场景编码", fontsize=18, fontweight="bold", color=COLORS["blue_dark"], va="top")
    ax.text(0.52, 6.68, "Scenario Encoding", fontsize=12.5, color=COLORS["muted"], va="top")
    inputs = (
        ("空间拓扑", "geometry · exits"),
        ("群体画像", "profiles · mobility"),
        ("边界条件", "flow · obstacles"),
    )
    for index, (title, subtitle) in enumerate(inputs):
        y = 5.70 - index * 1.03
        _box(ax, 0.52, y, 1.82, 0.74, edge=COLORS["blue"], face=COLORS["paper"], radius=0.08, linewidth=1.0)
        ax.text(0.67, y + 0.47, title, fontsize=14, fontweight="bold", va="center")
        ax.text(0.67, y + 0.20, subtitle, fontsize=10.5, color=COLORS["muted"], va="center")
    _box(ax, 2.98, 4.88, 7.42, 2.52, edge=COLORS["teal"], face=COLORS["teal_pale"])
    ax.text(3.25, 7.05, "02  Fast Brain · 高频多智能体演化", fontsize=18, fontweight="bold", color=COLORS["teal"], va="top")
    ax.text(3.25, 6.68, "Agent Interaction Layers", fontsize=12.5, color=COLORS["muted"], va="top")

    layer_x = [3.36, 3.88, 4.40, 4.92]
    for layer_index, x in enumerate(layer_x):
        _box(ax, x, 5.18, 0.88, 1.18, edge=COLORS["teal"], face=COLORS["paper"], radius=0.06, linewidth=1.0)
        for row in range(3):
            for column in range(2):
                ax.add_patch(Circle((x + 0.27 + column * 0.34, 5.46 + row * 0.30), 0.055, facecolor=COLORS["teal"], edgecolor="none"))
        if layer_index < len(layer_x) - 1:
            _arrow(ax, (x + 0.88, 5.77), (layer_x[layer_index + 1], 5.77), color=COLORS["teal"], width=1.1)
    ax.text(4.63, 5.02, "邻域感知 · 社会力 · 避障更新", fontsize=11, color=COLORS["muted"], ha="center")

    ax.text(6.18, 6.43, "Temporal Evolution", fontsize=12.5, color=COLORS["muted"], va="top")
    times = ("t", "t+1", "…", "t+n")
    for index, label in enumerate(times):
        x = 6.00 + index * 0.63
        _box(ax, x, 5.43, 0.56, 0.58, edge=COLORS["teal"], face=COLORS["paper"], radius=0.07, linewidth=1.0)
        ax.text(x + 0.28, 5.72, label, fontsize=12.5, ha="center", va="center", fontweight="bold")
        if index < len(times) - 1:
            _arrow(ax, (x + 0.56, 5.72), (x + 0.62, 5.72), color=COLORS["teal"], width=1.0)

    ax.text(9.38, 6.43, "Crowd State", fontsize=12.5, color=COLORS["muted"], ha="center", va="top")
    for index, label in enumerate(("Density", "Velocity", "Congestion")):
        y = 5.88 - index * 0.39
        _box(ax, 8.64, y, 1.48, 0.28, edge=COLORS["teal"], face=COLORS["paper"], radius=0.05, linewidth=0.9)
        ax.text(9.38, y + 0.14, label, fontsize=10.5, ha="center", va="center")

    _arrow(ax, (2.60, 5.92), (2.98, 5.92), color=COLORS["blue"], width=2.0)

    gate = Polygon(
        [(11.32, 6.95), (12.28, 6.13), (11.32, 5.31), (10.36, 6.13)],
        closed=True,
        facecolor=COLORS["red_pale"],
        edgecolor=COLORS["red"],
        linewidth=1.5,
    )
    ax.add_patch(gate)
    ax.text(11.32, 6.29, "Risk-aware", fontsize=12.5, ha="center", va="center", fontweight="bold", color=COLORS["red"])
    ax.text(11.32, 5.99, "Gating", fontsize=12.5, ha="center", va="center", fontweight="bold", color=COLORS["red"])
    ax.text(11.32, 5.69, "score > τ", fontsize=10.5, ha="center", va="center", color=COLORS["muted"])
    _arrow(ax, (10.40, 6.13), (10.57, 6.13), color=COLORS["teal"], width=2.0)

    _box(ax, 2.98, 1.18, 9.30, 2.80, edge=COLORS["orange"], face=COLORS["orange_pale"])
    ax.text(3.25, 3.64, "03  Slow Brain · 证据增强风险推理", fontsize=18, fontweight="bold", color=COLORS["orange"], va="top")
    ax.text(3.25, 3.28, "Event-triggered reasoning path", fontsize=12.5, color=COLORS["muted"], va="top")
    slow_nodes = (
        (3.26, "Risk Context", "时空异常摘要"),
        (5.49, "Evidence Retrieval", "RAG · metadata"),
        (7.72, "Reasoning", "evidence-grounded"),
        (9.95, "Intervention Head", "guardrail · flow · exits"),
    )
    for index, (x, title, subtitle) in enumerate(slow_nodes):
        _box(ax, x, 1.68, 1.83, 1.04, edge=COLORS["orange"], face=COLORS["paper"], radius=0.09, linewidth=1.1)
        ax.text(x + 0.915, 2.34, title, fontsize=12.2, ha="center", va="center", fontweight="bold")
        ax.text(x + 0.915, 1.98, subtitle, fontsize=10.2, ha="center", va="center", color=COLORS["muted"])
        if index < len(slow_nodes) - 1:
            _arrow(ax, (x + 1.83, 2.20), (slow_nodes[index + 1][0], 2.20), color=COLORS["orange"], width=1.7)
    ax.plot([11.32, 11.32, 4.18], [5.31, 3.02, 3.02], color=COLORS["red"], linewidth=1.7)
    _arrow(ax, (4.18, 3.02), (4.18, 2.72), color=COLORS["red"], width=1.7)
    ax.text(10.92, 3.16, "trigger", fontsize=10.5, color=COLORS["red"], fontweight="bold", ha="center")

    _box(ax, 12.75, 1.18, 3.00, 6.22, edge=COLORS["green"], face=COLORS["green_pale"])
    ax.text(13.04, 7.05, "04  闭环验证", fontsize=18, fontweight="bold", color=COLORS["green"], va="top")
    ax.text(13.04, 6.68, "Matched-seed Replay", fontsize=12.5, color=COLORS["muted"], va="top")
    replay_nodes = (
        (5.50, "Baseline", "original parameters"),
        (4.26, "Intervention", "executable parameters"),
        (3.02, "Paired Comparison", "density · flow · duration"),
        (1.78, "Evidence Artifacts", "JSON · report · traces"),
    )
    for index, (y, title, subtitle) in enumerate(replay_nodes):
        face = COLORS["paper"] if index != 2 else "#DDF0E6"
        _box(ax, 13.08, y, 2.34, 0.82, edge=COLORS["green"], face=face, radius=0.08, linewidth=1.1)
        ax.text(14.25, y + 0.51, title, fontsize=12.2, ha="center", va="center", fontweight="bold")
        ax.text(14.25, y + 0.21, subtitle, fontsize=9.8, ha="center", va="center", color=COLORS["muted"])
        if index < len(replay_nodes) - 1:
            _arrow(ax, (14.25, y), (14.25, replay_nodes[index + 1][0] + 0.82), color=COLORS["green"], width=1.5)
    _arrow(ax, (12.28, 6.13), (13.08, 5.91), color=COLORS["green"], width=1.9)
    _arrow(ax, (11.78, 2.20), (13.08, 4.67), color=COLORS["orange"], width=1.9, connectionstyle="angle3,angleA=0,angleB=-90")

    ax.text(
        0.25,
        0.50,
        "Figure 1. 快脑持续推进群体状态；风险门控仅在异常时激活慢脑；干预策略必须回到同种子仿真中接受成对验证。",
        fontsize=12.5,
        color=COLORS["muted"],
        va="center",
    )
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

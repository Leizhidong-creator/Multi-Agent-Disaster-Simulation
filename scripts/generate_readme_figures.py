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
    """Build a spacious English-only pipeline figure for the README."""
    fig, ax = plt.subplots(figsize=(18.5, 9.2))
    ax.set_xlim(0, 18.5)
    ax.set_ylim(0, 9.2)
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

    section_label(0.35, 8.72, "a", "Continuous Crowd Dynamics", 11.55)
    section_label(7.98, 5.25, "b", "Event-triggered Evidence Reasoning", 7.70)
    section_label(15.90, 8.72, "c", "Counterfactual Evaluator", 2.25)

    module(0.45, 6.35, 1.80, 1.70, "Scene Tokens", "", edge=blue, face=light_blue, title_size=13.5)
    for index, label in enumerate(("Geometry", "Profiles", "Boundary")):
        y = 7.40 - index * 0.34
        ax.add_patch(Circle((0.68, y), 0.055, facecolor=blue, edgecolor="none"))
        ax.text(0.83, y, label, fontsize=10.0, color=gray, va="center")

    _box(ax, 2.85, 6.22, 2.80, 1.96, edge=blue, face=COLORS["paper"], radius=0.05, linewidth=1.15)
    ax.text(4.25, 7.82, "Interaction Encoder", fontsize=13.8, fontweight="bold", ha="center", va="center")
    for layer in range(4):
        x = 3.20 + layer * 0.45
        face = light_blue if layer % 2 == 0 else COLORS["paper"]
        _box(ax, x, 6.72, 0.74, 0.74, edge=sky, face=face, radius=0.03, linewidth=0.9)
        for row in range(2):
            for column in range(2):
                ax.add_patch(Circle((x + 0.23 + column * 0.27, 6.94 + row * 0.27), 0.044, facecolor=blue, edgecolor="none"))
    ax.text(5.30, 7.33, "× L", fontsize=11.0, color=blue, fontweight="bold", ha="center")
    ax.text(4.25, 6.43, "local interaction · collision", fontsize=9.8, color=gray, ha="center")

    module(6.25, 6.35, 2.60, 1.70, "Temporal Rollout", "state transition", edge=blue, face=COLORS["paper"], title_size=13.5)
    state_labels = (r"$X_t$", r"$X_{t+1}$", "…", r"$X_{t+H}$")
    for index, label in enumerate(state_labels):
        x = 6.52 + index * 0.53
        _box(ax, x, 6.94, 0.44, 0.47, edge=sky, face=light_blue, radius=0.04, linewidth=0.9)
        ax.text(x + 0.22, 7.175, label, fontsize=9.6, fontweight="bold", ha="center", va="center")
        if index < len(state_labels) - 1:
            _arrow(ax, (x + 0.44, 7.175), (x + 0.52, 7.175), color=sky, width=0.9)

    gate = Polygon(
        [(9.92, 8.14), (10.72, 7.20), (9.92, 6.26), (9.12, 7.20)],
        closed=True,
        facecolor=light_amber,
        edgecolor=amber,
        linewidth=1.25,
    )
    ax.add_patch(gate)
    ax.text(9.92, 7.43, "Risk Gate", fontsize=12.5, fontweight="bold", ha="center", va="center")
    ax.text(9.92, 7.00, "threshold", fontsize=10.0, color=vermillion, ha="center", va="center")

    module(11.02, 6.35, 1.65, 1.70, "Crowd State", "", edge=blue, face=light_blue, title_size=13.0)
    for index, label in enumerate(("density", "velocity", "conflict")):
        ax.text(11.845, 7.36 - index * 0.30, label, fontsize=9.8, color=gray, ha="center", va="center")

    _arrow(ax, (2.25, 7.20), (2.85, 7.20), color=blue, width=1.6)
    _arrow(ax, (5.65, 7.20), (6.25, 7.20), color=blue, width=1.6)
    _arrow(ax, (8.85, 7.20), (9.12, 7.20), color=blue, width=1.6)
    _arrow(ax, (10.72, 7.20), (11.02, 7.20), color=blue, width=1.6)

    module(8.05, 2.75, 1.65, 1.55, "Risk Context", "risk descriptors", edge=vermillion, face=light_amber, title_size=12.2)
    module(10.15, 2.75, 1.82, 1.55, "Evidence\nRetriever", "top-k + metadata", edge=amber, face=COLORS["paper"], title_size=11.5)
    module(12.42, 2.75, 1.86, 1.55, "Evidence\nReasoner", "evidence-grounded", edge=amber, face=COLORS["paper"], title_size=11.5)
    module(14.73, 2.75, 1.15, 1.55, "Strategy", "parameters", edge=amber, face=light_amber, title_size=11.5)

    ax.plot([9.92, 9.92, 8.88], [6.26, 4.70, 4.70], color=vermillion, linewidth=1.35)
    _arrow(ax, (8.88, 4.70), (8.88, 4.30), color=vermillion, width=1.35)
    ax.text(10.12, 5.02, "risk trigger", fontsize=9.6, color=vermillion, va="center")
    _arrow(ax, (9.70, 3.52), (10.15, 3.52), color=amber, width=1.4)
    _arrow(ax, (11.97, 3.52), (12.42, 3.52), color=amber, width=1.4)
    _arrow(ax, (14.28, 3.52), (14.73, 3.52), color=amber, width=1.4)

    _box(ax, 10.23, 1.42, 1.66, 0.62, edge=border, face=light_gray, radius=0.04, linewidth=0.9)
    ax.text(11.06, 1.73, "Evidence Store", fontsize=9.8, fontweight="bold", color=gray, ha="center", va="center")
    _arrow(ax, (11.06, 2.04), (11.06, 2.75), color=border, width=1.0, linestyle="--")

    _box(ax, 16.12, 1.55, 2.05, 6.56, edge=green, face=light_green, radius=0.06, linewidth=1.2)
    ax.text(17.145, 7.62, "Matched Seed", fontsize=12.5, fontweight="bold", color=green, ha="center")
    ax.text(17.145, 7.25, "same initial state", fontsize=9.8, color=gray, ha="center")
    module(16.38, 5.68, 1.53, 0.95, "Baseline", "control", edge=green, face=COLORS["paper"], title_size=12.0)
    module(16.38, 4.30, 1.53, 0.95, "Intervention", "strategy", edge=green, face=COLORS["paper"], title_size=11.5)
    _box(ax, 16.38, 2.45, 1.53, 1.22, edge=green, face=COLORS["paper"], radius=0.04, linewidth=1.0)
    ax.text(17.145, 3.20, "Paired Δ", fontsize=11.5, fontweight="bold", ha="center")
    ax.text(17.145, 2.78, "density · risk · flow", fontsize=8.8, color=gray, ha="center")
    _arrow(ax, (17.145, 5.68), (17.145, 5.25), color=green, width=1.2)
    _arrow(ax, (17.145, 4.30), (17.145, 3.67), color=green, width=1.2)

    ax.plot([12.67, 15.76, 15.76, 16.12], [7.20, 7.20, 6.15, 6.15], color=blue, linewidth=1.35)
    _arrow(ax, (15.76, 6.15), (16.38, 6.15), color=blue, width=1.35)
    ax.plot([15.88, 16.00, 16.00], [3.52, 3.52, 4.77], color=amber, linewidth=1.35)
    _arrow(ax, (16.00, 4.77), (16.38, 4.77), color=amber, width=1.35)

    ax.text(0.45, 0.60, "Fast path", fontsize=10.0, color=blue, fontweight="bold")
    ax.plot([1.28, 2.38], [0.66, 0.66], color=blue, linewidth=1.7)
    ax.text(2.75, 0.60, "Triggered path", fontsize=10.0, color=amber, fontweight="bold")
    ax.plot([4.02, 5.12], [0.66, 0.66], color=amber, linewidth=1.7)
    ax.text(5.50, 0.60, "Paired evaluation", fontsize=10.0, color=green, fontweight="bold")
    ax.plot([7.02, 8.12], [0.66, 0.66], color=green, linewidth=1.7)

    _save_figure(fig, "method-architecture")


def build_results_overview() -> None:
    interventions = json.loads((RESULTS / "interventions.json").read_text(encoding="utf-8"))
    calibration = json.loads((RESULTS / "historical-calibration.json").read_text(encoding="utf-8"))

    labels = ["Baseline", "Guardrail", "One-way flow", "Widened exits"]
    peak_density_runs = [
        [run["peak_density"] for run in interventions["baseline"]["runs"]],
        *[
            [run["peak_density"] for run in strategy["runs"]]
            for strategy in interventions["strategies"]
        ],
    ]
    reductions = [0.0, *[item["reduction_ratio"] * 100 for item in interventions["strategies"]]]
    target = calibration["target_peak_density_people_per_m2"]
    reproduced = calibration["calibrated_peak_density_people_per_m2"]
    relative_error = calibration["relative_calibration_error"] * 100

    fig, (ax_intervention, ax_calibration) = plt.subplots(
        1,
        2,
        figsize=(16, 6.8),
        gridspec_kw={"width_ratios": (1.65, 1), "wspace": 0.28},
    )
    fig.subplots_adjust(left=0.075, right=0.975, bottom=0.18, top=0.78)
    fig.suptitle("Quantitative Results", x=0.075, y=0.96, ha="left", fontsize=25, fontweight="bold")
    fig.text(0.075, 0.895, "Matched-seed intervention study and historical-scene reproduction", fontsize=13.5, color=COLORS["muted"])

    positions = np.arange(len(labels))
    palette = [COLORS["muted"], COLORS["blue"], COLORS["teal"], COLORS["orange"]]
    for seed_index in range(len(peak_density_runs[0])):
        values = [group[seed_index] for group in peak_density_runs]
        ax_intervention.plot(positions, values, color="#C7CDD6", linewidth=1.15, alpha=0.75, zorder=1)
    for position, (values, color) in enumerate(zip(peak_density_runs, palette)):
        jitter = np.linspace(-0.10, 0.10, len(values))
        ax_intervention.scatter(position + jitter, values, s=52, color=color, edgecolor="white", linewidth=0.8, zorder=3)
        mean = float(np.mean(values))
        standard_deviation = float(np.std(values))
        ax_intervention.errorbar(position, mean, yerr=standard_deviation, fmt="D", markersize=7, color=COLORS["ink"], capsize=5, linewidth=1.5, zorder=4)
        if position > 0:
            ax_intervention.text(position, 7.72, f"−{reductions[position]:.2f}%", ha="center", va="bottom", fontsize=11.5, fontweight="bold", color=color)
    ax_intervention.set_title("a  Peak Density under Interventions", loc="left", fontsize=17, fontweight="bold", pad=15)
    ax_intervention.set_ylabel("Peak density (persons / m²)")
    ax_intervention.set_xticks(positions, labels)
    ax_intervention.set_ylim(3.95, 8.05)
    ax_intervention.grid(axis="y", color="#E5EAF0", linewidth=0.9)
    ax_intervention.set_axisbelow(True)
    ax_intervention.text(0.0, -0.19, "Points: fixed seeds · diamonds: mean · error bars: Standard deviation", transform=ax_intervention.transAxes, fontsize=10.5, color=COLORS["muted"])
    ax_intervention.text(0.0, -0.27, "n = 3 seeds · 300 Agent capacity · 120 steps", transform=ax_intervention.transAxes, fontsize=10.5, color=COLORS["muted"])

    ax_calibration.set_title("b  Historical-scene Reproduction", loc="left", fontsize=17, fontweight="bold", pad=15)
    ax_calibration.plot([0, 1], [target, reproduced], color=COLORS["blue"], linewidth=2.0, zorder=1)
    ax_calibration.scatter([0], [target], s=95, marker="o", color=COLORS["blue"], edgecolor="white", linewidth=1.0, zorder=3)
    ax_calibration.scatter([1], [reproduced], s=105, marker="D", color=COLORS["teal"], edgecolor="white", linewidth=1.0, zorder=3)
    ax_calibration.set_xticks([0, 1], ["Historical target", "Simulation"])
    ax_calibration.set_ylabel("Peak density (persons / m²)")
    ax_calibration.set_xlim(-0.45, 1.45)
    ax_calibration.set_ylim(16.26, 16.46)
    ax_calibration.grid(axis="y", color="#E5EAF0", linewidth=0.9)
    ax_calibration.set_axisbelow(True)
    ax_calibration.text(0, target + 0.012, f"{target:.2f}", ha="center", fontsize=12.5, fontweight="bold")
    ax_calibration.text(1, reproduced - 0.023, f"{reproduced:.2f}", ha="center", fontsize=12.5, fontweight="bold")
    ax_calibration.text(0.50, 0.55, f"{relative_error:.2f}%", transform=ax_calibration.transAxes, ha="center", fontsize=30, fontweight="bold", color=COLORS["blue"])
    ax_calibration.text(0.50, 0.45, "relative reproduction error", transform=ax_calibration.transAxes, ha="center", fontsize=11.0, color=COLORS["muted"])
    ax_calibration.text(0.50, -0.19, "Historical target calibration · absolute gap 0.07 persons / m²", transform=ax_calibration.transAxes, ha="center", fontsize=10.5, color=COLORS["muted"])

    _save_figure(fig, "results-overview")


if __name__ == "__main__":
    _configure()
    ASSETS.mkdir(parents=True, exist_ok=True)
    build_wordmark()
    build_section_icons()
    build_method_architecture()
    build_results_overview()

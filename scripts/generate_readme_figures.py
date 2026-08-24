"""Generate publication-style figures used by README.md.

The figures are intentionally deterministic and derived from the checked-in
experiment JSON, so the portfolio page does not depend on an image model or
an external API key.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "assets"


def _configure() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Noto Sans SC", "Microsoft YaHei", "DejaVu Sans"],
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#667085",
            "axes.linewidth": 0.8,
            "xtick.color": "#344054",
            "ytick.color": "#344054",
            "text.color": "#1D2939",
            "figure.facecolor": "#FFFFFF",
            "axes.facecolor": "#FFFFFF",
            "savefig.facecolor": "#FFFFFF",
            "savefig.edgecolor": "none",
            "svg.hashsalt": "zhiyan-readme-figures",
            "svg.fonttype": "none",
        }
    )


def _save(fig: plt.Figure, stem: str) -> None:
    svg_path = FIGURES / f"{stem}.svg"
    fig.savefig(
        svg_path,
        bbox_inches="tight",
        pad_inches=0.12,
        metadata={"Date": None, "Creator": "Zhiyan Agent figure generator"},
    )
    fig.savefig(
        FIGURES / f"{stem}.png",
        dpi=300,
        bbox_inches="tight",
        pad_inches=0.12,
        metadata={"Software": "Zhiyan Agent figure generator"},
    )
    svg_path.write_text(
        "\n".join(line.rstrip() for line in svg_path.read_text(encoding="utf-8").splitlines()) + "\n",
        encoding="utf-8",
    )
    plt.close(fig)


def build_method_overview() -> None:
    fig, ax = plt.subplots(figsize=(15.5, 7.4), constrained_layout=True)
    ax.set_xlim(0, 15.5)
    ax.set_ylim(0, 7.4)
    ax.axis("off")

    colors = {
        "navy": "#17324D",
        "blue": "#2F80ED",
        "teal": "#008C95",
        "orange": "#E67E22",
        "green": "#2E8B57",
        "ink": "#1D2939",
        "muted": "#667085",
        "line": "#98A2B3",
        "pale_blue": "#EAF3FF",
        "pale_teal": "#E8F7F6",
        "pale_orange": "#FFF3E8",
        "pale_green": "#EAF7EF",
        "pale_gray": "#F8FAFC",
    }

    def panel(x: float, y: float, w: float, h: float, title: str, subtitle: str, color: str, fill: str) -> None:
        rect = plt.Rectangle((x, y), w, h, facecolor=fill, edgecolor=color, linewidth=1.4, joinstyle="round")
        ax.add_patch(rect)
        ax.text(x + 0.22, y + h - 0.38, title, fontsize=12, fontweight="bold", color=color, va="top")
        ax.text(x + 0.22, y + h - 0.72, subtitle, fontsize=8.5, color=colors["muted"], va="top")

    def node(x: float, y: float, w: float, h: float, title: str, body: str, color: str, fill: str) -> None:
        rect = plt.Rectangle((x, y), w, h, facecolor=fill, edgecolor=color, linewidth=1.1, joinstyle="round")
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=10, fontweight="bold", color=colors["ink"])
        ax.text(x + w / 2, y + h * 0.33, body, ha="center", va="center", fontsize=8, color=colors["muted"])

    def arrow(x1: float, y1: float, x2: float, y2: float, label: str = "", color: str = colors["line"]) -> None:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops={"arrowstyle": "->", "lw": 1.4, "color": color, "shrinkA": 3, "shrinkB": 3})
        if label:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, fontsize=7.5, color=colors["muted"], ha="center", va="bottom")

    ax.text(0, 7.22, "智演 Agent：面向高密度人群风险复演与干预评估的方法总览", fontsize=17, fontweight="bold", color=colors["navy"], va="top")
    ax.text(0, 6.88, "A deterministic multi-agent simulation loop with event-triggered reasoning and evidence-grounded intervention evaluation", fontsize=9.5, color=colors["muted"], va="top")

    panel(0.2, 0.75, 3.25, 5.45, "A  场景与输入", "Scenario construction", colors["blue"], colors["pale_blue"])
    node(0.52, 4.85, 2.6, 0.78, "场景参数", "geometry · flow · profiles", colors["blue"], "#FFFFFF")
    node(0.52, 3.62, 2.6, 0.78, "个体画像", "normal · group · vulnerable", colors["blue"], "#FFFFFF")
    node(0.52, 2.39, 2.6, 0.78, "事故 / 瓶颈", "funnel · conflict · blockage", colors["blue"], "#FFFFFF")
    ax.text(1.82, 1.31, "same seed\nfor paired replay", ha="center", va="center", fontsize=9, color=colors["blue"], fontweight="bold")

    panel(3.9, 0.75, 4.9, 5.45, "B  快慢双脑仿真", "Fast physics + event-triggered cognition", colors["teal"], colors["pale_teal"])
    node(4.25, 4.55, 4.2, 1.0, "Fast Brain", "vectorized Social Force Model · NumPy", colors["teal"], "#FFFFFF")
    node(4.25, 2.95, 4.2, 1.0, "Slow Brain", "representative Agent reasoning · LLM / local", colors["orange"], "#FFFFFF")
    node(4.25, 1.35, 4.2, 1.0, "State + evidence", "density · velocity · pressure · action logs", colors["navy"], "#FFFFFF")
    arrow(1.95, 4.7, 4.25, 5.05, "initialize", colors["blue"])
    arrow(1.95, 3.47, 4.25, 3.45, "profile", colors["blue"])
    arrow(1.95, 2.74, 4.25, 1.85, "perturb", colors["blue"])
    arrow(6.35, 4.55, 6.35, 3.95, "risk threshold", colors["orange"])
    arrow(6.35, 2.95, 6.35, 2.36, "action mapping", colors["orange"])
    ax.text(8.12, 5.72, "high-frequency", fontsize=8, color=colors["teal"], ha="right")
    ax.text(8.12, 2.61, "event-triggered", fontsize=8, color=colors["orange"], ha="right")

    panel(9.25, 0.75, 2.65, 5.45, "C  证据诊断", "Evidence-grounded analysis", colors["orange"], colors["pale_orange"])
    node(9.57, 4.55, 2.0, 0.9, "RAG", "safety rules", colors["orange"], "#FFFFFF")
    node(9.57, 3.15, 2.0, 0.9, "Risk report", "timeline · excerpts", colors["orange"], "#FFFFFF")
    node(9.57, 1.75, 2.0, 0.9, "Interventions", "guardrail · flow · exits", colors["orange"], "#FFFFFF")
    arrow(8.45, 1.85, 9.57, 3.6, "metrics", colors["navy"])
    arrow(8.45, 3.45, 9.57, 5.0, "logs", colors["navy"])
    arrow(10.57, 4.55, 10.57, 4.05, "retrieve", colors["orange"])
    arrow(10.57, 3.15, 10.57, 2.7, "recommend", colors["orange"])

    panel(12.35, 0.75, 2.95, 5.45, "D  输出与评估", "Decision support", colors["green"], colors["pale_green"])
    node(12.7, 4.55, 2.25, 0.9, "Re-simulation", "same seed · paired", colors["green"], "#FFFFFF")
    node(12.7, 3.15, 2.25, 0.9, "Comparison", "peak density · flow", colors["green"], "#FFFFFF")
    node(12.7, 1.75, 2.25, 0.9, "Artifacts", "Markdown · PDF · JSON", colors["green"], "#FFFFFF")
    arrow(11.57, 2.15, 12.7, 5.0, "parameterize", colors["green"])
    arrow(12.7, 4.55, 12.7, 4.05, "run", colors["green"])
    arrow(12.7, 3.15, 12.7, 2.7, "export", colors["green"])

    _save(fig, "method-overview")


def build_intervention_comparison() -> None:
    data = json.loads((ROOT / "docs" / "results" / "interventions.json").read_text(encoding="utf-8"))
    strategies = {item["strategy"]: item for item in data["strategies"]}
    ordered = [
        data["baseline"],
        strategies["central_guardrail"],
        strategies["one_way_flow"],
        strategies["widen_exits"],
    ]
    density = [item["peak_density_mean"] for item in ordered]
    flow = [float(np.mean([run["exit_pass_rate"] for run in item["runs"]])) for item in ordered]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 4.8), gridspec_kw={"width_ratios": [1.35, 1]}, constrained_layout=True)
    x = np.arange(4)
    bar_colors = ["#667085", "#56B4E9", "#009E73", "#E69F00"]
    bars = ax1.bar(x, density, color=bar_colors, width=0.62, edgecolor="white", linewidth=0.8)
    ax1.set_title("峰值密度 / Peak density", loc="left", fontweight="bold")
    ax1.set_ylabel("峰值密度（人 / m²）")
    ax1.set_xticks(x, ["无干预", "中央护栏", "单向导流", "出口拓宽"])
    ax1.grid(axis="y", color="#EAECF0", linewidth=0.8)
    ax1.set_axisbelow(True)
    ax1.set_ylim(0, 7.5)
    for bar, value in zip(bars, density):
        ax1.text(bar.get_x() + bar.get_width() / 2, value + 0.15, f"{value:.3f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax1.text(0, -0.19, "n = 3 fixed seeds · 300 Agent capacity · 120 steps", transform=ax1.transAxes, fontsize=8.5, color="#667085")

    ax2.plot(x, np.array(flow) * 100, color="#17324D", marker="o", linewidth=2.2, markersize=6, label="Exit pass rate")
    ax2.set_title("出口通过率 / Exit pass rate", loc="left", fontweight="bold")
    ax2.set_ylabel("出口通过率（%）")
    ax2.set_xticks(x, ["无干预", "中央护栏", "单向导流", "出口拓宽"])
    ax2.set_ylim(0, 50)
    ax2.grid(axis="y", color="#EAECF0", linewidth=0.8)
    ax2.set_axisbelow(True)
    for index, value in enumerate(flow):
        ax2.text(index, value * 100 + 1.5, f"{value * 100:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold", color="#17324D")
    ax2.text(0, -0.19, "Peak-density reduction: 0.00%, 7.66%, 23.10%, 7.66%", transform=ax2.transAxes, fontsize=8.5, color="#667085")

    fig.suptitle("干预实验：固定种子成对复演 / Intervention benchmark", x=0.02, ha="left", fontsize=16, fontweight="bold", color="#17324D")
    _save(fig, "intervention-comparison")


if __name__ == "__main__":
    _configure()
    FIGURES.mkdir(parents=True, exist_ok=True)
    build_method_overview()
    build_intervention_comparison()

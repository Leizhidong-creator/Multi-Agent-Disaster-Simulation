from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_follows_research_repository_narrative() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sections = (
        "摘要 / Abstract",
        "方法概览 / Method",
        "主要贡献 / Contributions",
        "实验结果 / Results",
        "系统演示 / Demo",
        "复现指南 / Reproduction",
        "作者贡献 / Author Contributions",
    )

    for section in sections:
        assert section in readme
    for earlier, later in zip(sections, sections[1:]):
        assert readme.index(earlier) < readme.index(later)
    for rejected in ("30 秒看懂项目", "面试官关心的问题", "核心页面"):
        assert rejected not in readme


def test_readme_uses_crisp_generated_assets_before_demo() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assets = (
        "docs/assets/zhiyan-wordmark.svg",
        "docs/assets/method-architecture.svg",
        "docs/assets/results-overview.svg",
    )

    for asset in assets:
        assert asset in readme
    assert readme.index("docs/assets/method-architecture.svg") < readme.index(
        "系统演示 / Demo"
    )
    assert readme.index("docs/assets/results-overview.svg") < readme.index(
        "系统演示 / Demo"
    )


def test_figure_script_reads_all_machine_results() -> None:
    script = (ROOT / "scripts" / "generate_readme_figures.py").read_text(
        encoding="utf-8"
    )
    interventions = json.loads(
        (ROOT / "docs" / "results" / "interventions.json").read_text(
            encoding="utf-8"
        )
    )

    for filename in (
        "interventions.json",
        "benchmark.json",
        "historical-calibration.json",
    ):
        assert filename in script
    assert interventions["baseline"]["peak_density_mean"] == 6.433
    assert interventions["strategies"][1]["reduction_ratio"] == 0.231


def test_result_language_preserves_evidence_boundaries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "复现相对误差 **0.43%**" in readme
    assert "峰值密度降低 **23.10%**" in readme
    assert "Recall@5 约 85%" not in readme
    assert "99.57%" not in readme


def test_publication_assets_are_present_and_nontrivial() -> None:
    for name in (
        "zhiyan-wordmark.svg",
        "method-architecture.svg",
        "method-architecture.png",
        "results-overview.svg",
        "results-overview.png",
    ):
        path = ROOT / "docs" / "assets" / name
        assert path.stat().st_size > 10_000

    for name in (
        "abstract.svg",
        "method.svg",
        "contributions.svg",
        "results.svg",
        "demo.svg",
        "reproduction.svg",
        "structure.svg",
        "limitations.svg",
        "author.svg",
        "references.svg",
    ):
        assert (ROOT / "docs" / "assets" / "icons" / name).stat().st_size > 200

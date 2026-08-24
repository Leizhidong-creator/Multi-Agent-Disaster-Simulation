from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_uses_research_figures_before_product_screenshots() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/assets/method-overview.png" in readme
    assert "docs/assets/intervention-comparison.png" in readme
    assert "docs/assets/zhiyan-simulation-dashboard.png" not in readme
    assert "docs/assets/zhiyan-control-workspace.png" not in readme
    assert readme.index("docs/assets/method-overview.png") < readme.index("## ⚡ 30 秒看懂项目")


def test_intervention_figure_script_reads_machine_results() -> None:
    script = (ROOT / "scripts" / "generate_readme_figures.py").read_text(encoding="utf-8")
    results = json.loads(
        (ROOT / "docs" / "results" / "interventions.json").read_text(encoding="utf-8")
    )

    assert '"docs" / "results" / "interventions.json"' in script
    assert results["baseline"]["peak_density_mean"] == 6.433
    assert results["strategies"][1]["reduction_ratio"] == 0.231


def test_publication_assets_are_present_and_nontrivial() -> None:
    for name in (
        "method-overview.png",
        "method-overview.svg",
        "intervention-comparison.png",
        "intervention-comparison.svg",
    ):
        path = ROOT / "docs" / "assets" / name
        assert path.stat().st_size > 10_000

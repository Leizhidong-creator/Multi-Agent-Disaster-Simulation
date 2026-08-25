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
        "复现指南 / Reproduction",
        "作者贡献 / Author Contributions",
    )

    for section in sections:
        assert section in readme
    for earlier, later in zip(sections, sections[1:]):
        assert readme.index(earlier) < readme.index(later)
    for rejected in (
        "30 秒看懂项目",
        "面试官关心的问题",
        "核心页面",
        "系统演示 / Demo",
    ):
        assert rejected not in readme


def test_readme_uses_research_figures_without_product_screenshots() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/assets/zhiyan-wordmark.svg" in readme
    assert readme.count("docs/assets/method-architecture.svg") == 1
    assert readme.count("docs/assets/results-overview.svg") == 1
    assert readme.count("docs/assets/crowd-distribution-audit.png") == 1
    for rejected_asset in (
        "docs/assets/zhiyan-simulation-dashboard.png",
        "docs/assets/zhiyan-control-workspace.png",
    ):
        assert rejected_asset not in readme


def test_method_figure_source_uses_english_only() -> None:
    script = (ROOT / "scripts" / "generate_readme_figures.py").read_text(
        encoding="utf-8"
    )
    method_source = script[
        script.index("def build_method_architecture") : script.index(
            "def build_results_overview"
        )
    ]

    assert "Interaction Encoder" in method_source
    assert "Evidence\\nReasoner" in method_source
    assert "Counterfactual Evaluator" in method_source
    assert not any("\u4e00" <= character <= "\u9fff" for character in method_source)


def test_figure_script_reads_machine_results_used_by_the_charts() -> None:
    script = (ROOT / "scripts" / "generate_readme_figures.py").read_text(
        encoding="utf-8"
    )
    interventions = json.loads(
        (ROOT / "docs" / "results" / "interventions.json").read_text(
            encoding="utf-8"
        )
    )

    for filename in ("interventions.json", "historical-calibration.json"):
        assert filename in script
    assert interventions["baseline"]["peak_density_mean"] == 6.433
    assert interventions["strategies"][1]["reduction_ratio"] == 0.231


def test_results_figure_shows_individual_runs_and_uncertainty() -> None:
    script = (ROOT / "scripts" / "generate_readme_figures.py").read_text(
        encoding="utf-8"
    )
    results_source = script[
        script.index("def build_results_overview") : script.index(
            'if __name__ == "__main__"'
        )
    ]

    assert '[run["peak_density"] for run in' in results_source
    assert "Standard deviation" in results_source
    assert "Knowledge Base Statistics" not in results_source
    assert "Throughput" not in results_source
    assert not any("\u4e00" <= character <= "\u9fff" for character in results_source)


def test_spatial_figure_is_a_four_slice_publication_audit() -> None:
    script = (ROOT / "scripts" / "verify_phase2_visual.py").read_text(
        encoding="utf-8"
    )

    assert "target_steps = [0, 19, 39, 59]" in script
    assert "Bottleneck Region" in script
    assert "np.histogram2d" in script
    assert 'OUTPUT_PATH = ROOT_DIR / "docs" / "assets" / "crowd-distribution-audit.png"' in script


def test_readme_uses_approved_results_copy() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "| 量化指标 | 测试结果 | 指标说明 |" in readme
    assert "空间演化 / Spatial Evolution" in readme
    assert "公开版同时提供无 API Key" not in readme
    assert "评估问题" not in readme
    assert "实验边界与证据" not in readme
    assert "这里的 `0.43%` 衡量" not in readme

    limitations = readme[
        readme.index("局限性 / Limitations") : readme.index(
            "作者贡献 / Author Contributions"
        )
    ]
    assert limitations.count("\n- **") == 2


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
        "crowd-distribution-audit.png",
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

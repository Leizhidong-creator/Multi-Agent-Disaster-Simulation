import subprocess
import sys
import json
from pathlib import Path

from app.models.schemas import SimulationRequest


ROOT = Path(__file__).resolve().parents[1]


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_simulation_request_accepts_reproducible_seed() -> None:
    assert SimulationRequest(random_seed=20260824).random_seed == 20260824


def test_benchmark_cli_is_available() -> None:
    result = run_script("benchmark_simulation.py", "--help")
    assert result.returncode == 0, result.stderr
    assert "--seed" in result.stdout


def test_intervention_cli_is_available() -> None:
    result = run_script("evaluate_interventions.py", "--help")
    assert result.returncode == 0, result.stderr
    assert "--seeds" in result.stdout


def test_benchmark_writes_reproduction_metadata(tmp_path: Path) -> None:
    output = tmp_path / "benchmark.json"
    result = run_script(
        "benchmark_simulation.py",
        "--agents",
        "20",
        "--steps",
        "40",
        "--seed",
        "20260824",
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["agents"] == 20
    assert payload["steps"] == 40
    assert payload["seed"] == 20260824
    assert payload["steps_per_second"] > 0
    assert payload["peak_density"] >= 0
    assert payload["environment"]["python"]
    assert payload["environment"]["platform"]


def test_intervention_writes_paired_baseline(tmp_path: Path) -> None:
    output = tmp_path / "interventions.json"
    result = run_script(
        "evaluate_interventions.py",
        "--agents",
        "20",
        "--steps",
        "40",
        "--seeds",
        "20260824",
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["seeds"] == [20260824]
    assert payload["agents"] == 20
    assert payload["steps"] == 40
    assert payload["baseline"]["strategy"] == "none"
    assert {item["strategy"] for item in payload["strategies"]} == {
        "central_guardrail",
        "one_way_flow",
        "widen_exits",
    }
    assert all("peak_density_mean" in item for item in payload["strategies"])
    assert all("reduction_ratio" in item for item in payload["strategies"])

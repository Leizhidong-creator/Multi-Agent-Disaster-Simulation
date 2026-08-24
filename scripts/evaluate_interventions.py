from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.schemas import SimulationRequest
from app.services.simulation import simulation_service


STRATEGIES = ("central_guardrail", "one_way_flow", "widen_exits")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate paired Zhiyan intervention simulations.")
    parser.add_argument("--seeds", type=int, nargs="+", default=[20260824, 20260825, 20260826])
    parser.add_argument("--agents", type=int, default=300)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--output", default="docs/results/interventions.json")
    return parser


def reduction_ratio(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return round((before - after) / before, 4)


async def run_once(*, strategy: str, seed: int, agents: int, steps: int) -> dict:
    request = SimulationRequest(
        scenario="mitigation",
        max_agents=agents,
        duration_steps=steps,
        use_api=False,
        random_seed=seed,
        mitigation_strategy=strategy,
    )
    response = await simulation_service.run(request)
    summary = response.summary
    return {
        "seed": seed,
        "peak_density": summary.peak_density,
        "average_peak_density": summary.average_peak_density,
        "dangerous_steps": summary.dangerous_steps,
        "exit_pass_rate": summary.exit_pass_rate,
        "api_calls_used": summary.api_calls_used,
    }


def summarize(strategy: str, runs: list[dict], baseline_mean: float | None = None) -> dict:
    peaks = [float(item["peak_density"]) for item in runs]
    peak_mean = statistics.fmean(peaks) if peaks else 0.0
    payload = {
        "strategy": strategy,
        "peak_density_mean": round(peak_mean, 3),
        "peak_density_std": round(statistics.pstdev(peaks), 3) if len(peaks) > 1 else 0.0,
        "runs": runs,
    }
    if baseline_mean is not None:
        payload["reduction_ratio"] = reduction_ratio(baseline_mean, peak_mean)
    return payload


async def evaluate(*, seeds: list[int], agents: int, steps: int) -> dict:
    baseline_runs = [
        await run_once(strategy="none", seed=seed, agents=agents, steps=steps)
        for seed in seeds
    ]
    baseline = summarize("none", baseline_runs)
    baseline_mean = float(baseline["peak_density_mean"])
    strategies = []
    for strategy in STRATEGIES:
        runs = [
            await run_once(strategy=strategy, seed=seed, agents=agents, steps=steps)
            for seed in seeds
        ]
        strategies.append(summarize(strategy, runs, baseline_mean))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": "mitigation",
        "mode": "local_physics_only",
        "agents": agents,
        "steps": steps,
        "seeds": seeds,
        "baseline": baseline,
        "strategies": strategies,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    payload = asyncio.run(evaluate(seeds=args.seeds, agents=args.agents, steps=args.steps))
    output = Path(args.output)
    write_json(output, payload)
    print(f"Intervention evaluation complete: {len(args.seeds)} paired seed(s) -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

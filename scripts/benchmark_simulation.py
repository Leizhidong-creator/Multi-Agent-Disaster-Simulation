from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.models.schemas import SimulationRequest
from app.services.simulation import simulation_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the local Zhiyan simulation engine.")
    parser.add_argument("--agents", type=int, default=300)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260824)
    parser.add_argument("--output", default="docs/results/benchmark.json")
    return parser


def build_environment() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine() or "unknown",
        "processor": platform.processor() or "unknown",
    }


async def run_benchmark(*, agents: int, steps: int, seed: int) -> dict:
    request = SimulationRequest(
        scenario="accident",
        max_agents=agents,
        duration_steps=steps,
        use_api=False,
        random_seed=seed,
    )
    started = time.perf_counter()
    response = await simulation_service.run(request)
    elapsed = time.perf_counter() - started
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scenario": request.scenario,
        "mode": "local_physics_only",
        "agents": agents,
        "steps": steps,
        "seed": seed,
        "elapsed_seconds": round(elapsed, 4),
        "steps_per_second": round(steps / elapsed, 2),
        "peak_density": response.summary.peak_density,
        "max_agents_seen": response.summary.max_agents_seen,
        "api_calls_used": response.summary.api_calls_used,
        "environment": build_environment(),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    payload = asyncio.run(run_benchmark(agents=args.agents, steps=args.steps, seed=args.seed))
    output = Path(args.output)
    write_json(output, payload)
    print(
        f"Benchmark complete: {payload['steps_per_second']:.2f} step/s, "
        f"peak density {payload['peak_density']:.2f} people/m^2 -> {output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

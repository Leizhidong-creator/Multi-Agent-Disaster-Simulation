from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.engine.rag import generate_diagnostic_report


def main() -> None:
    sample_logs = {
        "peak_density": 13.4,
        "deadlock_seconds": 18.0,
        "slow_brain_trigger_count": 9,
        "scenario": "itaewon-what-if",
        "notes": "双向对冲在漏斗段中央形成锁死，整改前无物理隔离措施。",
        "summary": {
            "peak_density": 13.4,
            "dangerous_steps": 36,
            "density_sample_interval_seconds": 0.5,
            "slow_brain_triggers": 9,
            "final_risk_level": "danger",
            "velocity_decay_ratio": 0.35,
            "mean_velocity_danger_zone": 0.42,
            "conflict_count": 67,
            "exit_pass_rate": 0.38,
            "mean_dwell_time_danger": 12.5,
        },
        "logs": [],
        "density_series": [2.1, 4.5, 7.8, 10.2, 12.8, 13.4, 13.1, 11.9, 10.5, 8.7],
    }
    result = generate_diagnostic_report(sample_logs)
    report_markdown = result.get("report_markdown", "")
    output_path = ROOT_DIR / "artifacts" / "sample_diagnostic_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_markdown, encoding="utf-8")
    print("Sample diagnostic report generated.")
    print(f"Output: {output_path}")
    print(f"Recommended interventions: {len(result.get('recommended_interventions', []))}")


if __name__ == "__main__":
    main()

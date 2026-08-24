from pathlib import Path

from app.models.schemas import SimulationRequest


ROOT = Path(__file__).resolve().parents[1]


def test_simulation_request_defaults_to_local_mode() -> None:
    assert SimulationRequest().use_api is False


def test_explicit_api_mode_is_preserved() -> None:
    assert SimulationRequest(use_api=True).use_api is True


def test_frontend_does_not_enable_api_before_bootstrap() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="use-api" type="checkbox" checked' not in html


def test_frontend_uses_provider_aware_status_without_hardware_claims() -> None:
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "frontend" / "assets" / "app.js").read_text(encoding="utf-8")

    assert "syncProviderState" in script
    assert "llm_provider_ready" in script
    assert "RTX 5070" not in html + script
    assert "LLM Concurrency Pool: Active" not in html + script

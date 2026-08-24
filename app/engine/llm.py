from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None

from app.core.config import settings


@dataclass(slots=True)
class SlowBrainDecision:
    agent_id: int
    action: str
    rationale: str
    displacement: tuple[float, float]


class LLMDecisionMaker:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        system_prompt: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.local_llm_base_url).rstrip("/")
        self.api_key = api_key or settings.local_llm_api_key or "EMPTY"
        self.model = model or settings.local_llm_model
        self.timeout_seconds = timeout_seconds or settings.llm_timeout_seconds
        self.system_prompt = system_prompt or (
            "You are a pedestrian trapped in an extremely congested bidirectional alley. "
            "Read the JSON perception payload and output one JSON object only. "
            "Choose one action from: push_forward, hold_position, step_back, shift_left, shift_right. "
            "Return keys: action, rationale, speed_scale, lateral_bias."
        )
        self._client = (
            AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
            if AsyncOpenAI is not None
            else None
        )

    @property
    def ready(self) -> bool:
        return self._client is not None and bool(self.model)

    async def decide_many(self, requests: list[dict[str, Any]]) -> list[SlowBrainDecision]:
        tasks = [self._decide_single(request) for request in requests]
        return list(await asyncio.gather(*tasks))

    async def _decide_single(self, request: dict[str, Any]) -> SlowBrainDecision:
        if not self.ready:
            raise RuntimeError("LLMDecisionMaker 未配置真实模型，已禁用 fallback。")

        try:
            profile = request.get('profile', 'young woman')
            density = request['density']
            system_prompt = (
                f"You are a {profile} trapped in an extremely congested bidirectional alley (Itaewon). "
                f"Local density is {density:.2f} people/m^2. You are experiencing extreme pressure. "
                "Read the JSON perception payload and output one JSON object only. "
                "Choose one action from: push_forward, hold_position, step_back, shift_left, shift_right. "
                "Return keys: action, rationale, speed_scale, lateral_bias."
            )

            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self.model,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": (
                                "Perception JSON:\n"
                                f"{request['perception_json']}\n"
                                f"Local density: {density:.2f} people/m^2"
                            ),
                        },
                    ],
                ),
                timeout=2.0
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)
            return self._to_decision(request, parsed)
        except Exception:
            raise

    def _to_decision(self, request: dict[str, Any], payload: dict[str, Any]) -> SlowBrainDecision:
        action = str(payload.get("action", "hold_position"))
        rationale = str(payload.get("rationale", "visibility is low and pressure is rising"))
        speed_scale = float(payload.get("speed_scale", 0.45))
        lateral_bias = float(payload.get("lateral_bias", 0.0))

        if action == "push_forward":
            displacement = (speed_scale, lateral_bias)
        elif action == "step_back":
            displacement = (-max(0.2, speed_scale), lateral_bias * 0.5)
        elif action == "shift_left":
            displacement = (0.15, -max(0.25, abs(lateral_bias) or 0.45))
        elif action == "shift_right":
            displacement = (0.15, max(0.25, abs(lateral_bias) or 0.45))
        else:
            displacement = (0.02, lateral_bias * 0.2)

        return SlowBrainDecision(
            agent_id=int(request["agent_id"]),
            action=action,
            rationale=rationale,
            displacement=displacement,
        )

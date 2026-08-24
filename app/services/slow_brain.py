from __future__ import annotations

import json
import traceback
from typing import Any

import httpx

from app.core.config import settings


class SlowBrainService:
    def __init__(self) -> None:
        self._key_cursor = 0

    @property
    def provider_ready(self) -> bool:
        return bool(settings.resolved_llm_api_keys and settings.resolved_llm_base_url and settings.llm_model)

    @property
    def provider_name(self) -> str:
        if len(settings.resolved_llm_api_keys) > 1:
            return "阿里云百炼 / 通义千问兼容接口 (多 Key 轮询)"
        return "阿里云百炼 / 通义千问兼容接口"

    async def generate_reasoning(
        self,
        *,
        agent_id: int,
        local_density: float,
        scenario: str,
        use_api: bool,
        typology: str = "normal_pedestrian",
        mitigation_strategy: str | None = None,
        x: float = 0.0,
        y: float = 0.0,
        vx: float = 0.0,
        vy: float = 0.0,
        neighbor_count: int = 0,
        heard_messages: list[str] | None = None,
        broadcast_radius: float = 0.0,
    ) -> dict[str, Any]:
        if not use_api:
            raise RuntimeError("慢脑已被要求强制走真实 LLM API，但当前请求未启用 `use_api`。")
        if not self.provider_ready:
            raise RuntimeError("未检测到真实 LLM API 配置，已拒绝使用任何 fallback。")

        try:
            return await self._call_remote_llm(
                agent_id=agent_id,
                local_density=local_density,
                scenario=scenario,
                typology=typology,
                mitigation_strategy=mitigation_strategy,
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                neighbor_count=neighbor_count,
                heard_messages=heard_messages or [],
                broadcast_radius=broadcast_radius,
            )
        except Exception:
            traceback.print_exc()
            raise

    async def _call_remote_llm(
        self,
        *,
        agent_id: int,
        local_density: float,
        scenario: str,
        typology: str,
        mitigation_strategy: str | None,
        x: float,
        y: float,
        vx: float,
        vy: float,
        neighbor_count: int,
        heard_messages: list[str],
        broadcast_radius: float,
    ) -> dict[str, Any]:
        api_keys = settings.resolved_llm_api_keys
        if not api_keys:
            raise RuntimeError("未检测到真实 LLM API Key，已拒绝使用任何 fallback。")

        heard_block = "；".join(heard_messages[:4]) if heard_messages else "周围暂时没有清晰呼救声。"
        identity = self._human_typology_label(typology)
        behavior_profile = self._behavior_hint(typology)
        mitigation_label = self._mitigation_label(mitigation_strategy)
        mitigation_block = (
            f"当前现场已部署[{mitigation_label}]。"
            "你必须具体描述这项措施如何改变你身边的人流组织、对向冲撞、与同伴或弱势群体的移动感受。"
            if mitigation_label
            else ""
        )
        prompt = (
            f"你是一个[{identity}]。"
            f"当前场景为[{scenario}]，你位于梨泰院狭窄漏斗巷道中，坐标为({x:.2f}, {y:.2f})，"
            f"速度向量为({vx:.2f}, {vy:.2f})，广播半径为 {broadcast_radius:.2f} 米，"
            f"周围 1.5 米内有 {neighbor_count} 人，局部密度高达 {local_density:.2f} 人/m²。"
            f"你的行为特征是：{behavior_profile}。"
            f"你听到了附近其他人的真实呼救[{heard_block}]。"
            f"{mitigation_block}"
            "请结合你的身份、听到的声音与极度拥挤的现状，"
            "输出你此刻的感知、情绪、意图、对话和动作。"
            "要求内容丰富，包含：1)对周围环境和人的细致观察 2)内心独白和记忆闪回 3)身体感受的详细描述 4)对他人状态的推测。"
        )
        payload = {
            "model": settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是公共安全推演中的单个行人智能体的慢脑 Reasoner。"
                        "请遵循 Talker/Reasoner 分工：Reasoner 负责根据局部观察、邻近呼喊和身份生成结构化信念，Talker 负责输出对话。"
                        "场景固定为梨泰院窄巷高密度踩踏事故复现，且正处在真实危险拥挤状态。"
                        "禁止出现车辆、爆炸、枪击、消防车、机器人、无人机等与该场景无关元素。"
                        "你只能描述拥挤、遮挡、推挤、恐慌、双向对冲、出口不明、呼救扩散、互相拉扯、摔倒风险、沿墙求生等现象。"
                        "如果用户输入里存在中央护栏、单向导流、出口拓宽等干预措施，你必须把这些措施对人流组织的真实影响写进感知、意图和动作。"
                        "你必须站在该行人的第一视角发声，不要全知叙述。"
                        "如果你听见周围其他人的高优先级呼救，你可以因此改变原本意图，转而避让、保护同伴、呼喊求助或沿墙脱困。"
                        "必须只输出合法 JSON 对象，不要输出 markdown，不要额外解释。"
                        "输出字段固定为：perception, emotion, intention, dialogue, action, movement_hint。"
                        "perception 要求：详细描述你看到的周围环境、人群状态、障碍物、光线、声音等感官输入，至少3句话。"
                        "emotion 要求：描述你的情绪变化过程，包含身体感受（如心跳、呼吸、出汗）和心理状态，至少2句话。"
                        "intention 要求：描述你的意图演变，包含对周围人的观察和推测，以及你的应对策略，至少2句话。"
                        "dialogue 要求：输出你此刻会说的话或内心独白，可以包含对特定人的呼喊。"
                        "action 必须是自然语言的一句话，直接描述你将采取的真实动作，不要输出任何 skill 名称。"
                        "movement_hint 要求：描述你下一步的移动方向和策略。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.6,
        }
        last_error: Exception | None = None
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            for api_key in self._iter_api_keys(api_keys):
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                try:
                    response = await client.post(
                        settings.resolved_llm_base_url + "/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    return self._normalize_reasoning_output(
                        parsed,
                        source="llm_api",
                        agent_id=agent_id,
                        typology=typology,
                        local_density=local_density,
                        x=x,
                        y=y,
                        neighbor_count=neighbor_count,
                        heard_messages=heard_messages,
                    )
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"LLM 未返回合法 JSON: {content[:300]}") from exc
                except Exception as exc:
                    last_error = exc
                    continue

        if last_error is None:
            raise RuntimeError("慢脑请求失败，且未捕获到具体异常。")
        raise last_error

    def _iter_api_keys(self, api_keys: list[str]) -> list[str]:
        if not api_keys:
            return []
        start_index = self._key_cursor % len(api_keys)
        self._key_cursor = (self._key_cursor + 1) % len(api_keys)
        return api_keys[start_index:] + api_keys[:start_index]

    def _normalize_reasoning_output(
        self,
        payload: dict[str, Any],
        *,
        source: str,
        agent_id: int,
        typology: str,
        local_density: float,
        x: float,
        y: float,
        neighbor_count: int,
        heard_messages: list[str],
    ) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "source": source,
            "typology": typology,
            "profile_label": self._human_typology_label(typology),
            "local_density": round(local_density, 2),
            "position": {"x": round(x, 2), "y": round(y, 2)},
            "neighbor_count": neighbor_count,
            "heard_messages": heard_messages[:4],
            "perception": str(payload.get("perception") or ""),
            "emotion": str(payload.get("emotion") or ""),
            "intention": str(payload.get("intention") or ""),
            "dialogue": str(payload.get("dialogue") or ""),
            "action": str(payload.get("action") or ""),
            "movement_hint": str(payload.get("movement_hint") or ""),
        }

    def _human_typology_label(self, typology: str) -> str:
        mapping = {
            "normal_pedestrian": "常态行人",
            "group_family": "结伴群体",
            "vulnerable": "弱势群体",
        }
        return mapping.get(typology, "普通行人")

    def _behavior_hint(self, typology: str) -> str:
        hints = {
            "normal_pedestrian": "步速标准，独立寻路，面对拥挤时会优先寻找可通行空隙",
            "group_family": "会优先维持同伴相邻移动，必要时减速等待、拉住同伴或护住队形",
            "vulnerable": "步速较慢，容易被横向挤压带偏，更倾向于呼救、贴边稳住身体或被动避让",
        }
        return hints.get(typology, "以普通行人的方式判断风险并求生")

    def _mitigation_label(self, mitigation_strategy: str | None) -> str:
        mapping = {
            "central_guardrail": "中央护栏分流",
            "one_way_flow": "单向导流",
            "widen_exits": "出口拓宽",
        }
        return mapping.get(str(mitigation_strategy or ""), "")


slow_brain_service = SlowBrainService()

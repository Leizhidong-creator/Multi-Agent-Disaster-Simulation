from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np

WALKABLE = np.int8(0)
WALL = np.int8(1)


@dataclass(slots=True)
class AgentSnapshot:
    agent_id: int
    x: float
    y: float
    vx: float
    vy: float
    local_density: float
    mode: str


@dataclass(slots=True)
class SlowBrainLogEntry:
    step_index: int
    agent_id: int
    density: float
    action: str
    rationale: str


@dataclass(slots=True)
class SimulationSnapshot:
    step_index: int
    sim_time: float
    active_agents: int
    peak_density: float
    max_local_density: float
    density_grid: np.ndarray
    agent_snapshots: list[AgentSnapshot]
    slow_brain_request_count: int = 0
    spawned_agents: int = 0
    exited_agents: int = 0
    frozen_this_step: bool = False
    slow_brain_logs: list[SlowBrainLogEntry] = field(default_factory=list)


class SlowBrainDecisionLike(Protocol):
    agent_id: int
    action: str
    rationale: str
    displacement: tuple[float, float]


class SlowBrainDecisionMaker(Protocol):
    async def decide_many(self, requests: list[dict[str, Any]]) -> list[SlowBrainDecisionLike]:
        ...


@dataclass(slots=True)
class Agent:
    agent_id: int
    x: float
    y: float
    target: tuple[float, float]
    velocity: tuple[float, float] = (0.0, 0.0)
    view_radius: float = 1.5
    radius: float = 0.22
    # Anchored to UCY/ETH dataset average pedestrian speed (1.34m/s)
    preferred_speed: float = 1.34
    mode: str = "fast"
    last_perception_json: str = "{}"
    # Agent Typology: "individual" or "group"
    typology: str = "individual"
    group_id: int | None = None
    profile: str = "young woman"

    def get_local_perception(self, env: SandboxEnvironment) -> str:
        local_grid = env.extract_local_grid(self.x, self.y, self.view_radius)
        nearby_agents = env.query_neighbor_descriptors(
            agent_id=self.agent_id,
            x=self.x,
            y=self.y,
            radius=self.view_radius,
        )
        payload = {
            "agent_id": self.agent_id,
            "profile": self.profile,
            "position": [round(self.x, 2), round(self.y, 2)],
            "target": [round(self.target[0], 2), round(self.target[1], 2)],
            "view_radius_m": round(self.view_radius, 2),
            "local_obstacles": local_grid["obstacles"],
            "nearby_agents": nearby_agents,
        }
        self.last_perception_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return self.last_perception_json

    def fast_brain_step(
        self,
        env: SandboxEnvironment,
        *,
        dt: float,
        local_density: float,
        slow_brain_bias: np.ndarray | None = None,
    ) -> None:
        current = np.array([self.x, self.y], dtype=np.float64)
        target = np.array(self.target, dtype=np.float64)
        desired = target - current
        desired_norm = np.linalg.norm(desired)
        if desired_norm > 1e-6:
            desired = desired / desired_norm

        social_force = env.compute_social_force(self)
        wall_force = env.compute_wall_force(self)

        # Bottleneck slow down zone in the center (simulating the narrow funnel)
        in_bottleneck = (0.40 * env.width_m < self.x < 0.62 * env.width_m)
        if local_density < 2.0:
            density_scale = 1.0
        elif local_density < 5.4:
            # Weidmann-style exponential decay, calibrated to congested_speed at 5.4
            decay_rate = -np.log(max(0.3 / self.preferred_speed, 0.01)) / 3.4
            density_scale = float(np.exp(-decay_rate * (local_density - 2.0)))
        else:
            density_scale = float(max(0.05, 0.3 * np.exp(-0.25 * (local_density - 5.4)) / self.preferred_speed))
        if in_bottleneck and local_density >= 3.0:
            density_scale *= 0.85

        preferred_velocity = desired * (self.preferred_speed * density_scale)

        if slow_brain_bias is not None:
            preferred_velocity = preferred_velocity * 0.55 + slow_brain_bias * self.preferred_speed
            self.mode = "slow"
        else:
            self.mode = "fast"

        # Add lateral perturbation to avoid greedy snake queuing
        lateral_dir = np.array([-desired[1], desired[0]], dtype=np.float64)
        perturbation = lateral_dir * float(np.random.uniform(-0.4, 0.4)) * min(1.0, local_density / 4.0)

        next_velocity = preferred_velocity + social_force + wall_force + perturbation
        speed = np.linalg.norm(next_velocity)
        capped_speed = max(0.05, self.preferred_speed * max(0.1, density_scale))
        if speed > capped_speed:
            next_velocity = next_velocity / speed * capped_speed

        next_position = current + next_velocity * dt
        clamped_position = env.clamp_to_walkable(next_position, self.radius)
        self.x = float(clamped_position[0])
        self.y = float(clamped_position[1])
        self.velocity = (float(next_velocity[0]), float(next_velocity[1]))


class AgentSpawner:
    def __init__(
        self,
        *,
        arrival_rate_left: float,
        arrival_rate_right: float,
        distribution: str = "poisson",
        seed: int | None = None,
    ) -> None:
        if distribution not in {"poisson", "uniform"}:
            raise ValueError("distribution must be 'poisson' or 'uniform'")
        self.arrival_rate_left = arrival_rate_left
        self.arrival_rate_right = arrival_rate_right
        self.distribution = distribution
        self.rng = np.random.default_rng(seed)
        self._uniform_left_budget = 0.0
        self._uniform_right_budget = 0.0
        self._group_id_counter = 1

    def set_arrival_rates(self, *, left: float, right: float) -> None:
        self.arrival_rate_left = max(0.0, left)
        self.arrival_rate_right = max(0.0, right)

    def spawn(self, env: SandboxEnvironment, dt: float) -> list[Agent]:
        left_count, right_count = self._sample_counts(dt)
        created: list[Agent] = []
        created.extend(self._spawn_side(env, "left", left_count))
        created.extend(self._spawn_side(env, "right", right_count))
        return created

    def _sample_counts(self, dt: float) -> tuple[int, int]:
        if self.distribution == "poisson":
            left_count = int(self.rng.poisson(self.arrival_rate_left * dt))
            right_count = int(self.rng.poisson(self.arrival_rate_right * dt))
            return left_count, right_count

        self._uniform_left_budget += self.arrival_rate_left * dt
        self._uniform_right_budget += self.arrival_rate_right * dt
        left_count = int(self._uniform_left_budget)
        right_count = int(self._uniform_right_budget)
        self._uniform_left_budget -= left_count
        self._uniform_right_budget -= right_count
        return left_count, right_count

    def _spawn_side(self, env: SandboxEnvironment, side: str, count: int) -> list[Agent]:
        created: list[Agent] = []
        remaining = count
        import random
        profiles = ["young woman", "middle-aged man", "young man", "elderly"]
        while remaining > 0:
            # Typology: 30% chance for a group of 2-3 (representing companions/couples in Itaewon)
            if remaining >= 2 and self.rng.random() < 0.3:
                group_size = int(self.rng.integers(2, min(4, remaining + 1)))
                group_id = self._group_id_counter
                self._group_id_counter += 1
                typology = "group"
                profile = "couple/group"
            else:
                group_size = 1
                group_id = None
                typology = "individual"
                profile = random.choice(profiles)

            # Try to spawn the whole group close together
            base_spawn = env.pick_spawn_point(side, self.rng)
            if base_spawn is None:
                break

            for i in range(group_size):
                if i == 0:
                    spawn_point = base_spawn
                else:
                    # Perturb spawn point for group members
                    perturb_x = base_spawn[0] + float(self.rng.uniform(-0.3, 0.3))
                    perturb_y = base_spawn[1] + float(self.rng.uniform(-0.3, 0.3))
                    spawn_point = (perturb_x, perturb_y)
                    if not env._spawn_point_clear(spawn_point):
                        continue  # Skip if crowded, even if it breaks the group size

                target = env.right_exit if side == "left" else env.left_exit
                # Base preferred speed is 1.34m/s with std dev 0.26m/s from UCY/ETH
                preferred_speed = max(0.5, random.gauss(1.34, 0.26))
                agent = Agent(
                    agent_id=env.issue_agent_id(),
                    x=float(spawn_point[0]),
                    y=float(spawn_point[1]),
                    target=target,
                    velocity=(0.0, 0.0),
                    view_radius=1.5,
                    preferred_speed=float(preferred_speed),
                    typology=typology,
                    group_id=group_id,
                    profile=profile,
                )
                env.register_agent(agent)
                created.append(agent)
                remaining -= 1

            if remaining <= 0:
                break

        return created


class SandboxEnvironment:
    def __init__(
        self,
        *,
        width_m: float = 5.7,
        height_m: float = 3.2,
        resolution_m: float = 0.1,
        slow_brain_threshold: float = 5.0,
        density_radius_m: float = 1.0,
        spawner: AgentSpawner | None = None,
    ) -> None:
        self.width_m = width_m
        self.height_m = height_m
        self.resolution_m = resolution_m
        self.cols = int(np.ceil(width_m / resolution_m))
        self.rows = int(np.ceil(height_m / resolution_m))
        self.slow_brain_threshold = slow_brain_threshold
        self.density_radius_m = density_radius_m
        self.spawner = spawner
        self.grid = np.full((self.rows, self.cols), WALL, dtype=np.int8)
        self.walkable_mask = np.zeros((self.rows, self.cols), dtype=bool)
        self.density_grid = np.zeros((self.rows, self.cols), dtype=np.float64)
        self.agents: dict[int, Agent] = {}
        self.step_index = 0
        self.sim_time = 0.0
        self.physics_frozen = False
        self._agent_id_counter = 1
        self.left_exit = (0.15, self.height_m / 2.0)
        self.right_exit = (self.width_m - 0.15, self.height_m / 2.0)
        self.layout_profile = self._build_layout_profile()
        self._build_funnel_geometry()
        self.left_spawn_cells = self._collect_spawn_cells("left")
        self.right_spawn_cells = self._collect_spawn_cells("right")

    def issue_agent_id(self) -> int:
        agent_id = self._agent_id_counter
        self._agent_id_counter += 1
        return agent_id

    def register_agent(self, agent: Agent) -> None:
        if not self.is_walkable(agent.x, agent.y):
            raise ValueError("agent position must be on a walkable cell")
        self.agents[agent.agent_id] = agent

    def remove_agent(self, agent_id: int) -> None:
        self.agents.pop(agent_id, None)

    def freeze_physics_time(self) -> None:
        self.physics_frozen = True

    def resume_physics_time(self) -> None:
        self.physics_frozen = False

    def step(self, dt: float) -> SimulationSnapshot:
        spawned_agents = 0
        if self.spawner is not None:
            spawned_agents = len(self.spawner.spawn(self, dt))

        local_densities = self.compute_agent_local_densities()
        for agent in list(self.agents.values()):
            agent.fast_brain_step(env=self, dt=dt, local_density=local_densities.get(agent.agent_id, 0.0))

        exited_agents = self._purge_exited_agents()
        self.step_index += 1
        self.sim_time += dt
        self.density_grid = self.compute_density_grid()
        updated_local_densities = self.compute_agent_local_densities()
        return self._build_snapshot(
            updated_local_densities,
            [],
            spawned_agents=spawned_agents,
            exited_agents=exited_agents,
            slow_brain_request_count=0,
            frozen_this_step=False,
        )

    async def step_async(
        self,
        dt: float,
        decision_maker: SlowBrainDecisionMaker | None = None,
    ) -> SimulationSnapshot:
        spawned_agents = 0
        if self.spawner is not None:
            spawned_agents = len(self.spawner.spawn(self, dt))

        local_densities = self.compute_agent_local_densities()
        slow_logs: list[SlowBrainLogEntry] = []
        slow_actions: dict[int, SlowBrainDecisionLike] = {}
        slow_brain_request_count = 0
        frozen_this_step = False

        if decision_maker is not None:
            requests: list[dict[str, Any]] = []
            for agent in self.agents.values():
                density = local_densities.get(agent.agent_id, 0.0)
                if density < self.slow_brain_threshold:
                    continue
                requests.append(
                    {
                        "agent_id": agent.agent_id,
                        "density": density,
                        "perception_json": agent.get_local_perception(self),
                        "target": agent.target,
                        "position": (agent.x, agent.y),
                        "profile": agent.profile,
                    }
                )

            if requests:
                slow_brain_request_count = len(requests)
                self.freeze_physics_time()
                frozen_this_step = True
                decisions = await decision_maker.decide_many(requests)
                for decision in decisions:
                    slow_actions[decision.agent_id] = decision
                    slow_logs.append(
                        SlowBrainLogEntry(
                            step_index=self.step_index,
                            agent_id=decision.agent_id,
                            density=round(local_densities.get(decision.agent_id, 0.0), 2),
                            action=decision.action,
                            rationale=decision.rationale,
                        )
                    )
                self.resume_physics_time()

        for agent in list(self.agents.values()):
            decision = slow_actions.get(agent.agent_id)
            bias = None
            if decision is not None:
                bias = np.array(decision.displacement, dtype=np.float64)
            agent.fast_brain_step(
                env=self,
                dt=dt,
                local_density=local_densities.get(agent.agent_id, 0.0),
                slow_brain_bias=bias,
            )

        exited_agents = self._purge_exited_agents()
        self.step_index += 1
        self.sim_time += dt
        self.density_grid = self.compute_density_grid()
        updated_local_densities = self.compute_agent_local_densities()
        return self._build_snapshot(
            updated_local_densities,
            slow_logs,
            spawned_agents=spawned_agents,
            exited_agents=exited_agents,
            slow_brain_request_count=slow_brain_request_count,
            frozen_this_step=frozen_this_step,
        )

    def compute_density_grid(self) -> np.ndarray:
        density_grid = np.zeros((self.rows, self.cols), dtype=np.float64)
        if not self.agents:
            return density_grid

        positions = np.array([[agent.x, agent.y] for agent in self.agents.values()], dtype=np.float64)
        sampling_radius = 0.35
        area = np.pi * (sampling_radius**2)
        for row in range(self.rows):
            for col in range(self.cols):
                if not self.walkable_mask[row, col]:
                    continue
                sample_point = np.array(self.grid_to_world(col, row), dtype=np.float64)
                distances = np.linalg.norm(positions - sample_point, axis=1)
                density_grid[row, col] = float(np.sum(distances <= sampling_radius) / area)
        density_grid[~self.walkable_mask] = 0.0
        return density_grid

    def compute_agent_local_densities(self) -> dict[int, float]:
        if not self.agents:
            return {}

        agents = list(self.agents.values())
        positions = np.array([[agent.x, agent.y] for agent in agents], dtype=np.float64)
        deltas = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
        distances = np.linalg.norm(deltas, axis=2)
        within = distances <= self.density_radius_m
        counts = within.sum(axis=1)
        area = np.pi * (self.density_radius_m**2)
        densities = counts / area
        return {
            agent.agent_id: round(float(density), 4)
            for agent, density in zip(agents, densities, strict=True)
        }

    def query_neighbor_descriptors(
        self,
        *,
        agent_id: int,
        x: float,
        y: float,
        radius: float,
    ) -> list[dict[str, float | int]]:
        if not self.agents:
            return []

        descriptors: list[dict[str, float | int]] = []
        origin = np.array([x, y], dtype=np.float64)
        for neighbor in self.agents.values():
            if neighbor.agent_id == agent_id:
                continue
            offset = np.array([neighbor.x, neighbor.y], dtype=np.float64) - origin
            distance = np.linalg.norm(offset)
            if distance > radius:
                continue
            descriptors.append(
                {
                    "id": neighbor.agent_id,
                    "dx": round(float(offset[0]), 2),
                    "dy": round(float(offset[1]), 2),
                    "distance": round(float(distance), 2),
                }
            )
        descriptors.sort(key=lambda item: item["distance"])
        return descriptors[:24]

    def extract_local_grid(self, x: float, y: float, radius: float) -> dict[str, list[list[float]]]:
        center_col, center_row = self.world_to_grid(x, y)
        radius_cells = int(np.ceil(radius / self.resolution_m))
        obstacles: list[list[float]] = []
        for row in range(max(0, center_row - radius_cells), min(self.rows, center_row + radius_cells + 1)):
            for col in range(max(0, center_col - radius_cells), min(self.cols, center_col + radius_cells + 1)):
                world_x, world_y = self.grid_to_world(col, row)
                if (world_x - x) ** 2 + (world_y - y) ** 2 > radius**2:
                    continue
                if self.grid[row, col] == WALL:
                    obstacles.append([round(world_x - x, 2), round(world_y - y, 2)])
        return {"obstacles": obstacles[:40]}

    def compute_social_force(self, agent: Agent) -> np.ndarray:
        if len(self.agents) <= 1:
            return np.zeros(2, dtype=np.float64)

        origin = np.array([agent.x, agent.y], dtype=np.float64)
        neighbors = []
        is_same_group = []
        for other in self.agents.values():
            if other.agent_id == agent.agent_id:
                continue
            neighbors.append([other.x, other.y])
            is_same_group.append(agent.typology == "group" and other.group_id == agent.group_id)

        neighbors_arr = np.array(neighbors, dtype=np.float64)
        same_group_arr = np.array(is_same_group, dtype=bool)

        offsets = origin - neighbors_arr
        distances = np.linalg.norm(offsets, axis=1)
        mask = (distances > 1e-6) & (distances < max(agent.view_radius * 0.8, 1.0))

        if not np.any(mask):
            return np.zeros(2, dtype=np.float64)

        offsets = offsets[mask]
        distances = distances[mask][:, np.newaxis]
        same_group_mask = same_group_arr[mask][:, np.newaxis]

        # Base repulsion: UCY/ETH calibrated parameters
        # weights = A * exp((r_ij - d) / B) approximated here
        weights = np.clip((1.0 / np.maximum(distances, 0.15)) - 0.65, 0.0, 2.0)

        # Typology: Group members have less repulsion and a cohesive attraction if they drift apart
        # Decrease repulsion for same group members
        weights = np.where(same_group_mask, weights * 0.4, weights)

        repulsion = (offsets / distances) * weights
        force = repulsion.sum(axis=0) * 0.08

        # Add cohesive force for groups (pulling them together if distance > 0.4)
        if np.any(same_group_mask):
            cohesion_mask = (distances > 0.4) & same_group_mask
            if np.any(cohesion_mask):
                cohesion_offsets = -offsets[cohesion_mask.flatten()]  # pointing towards neighbor
                cohesion_distances = distances[cohesion_mask.flatten()]
                cohesion_force = (cohesion_offsets / cohesion_distances).sum(axis=0) * 0.05
                force += cohesion_force

        return force

    def compute_wall_force(self, agent: Agent) -> np.ndarray:
        center_col, center_row = self.world_to_grid(agent.x, agent.y)
        radius_cells = max(2, int(np.ceil(agent.view_radius / self.resolution_m)))
        origin = np.array([agent.x, agent.y], dtype=np.float64)
        wall_points: list[list[float]] = []
        for row in range(max(0, center_row - radius_cells), min(self.rows, center_row + radius_cells + 1)):
            for col in range(max(0, center_col - radius_cells), min(self.cols, center_col + radius_cells + 1)):
                if self.grid[row, col] != WALL:
                    continue
                wall_points.append(list(self.grid_to_world(col, row)))

        if not wall_points:
            return np.zeros(2, dtype=np.float64)

        walls = np.array(wall_points, dtype=np.float64)
        offsets = origin - walls
        distances = np.linalg.norm(offsets, axis=1)
        mask = (distances > 1e-6) & (distances < 0.7)
        if not np.any(mask):
            return np.zeros(2, dtype=np.float64)
        offsets = offsets[mask]
        distances = distances[mask][:, np.newaxis]
        weights = np.clip((0.75 / np.maximum(distances, 0.1)) - 0.5, 0.0, 2.0)
        repulsion = (offsets / distances) * weights
        return repulsion.sum(axis=0) * 0.12

    def pick_spawn_point(self, side: str, rng: np.random.Generator) -> tuple[float, float] | None:
        spawn_cells = self.left_spawn_cells if side == "left" else self.right_spawn_cells
        if not spawn_cells:
            return None

        for index in rng.permutation(len(spawn_cells)):
            col, row = spawn_cells[int(index)]
            point = self.grid_to_world(col, row)
            if self._spawn_point_clear(point):
                return point
        return None

    def world_to_grid(self, x: float, y: float) -> tuple[int, int]:
        col = int(np.clip(x / self.resolution_m, 0, self.cols - 1))
        row = int(np.clip(y / self.resolution_m, 0, self.rows - 1))
        return col, row

    def normalized_to_world(self, nx: float, ny: float) -> tuple[float, float]:
        x = float(np.clip(nx, 0.0, 1.0) * self.width_m)
        y = float(np.clip(ny, 0.0, 1.0) * self.height_m)
        return x, y

    def world_to_normalized(self, x: float, y: float) -> tuple[float, float]:
        nx = float(np.clip(x / max(self.width_m, 1e-6), 0.0, 1.0))
        ny = float(np.clip(y / max(self.height_m, 1e-6), 0.0, 1.0))
        return nx, ny

    def grid_to_world(self, col: int, row: int) -> tuple[float, float]:
        x = min(self.width_m - (self.resolution_m / 2.0), (col + 0.5) * self.resolution_m)
        y = min(self.height_m - (self.resolution_m / 2.0), (row + 0.5) * self.resolution_m)
        return x, y

    def is_walkable(self, x: float, y: float) -> bool:
        if not (0.0 <= x <= self.width_m and 0.0 <= y <= self.height_m):
            return False
        col, row = self.world_to_grid(x, y)
        return bool(self.walkable_mask[row, col])

    def clamp_to_walkable(self, point: np.ndarray, radius: float) -> np.ndarray:
        x = float(np.clip(point[0], radius, self.width_m - radius))
        y = float(np.clip(point[1], radius, self.height_m - radius))
        if self.is_walkable(x, y):
            return np.array([x, y], dtype=np.float64)

        center = np.array([x, y], dtype=np.float64)
        best_point = center.copy()
        best_distance = np.inf
        for row in range(self.rows):
            for col in range(self.cols):
                if not self.walkable_mask[row, col]:
                    continue
                candidate = np.array(self.grid_to_world(col, row), dtype=np.float64)
                distance = np.linalg.norm(candidate - center)
                if distance < best_distance:
                    best_distance = distance
                    best_point = candidate
        return best_point

    def get_layout_profile(self) -> dict[str, Any]:
        return self.layout_profile

    def _build_funnel_geometry(self) -> None:
        corridor_polygon = [
            self.normalized_to_world(point[0], point[1])
            for point in self.layout_profile["corridor_polygon"]
        ]

        for row in range(self.rows):
            for col in range(self.cols):
                point = self.grid_to_world(col, row)
                walkable = self._point_in_polygon(point, corridor_polygon)
                self.walkable_mask[row, col] = walkable
                self.grid[row, col] = WALKABLE if walkable else WALL

    def _build_layout_profile(self) -> dict[str, Any]:
        return {
            "scene_name": "Itaewon Hamilton alley core zone",
            "source_note": "Anchored to the Itaewon core choke area, with a pronounced physical funnel to reproduce choke compression.",
            "corridor_polygon": [
                (0.02, 0.18),
                (0.24, 0.12),
                (0.42, 0.28),
                (0.48, 0.37),
                (0.54, 0.39),
                (0.60, 0.30),
                (0.82, 0.16),
                (0.98, 0.18),
                (0.98, 0.82),
                (0.82, 0.84),
                (0.60, 0.70),
                (0.54, 0.61),
                (0.48, 0.63),
                (0.42, 0.72),
                (0.24, 0.88),
                (0.02, 0.82),
            ],
            "context_polygons": [
                [(0.01, 0.02), (0.99, 0.02), (0.90, 0.26), (0.08, 0.30)],
                [(0.08, 0.70), (0.92, 0.74), (0.99, 0.98), (0.01, 0.98)],
            ],
            "hazard_zone": [
                (0.43, 0.32),
                (0.57, 0.32),
                (0.57, 0.68),
                (0.43, 0.68),
            ],
            "mitigation_barriers": [
                [(0.47, 0.26), (0.47, 0.74)],
                [(0.91, 0.50), (0.99, 0.50)],
            ],
            "labels": [
                {"text": "Hamilton Hotel Side", "position": (0.72, 0.05), "tone": "accent"},
                {"text": "Itaewon Station Exit 1", "position": (0.10, 0.92), "tone": "info"},
                {"text": "Physical funnel choke", "position": (0.50, 0.46), "tone": "danger"},
            ],
        }

    def _point_in_polygon(
        self,
        point: tuple[float, float],
        polygon: list[tuple[float, float]],
    ) -> bool:
        x, y = point
        inside = False
        point_count = len(polygon)
        if point_count < 3:
            return False

        j = point_count - 1
        for i in range(point_count):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            intersects = ((yi > y) != (yj > y)) and (
                x < ((xj - xi) * (y - yi) / ((yj - yi) or 1e-9)) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def _collect_spawn_cells(self, side: str) -> list[tuple[int, int]]:
        spawn_band = max(2, int(np.ceil(0.35 / self.resolution_m)))
        if side == "left":
            col_range = range(0, min(self.cols, spawn_band))
        else:
            col_range = range(max(0, self.cols - spawn_band), self.cols)
        cells: list[tuple[int, int]] = []
        for row in range(self.rows):
            for col in col_range:
                if self.walkable_mask[row, col]:
                    cells.append((col, row))
        return cells

    def _spawn_point_clear(self, point: tuple[float, float]) -> bool:
        if not self.agents:
            return True
        candidate = np.array(point, dtype=np.float64)
        positions = np.array([[agent.x, agent.y] for agent in self.agents.values()], dtype=np.float64)
        distances = np.linalg.norm(positions - candidate, axis=1)
        return bool(np.all(distances >= 0.45))

    def _purge_exited_agents(self) -> int:
        removable: list[int] = []
        for agent in self.agents.values():
            target = np.array(agent.target, dtype=np.float64)
            position = np.array([agent.x, agent.y], dtype=np.float64)
            if np.linalg.norm(target - position) <= 0.22:
                removable.append(agent.agent_id)
        for agent_id in removable:
            self.remove_agent(agent_id)
        return len(removable)

    def _build_snapshot(
        self,
        local_densities: dict[int, float],
        slow_logs: list[SlowBrainLogEntry],
        *,
        spawned_agents: int,
        exited_agents: int,
        slow_brain_request_count: int,
        frozen_this_step: bool,
    ) -> SimulationSnapshot:
        peak_density = float(np.max(self.density_grid)) if self.density_grid.size else 0.0
        max_local_density = max(local_densities.values(), default=0.0)
        agent_snapshots = [
            AgentSnapshot(
                agent_id=agent.agent_id,
                x=round(agent.x, 3),
                y=round(agent.y, 3),
                vx=round(agent.velocity[0], 3),
                vy=round(agent.velocity[1], 3),
                local_density=round(local_densities.get(agent.agent_id, 0.0), 3),
                mode=agent.mode,
            )
            for agent in self.agents.values()
        ]
        return SimulationSnapshot(
            step_index=self.step_index,
            sim_time=round(self.sim_time, 3),
            active_agents=len(self.agents),
            peak_density=round(peak_density, 3),
            max_local_density=round(float(max_local_density), 3),
            density_grid=self.density_grid.copy(),
            agent_snapshots=agent_snapshots,
            slow_brain_request_count=slow_brain_request_count,
            spawned_agents=spawned_agents,
            exited_agents=exited_agents,
            frozen_this_step=frozen_this_step,
            slow_brain_logs=slow_logs,
        )

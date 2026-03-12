from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


class MoveByDistanceInput(BaseModel):
    direction: Literal["forward", "backward", "left", "right"] = Field(
        description="Short relative direction to move."
    )
    distance_m: float = Field(
        description="Target distance in meters (must be > 0)."
    )
    speed: float = Field(
        default=0.4,
        description="Normalized movement speed between 0.1 and 1.0.",
    )


def create_move_by_distance_tool(runtime: RobotRuntime):
    @tool("move_by_distance", args_schema=MoveByDistanceInput)
    def move_by_distance(direction: str, distance_m: float, speed: float = 0.4) -> str:
        """Move in a relative direction by distance using duration = distance / speed."""
        requested_distance_m = float(distance_m)
        if requested_distance_m <= 0:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "invalid_distance",
                    "reason": "distance_m must be > 0",
                },
                ensure_ascii=True,
            )

        applied_speed = max(0.1, min(float(speed), 1.0))
        computed_duration_s = requested_distance_m / applied_speed
        move_result = runtime.move_relative(
            direction=direction,
            duration_s=computed_duration_s,
            speed=applied_speed,
        )
        applied_duration_s = float(move_result.get("duration_s", 0.0) or 0.0)
        estimated_distance_m = applied_duration_s * applied_speed
        distance_limited = estimated_distance_m + 1e-9 < requested_distance_m

        return json.dumps(
            {
                "status": move_result.get("status", "error"),
                "direction": direction,
                "target_distance_m": requested_distance_m,
                "target_speed": float(speed),
                "applied_speed": applied_speed,
                "computed_duration_s": computed_duration_s,
                "applied_duration_s": applied_duration_s,
                "estimated_distance_m": estimated_distance_m,
                "distance_limited": distance_limited,
                "move_result": move_result,
            },
            ensure_ascii=True,
        )

    return move_by_distance

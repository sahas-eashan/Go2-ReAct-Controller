from __future__ import annotations

import json
import math
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from unitree_go2_robot_controller.robot_runtime import RobotRuntime

ROTATION_DURATION_SCALE = 1.6


class MotionRotateInput(BaseModel):
    direction: Literal["left", "right"] = Field(
        default="left",
        description="Rotation direction.",
    )
    duration_s: float = Field(
        default=2.0,
        description="Rotate for this duration in seconds when angle_deg is not provided.",
    )
    angle_deg: float = Field(
        default=0.0,
        description="Optional relative angle in degrees. If non-zero, duration is derived from angle and speed.",
    )
    speed: float = Field(
        default=0.6,
        description="Normalized yaw speed between 0.1 and 1.0.",
    )


def create_motion_rotate_tool(runtime: RobotRuntime):
    @tool("motion_rotate", args_schema=MotionRotateInput)
    def motion_rotate(
        direction: str = "left",
        duration_s: float = 2.0,
        angle_deg: float = 0.0,
        speed: float = 0.6,
    ) -> str:
        """Rotate in place using yaw velocity for a duration or relative angle."""
        normalized_direction = direction.strip().lower()
        if normalized_direction not in {"left", "right"}:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "unsupported_direction",
                    "reason": normalized_direction,
                },
                ensure_ascii=True,
            )

        applied_speed = max(0.1, min(float(speed), 1.0))
        requested_angle = float(angle_deg)
        if abs(requested_angle) > 1e-6:
            computed_duration_s = (
                math.radians(abs(requested_angle)) / applied_speed
            ) * ROTATION_DURATION_SCALE
        else:
            computed_duration_s = float(duration_s)

        runtime_direction = "rotate_left" if normalized_direction == "left" else "rotate_right"
        move_result = runtime.move_relative(
            direction=runtime_direction,
            duration_s=computed_duration_s,
            speed=applied_speed,
        )

        return json.dumps(
            {
                "status": move_result.get("status", "error"),
                "direction": normalized_direction,
                "angle_deg": requested_angle,
                "duration_s": computed_duration_s,
                "speed": applied_speed,
                "move_result": move_result,
            },
            ensure_ascii=True,
        )

    return motion_rotate

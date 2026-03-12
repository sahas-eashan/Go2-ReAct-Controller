from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


class MotionMoveTimedInput(BaseModel):
    direction: Literal["forward", "backward", "left", "right"] = Field(
        description="Short relative translation direction."
    )
    duration_s: float = Field(description="How long to move for, in seconds.")
    speed: float = Field(
        default=0.4, description="Normalized movement speed between 0.1 and 1.0."
    )


def create_motion_move_timed_tool(runtime: RobotRuntime):
    @tool("motion_move_timed", args_schema=MotionMoveTimedInput)
    def motion_move_timed(direction: str, duration_s: float, speed: float = 0.4) -> str:
        """Move the robot a short time-based translation in a relative direction."""
        result = runtime.move_relative(
            direction=direction,
            duration_s=duration_s,
            speed=speed,
        )
        return json.dumps(result, ensure_ascii=True)

    return motion_move_timed

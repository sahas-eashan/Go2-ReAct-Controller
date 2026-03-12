from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_posture_stand_tool(runtime: RobotRuntime):
    @tool("posture_stand")
    def posture_stand() -> str:
        """Make the robot rise from sitting."""
        result = runtime.perform_action("stand_up")
        return json.dumps(result, ensure_ascii=True)

    return posture_stand

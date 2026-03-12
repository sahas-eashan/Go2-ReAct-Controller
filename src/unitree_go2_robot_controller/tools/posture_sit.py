from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_posture_sit_tool(runtime: RobotRuntime):
    @tool("posture_sit")
    def posture_sit() -> str:
        """Make the robot sit down."""
        result = runtime.perform_action("sit_down")
        return json.dumps(result, ensure_ascii=True)

    return posture_sit

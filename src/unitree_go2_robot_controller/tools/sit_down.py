from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_sit_down_tool(runtime: RobotRuntime):
    @tool("sit_down")
    def sit_down() -> str:
        """Make the robot sit down."""
        result = runtime.perform_action("sit_down")
        return json.dumps(result, ensure_ascii=True)

    return sit_down

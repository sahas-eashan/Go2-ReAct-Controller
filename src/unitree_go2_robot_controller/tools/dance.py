from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_dance_tool(runtime: RobotRuntime):
    @tool("dance")
    def dance() -> str:
        """Make the robot perform the standard dance action."""
        result = runtime.perform_action("dance")
        return json.dumps(result, ensure_ascii=True)

    return dance

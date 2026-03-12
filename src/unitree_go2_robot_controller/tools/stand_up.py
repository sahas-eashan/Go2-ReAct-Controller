from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_stand_up_tool(runtime: RobotRuntime):
    @tool("stand_up")
    def stand_up() -> str:
        """Make the robot rise from sitting."""
        result = runtime.perform_action("stand_up")
        return json.dumps(result, ensure_ascii=True)

    return stand_up

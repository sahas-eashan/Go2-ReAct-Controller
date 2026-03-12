from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_posture_stretch_tool(runtime: RobotRuntime):
    @tool("posture_stretch")
    def posture_stretch() -> str:
        """Make the robot perform the stretch action."""
        result = runtime.perform_action("stretch")
        return json.dumps(result, ensure_ascii=True)

    return posture_stretch

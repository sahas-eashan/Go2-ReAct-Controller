from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_take_image_tool(runtime: RobotRuntime):
    @tool("take_image")
    def take_image() -> str:
        """Capture and save a color image from the RealSense camera."""
        result = runtime.take_image()
        return json.dumps(result, ensure_ascii=True)

    return take_image

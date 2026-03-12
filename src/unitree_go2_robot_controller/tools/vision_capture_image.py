from __future__ import annotations

import json

from langchain_core.tools import tool

from unitree_go2_robot_controller.robot_runtime import RobotRuntime


def create_vision_capture_image_tool(runtime: RobotRuntime):
    @tool("vision_capture_image")
    def vision_capture_image() -> str:
        """Capture and save a color image from the RealSense camera."""
        result = runtime.take_image()
        return json.dumps(result, ensure_ascii=True)

    return vision_capture_image

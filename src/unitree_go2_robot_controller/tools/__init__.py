from __future__ import annotations

from unitree_go2_robot_controller.config import AppConfig
from unitree_go2_robot_controller.robot_runtime import RobotRuntime
from unitree_go2_robot_controller.tools.analyze_image import create_analyze_image_tool
from unitree_go2_robot_controller.tools.dance import create_dance_tool
from unitree_go2_robot_controller.tools.move_by_distance import create_move_by_distance_tool
from unitree_go2_robot_controller.tools.move_relative import create_move_relative_tool
from unitree_go2_robot_controller.tools.rotate_relative import create_rotate_relative_tool
from unitree_go2_robot_controller.tools.sit_down import create_sit_down_tool
from unitree_go2_robot_controller.tools.stand_up import create_stand_up_tool
from unitree_go2_robot_controller.tools.stretch import create_stretch_tool
from unitree_go2_robot_controller.tools.take_image import create_take_image_tool


def build_tools(config: AppConfig, runtime: RobotRuntime):
    return [
        create_move_relative_tool(runtime),
        create_move_by_distance_tool(runtime),
        create_rotate_relative_tool(runtime),
        create_sit_down_tool(runtime),
        create_stand_up_tool(runtime),
        create_stretch_tool(runtime),
        create_dance_tool(runtime),
        create_take_image_tool(runtime),
        create_analyze_image_tool(config),
    ]

from __future__ import annotations

from unitree_go2_robot_controller.config import AppConfig
from unitree_go2_robot_controller.robot_runtime import RobotRuntime
from unitree_go2_robot_controller.tools.behavior_dance import create_behavior_dance_tool
from unitree_go2_robot_controller.tools.motion_move_distance import (
    create_motion_move_distance_tool,
)
from unitree_go2_robot_controller.tools.motion_move_timed import (
    create_motion_move_timed_tool,
)
from unitree_go2_robot_controller.tools.motion_rotate import create_motion_rotate_tool
from unitree_go2_robot_controller.tools.posture_sit import create_posture_sit_tool
from unitree_go2_robot_controller.tools.posture_stand import create_posture_stand_tool
from unitree_go2_robot_controller.tools.posture_stretch import (
    create_posture_stretch_tool,
)
from unitree_go2_robot_controller.tools.vision_analyze_image import (
    create_vision_analyze_image_tool,
)
from unitree_go2_robot_controller.tools.vision_capture_image import (
    create_vision_capture_image_tool,
)


def build_tools(config: AppConfig, runtime: RobotRuntime):
    return [
        create_motion_move_timed_tool(runtime),
        create_motion_move_distance_tool(runtime),
        create_motion_rotate_tool(runtime),
        create_posture_sit_tool(runtime),
        create_posture_stand_tool(runtime),
        create_posture_stretch_tool(runtime),
        create_behavior_dance_tool(runtime),
        create_vision_capture_image_tool(runtime),
        create_vision_analyze_image_tool(config),
    ]

from __future__ import annotations

import datetime as dt
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image

from unitree_go2_robot_controller.config import AppConfig


def _append_python_search_paths() -> None:
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    search_paths = (
        f"/usr/local/lib/python{version}/pyrealsense2",
        f"/usr/local/lib/python{version}/dist-packages",
        f"/usr/local/lib/python{version}/site-packages",
        "/usr/local/lib/python3.8/pyrealsense2",
        "/usr/local/lib/python3.8/dist-packages",
        "/usr/local/lib/python3.8/site-packages",
        "/usr/lib/python3/dist-packages",
    )
    for path in search_paths:
        if path not in sys.path:
            sys.path.append(path)


def _import_pyrealsense2() -> Any:
    _append_python_search_paths()
    try:
        import pyrealsense2 as rs  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"pyrealsense2_not_found:{exc}") from exc
    return rs


class RobotRuntime:
    def __init__(self, config: AppConfig, network_interface: str):
        self._config = config
        self._network_interface = network_interface.strip()
        if not self._network_interface:
            raise RuntimeError("network_interface is required.")

        self._command_lock = threading.Lock()
        self._camera_lock = threading.Lock()

        self._capture_dir = Path(config.robot_capture_dir).expanduser().resolve()
        self._latest_image_path = Path(config.robot_captured_image_path).expanduser().resolve()
        self._capture_dir.mkdir(parents=True, exist_ok=True)
        self._latest_image_path.parent.mkdir(parents=True, exist_ok=True)

        self._sport_client = self._create_sport_client()
        self._rs = _import_pyrealsense2()
        self._pipeline = self._create_realsense_pipeline()

    def _create_sport_client(self) -> Any:
        try:
            from unitree_sdk2py.core.channel import ChannelFactoryInitialize
            from unitree_sdk2py.go2.sport.sport_client import SportClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(f"unitree_sdk2py_not_found:{exc}") from exc

        ChannelFactoryInitialize(0, self._network_interface)
        sport_client = SportClient()
        sport_client.SetTimeout(10.0)
        sport_client.Init()
        return sport_client

    def _create_realsense_pipeline(self) -> Any:
        pipeline = self._rs.pipeline()
        rs_config = self._rs.config()
        rs_config.enable_stream(
            self._rs.stream.color,
            self._config.realsense_color_width,
            self._config.realsense_color_height,
            self._rs.format.bgr8,
            self._config.realsense_color_fps,
        )
        pipeline.start(rs_config)
        for _ in range(3):
            pipeline.wait_for_frames(timeout_ms=1000)
        return pipeline

    def close(self) -> None:
        try:
            self._pipeline.stop()
        except KeyboardInterrupt:
            pass
        except Exception:
            pass

    def _busy_error(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error_code": "robot_busy",
            "reason": "another_robot_command_is_running",
        }

    def _run_locked(
        self,
        action_name: str,
        handler: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        if not self._command_lock.acquire(blocking=False):
            return self._busy_error()
        try:
            return handler()
        except Exception as exc:
            return {
                "status": "error",
                "error_code": f"{action_name}_failed",
                "reason": str(exc),
            }
        finally:
            self._command_lock.release()

    def _action_spec(self, action_name: str) -> tuple[Callable[[], Any], float]:
        action_map = {
            "sit_down": (self._sport_client.Sit, 8.0),
            "stand_up": (self._sport_client.RiseSit, 8.0),
            "stretch": (self._sport_client.Stretch, 4.0),
            "dance": (self._sport_client.Dance1, 25.0),
        }
        action = action_map.get(action_name.strip().lower())
        if action is None:
            raise RuntimeError(f"unsupported_action:{action_name}")
        return action

    def perform_action(self, action_name: str) -> dict[str, Any]:
        def _handler() -> dict[str, Any]:
            action_func, expected_duration_s = self._action_spec(action_name)
            self._sport_client.StopMove()
            time.sleep(1.0)
            started = time.time()
            action_func()
            remaining = expected_duration_s - (time.time() - started)
            if remaining > 0:
                time.sleep(remaining)
            return {
                "status": "ok",
                "action": action_name.strip().lower(),
            }

        return self._run_locked(action_name.strip().lower(), _handler)

    def move_relative(self, direction: str, duration_s: float, speed: float = 0.4) -> dict[str, Any]:
        normalized_direction = direction.strip().lower()
        speed = max(0.1, min(float(speed), 1.0))
        duration_s = max(0.2, float(duration_s))
        if normalized_direction in {"rotate_left", "rotate_right"}:
            # Rotation usually needs a slightly higher command floor than translation.
            speed = max(0.35, speed)

        velocity_map = {
            "forward": (speed, 0.0, 0.0),
            "backward": (-speed, 0.0, 0.0),
            "left": (0.0, speed, 0.0),
            "right": (0.0, -speed, 0.0),
            "rotate_left": (0.0, 0.0, speed),
            "rotate_right": (0.0, 0.0, -speed),
        }
        velocities = velocity_map.get(normalized_direction)
        if velocities is None:
            return {
                "status": "error",
                "error_code": "unsupported_direction",
                "reason": normalized_direction,
            }

        def _handler() -> dict[str, Any]:
            vx, vy, yaw = velocities
            self._sport_client.StopMove()
            # Re-publish velocity commands while running to avoid controller-side command decay.
            time.sleep(0.2)
            command_period_s = 0.1
            deadline = time.monotonic() + duration_s
            code = 0
            command_count = 0
            while True:
                code = self._sport_client.Move(vx, vy, yaw)
                command_count += 1
                now = time.monotonic()
                if now >= deadline:
                    break
                time.sleep(min(command_period_s, max(0.0, deadline - now)))
            self._sport_client.StopMove()
            return {
                "status": "ok",
                "direction": normalized_direction,
                "duration_s": duration_s,
                "speed": speed,
                "code": code,
                "command_count": command_count,
            }

        return self._run_locked("move_relative", _handler)

    def _capture_color_frame(self) -> np.ndarray:
        frames = self._pipeline.wait_for_frames(timeout_ms=1500)
        color_frame = frames.get_color_frame()
        if not color_frame:
            raise RuntimeError("missing_color_frame")
        frame = np.asanyarray(color_frame.get_data())
        if frame is None or frame.size == 0:
            raise RuntimeError("empty_color_frame")
        return frame

    def take_image(self) -> dict[str, Any]:
        if not self._camera_lock.acquire(blocking=False):
            return {
                "status": "error",
                "error_code": "camera_busy",
                "reason": "another_capture_is_running",
            }
        try:
            frame = self._capture_color_frame()
            timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            image_name = f"img_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
            image_path = self._capture_dir / image_name

            rgb_frame = frame[:, :, ::-1]
            image = Image.fromarray(rgb_frame)
            image.save(image_path, format="JPEG", quality=95)
            shutil.copyfile(image_path, self._latest_image_path)

            return {
                "status": "ok",
                "image_path": str(image_path),
                "latest_image_path": str(self._latest_image_path),
                "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
                "source": "realsense_color",
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_code": "camera_capture_failed",
                "reason": str(exc),
            }
        finally:
            self._camera_lock.release()

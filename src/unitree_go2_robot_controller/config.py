from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(override=False)


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str
    openai_model: str
    openai_vlm_model: str
    robot_capture_dir: str
    robot_captured_image_path: str
    realsense_color_width: int
    realsense_color_height: int
    realsense_color_fps: int
    voice_realtime_model: str
    voice_transcription_model: str
    voice_tts_model: str
    voice_name: str
    go2_ip: str
    go2_speaker_volume: int
    voice_vad_threshold: float
    voice_prefix_padding_ms: int
    voice_silence_duration_ms: int


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def load_config() -> AppConfig:
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required.")

    default_capture_dir = _project_root() / "run" / "captured_images"
    default_image_path = default_capture_dir / "latest.jpg"

    go2_speaker_volume = _get_int("GO2_SPEAKER_VOLUME", 10)
    go2_speaker_volume = max(0, min(go2_speaker_volume, 10))

    return AppConfig(
        openai_api_key=openai_api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini",
        openai_vlm_model=os.getenv("OPENAI_VLM_MODEL", "gpt-4.1-mini").strip()
        or "gpt-4.1-mini",
        robot_capture_dir=os.getenv(
            "ROBOT_CAPTURE_DIR", str(default_capture_dir)
        ).strip()
        or str(default_capture_dir),
        robot_captured_image_path=os.getenv(
            "ROBOT_CAPTURED_IMAGE_PATH", str(default_image_path)
        ).strip()
        or str(default_image_path),
        realsense_color_width=_get_int("REALSENSE_COLOR_WIDTH", 640),
        realsense_color_height=_get_int("REALSENSE_COLOR_HEIGHT", 480),
        realsense_color_fps=_get_int("REALSENSE_COLOR_FPS", 15),
        voice_realtime_model=os.getenv(
            "VOICE_REALTIME_MODEL", "gpt-realtime-mini"
        ).strip()
        or "gpt-realtime-mini",
        voice_transcription_model=os.getenv(
            "VOICE_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
        ).strip()
        or "gpt-4o-mini-transcribe",
        voice_tts_model=os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts").strip()
        or "gpt-4o-mini-tts",
        voice_name=os.getenv("VOICE_NAME", "ash").strip() or "ash",
        go2_ip=os.getenv("GO2_IP", "192.168.123.161").strip() or "192.168.123.161",
        go2_speaker_volume=go2_speaker_volume,
        voice_vad_threshold=float(os.getenv("VOICE_VAD_THRESHOLD", "0.5")),
        voice_prefix_padding_ms=int(os.getenv("VOICE_PREFIX_PADDING_MS", "180")),
        voice_silence_duration_ms=int(
            os.getenv("VOICE_SILENCE_DURATION_MS", "150")
        ),
    )

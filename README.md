# Go2-React-Controller

Single-process Python 3.11 voice agent for Go2 built around a RAI ReAct agent.

Architecture:

- OpenAI Realtime API handles speech input and playback
- RAI ReAct handles planning and tool calling in-process
- Unitree Python SDK `SportClient` handles motion and sport actions directly
- RealSense `pyrealsense2` handles color image capture directly
- No Flask sidecar, FastAPI service, or ROS dependency is required in this build

Current tool set:

- `motion_move_timed`
- `motion_move_distance`
- `motion_rotate`
- `posture_sit`
- `posture_stand`
- `posture_stretch`
- `behavior_dance`
- `vision_capture_image`
- `vision_analyze_image`

## Layout

```text
Go2-React-Controller/
  .env.example
  pyproject.toml
  README.md
  plan.md
  run/
    captured_images/
  src/unitree_go2_robot_controller/
    __main__.py
    audio.py
    config.py
    core.py
    main.py
    prompts.py
    robot_runtime.py
    voice_runtime.py
    tools/
      behavior_dance.py
      motion_move_distance.py
      motion_move_timed.py
      motion_rotate.py
      posture_sit.py
      posture_stand.py
      posture_stretch.py
      vision_analyze_image.py
      vision_capture_image.py
```

## Setup

```bash
cd /home/unitree/Go2-React-Controller
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e /path/to/rai-main/src/rai_core
pip install -e .
cp .env.example .env
```

Required runtime dependencies outside this package:

- `unitree_sdk2py`
- `pyrealsense2`
- OpenAI API access for chat, VLM, and Realtime voice

Set at least:

- `OPENAI_API_KEY`
- `ROBOT_CAPTURE_DIR`
- `ROBOT_CAPTURED_IMAGE_PATH`
- `AMP_OTEL_ENDPOINT` (example: `http://10.224.44.90:22893/otel`)
- `AMP_AGENT_API_KEY`

Optional voice tuning:

- `VOICE_TRANSCRIPTION_MODEL` (default `gpt-4o-mini-transcribe`)
- `VOICE_TTS_MODEL` (default `gpt-4o-mini-tts`)
- `GO2_IP` (go2 backend only, default `192.168.123.161`)
- `GO2_SPEAKER_VOLUME` (go2 backend only, `0..10`, default `10`)
- `VOICE_VAD_THRESHOLD` (default `0.5`)
- `VOICE_PREFIX_PADDING_MS` (default `180`)
- `VOICE_SILENCE_DURATION_MS` (default `150`)

Install Go2 playback dependencies in this environment:

- `go2-webrtc-connect`
- `aiortc`
- `aioice`
- `pyee`

## Run With AMP Tracing (Zero-Code)

Install instrumentation package in this venv:

```bash
cd /home/unitree/Go2-ReAct-Controller
source .venv/bin/activate
pip install amp-instrumentation
```

Set AMP environment variables (or keep them in `.env`):

```bash
export AMP_OTEL_ENDPOINT="http://10.224.44.90:22893/otel"
export AMP_AGENT_API_KEY="<your_agent_api_key>"
```

## Run

Voice mode on the robot:

```bash
cd /home/unitree/Go2-React-Controller
source .venv/bin/activate
set -a && source .env && set +a
amp-instrument unitree-go2-controller voice --interface eth0
```

CLI debug mode over SSH:

```bash
cd /home/unitree/Go2-ReAct-Controller
source .venv/bin/activate
set -a && source .env && set +a
amp-instrument unitree-go2-controller cli --interface eth0
```

Voice behavior:

- microphone audio is sent to OpenAI Realtime
- transcript text is passed directly to the local RAI ReAct agent object
- the agent calls tools in-process when needed
- the final text is played back through the Realtime session

## Captured Images

RealSense captures are saved locally:

- timestamped images in [run/captured_images](/home/unitree/Go2-React-Controller/run/captured_images)
- latest capture at [run/captured_images/latest.jpg](/home/unitree/Go2-React-Controller/run/captured_images/latest.jpg)

`vision_capture_image` captures one RealSense color frame and saves it locally. `vision_analyze_image` defaults to the latest saved image if no path is provided.

## Current Limits

- motion is time-based, not odometry-closed-loop navigation
- only the listed sport actions are exposed
- image capture is RealSense color only in v1

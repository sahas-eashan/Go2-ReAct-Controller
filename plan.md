## Current Build Direction

- Single-process robot-side Python 3.11 app
- Voice-first runtime with OpenAI Realtime
- CLI text mode only for debugging over SSH
- RAI ReAct agent as the core planner and tool caller
- Direct Unitree `SportClient` for robot motion and sport actions
- Direct RealSense `pyrealsense2` color capture for images
- No Flask sidecar
- No FastAPI or HTTP `/chat` service
- No ROS in this version

## Tool Surface

- `move_relative(direction, duration_s, speed)`
- `sit_down()`
- `stand_up()`
- `stretch()`
- `dance()`
- `take_image()`
- `analyze_image(prompt, image_path="")`

## Voice Workflow

- OpenAI Realtime API receives microphone audio
- Realtime transcription becomes plain text
- The transcript is passed directly to the local RAI ReAct agent object
- The agent executes tools in-process when needed
- The final text response is sent back through Realtime for speech playback

## Camera Direction

- Use RealSense, not Unitree `VideoClient`
- Capture color only in v1
- Save timestamped files plus `latest.jpg`
- `analyze_image` defaults to the latest saved image

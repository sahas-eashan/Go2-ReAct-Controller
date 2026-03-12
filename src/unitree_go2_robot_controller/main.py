from __future__ import annotations

import argparse
import asyncio
import json
import logging
import uuid

from unitree_go2_robot_controller.config import load_config
from unitree_go2_robot_controller.core import RobotAgentService
from unitree_go2_robot_controller.robot_runtime import RobotRuntime
from unitree_go2_robot_controller.voice_runtime import RealtimeVoiceRuntime


def _run_cli(agent_service: RobotAgentService) -> int:
    session_id = uuid.uuid4().hex
    print("CLI debug mode. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print()
            return 0

        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            return 0

        result = agent_service.chat(text=text, session_id=session_id)
        if result.get("status") == "ok":
            print(result.get("response", "").strip())
        else:
            print(json.dumps(result, ensure_ascii=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Unitree Go2 RAI agent")
    parser.add_argument(
        "mode",
        choices=["cli", "voice"],
        help="Run the CLI debug loop or the local Realtime voice runtime.",
    )
    parser.add_argument(
        "--interface",
        required=True,
        help="Network interface used by the Unitree SDK, for example eth0.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("rai.initialization.model_initialization").setLevel(logging.ERROR)
    config = load_config()
    runtime = RobotRuntime(config, network_interface=args.interface)
    agent_service = RobotAgentService(config, runtime)
    try:
        if args.mode == "cli":
            return _run_cli(agent_service)
        asyncio.run(RealtimeVoiceRuntime(config, agent_service).run())
        return 0
    except KeyboardInterrupt:
        logging.info("Interrupted by user.")
        return 130
    finally:
        try:
            runtime.close()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

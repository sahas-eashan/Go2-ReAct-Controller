from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid

from openai import AsyncOpenAI, OpenAI

from unitree_go2_robot_controller.audio import SAMPLE_RATE, stream_microphone_audio
from unitree_go2_robot_controller.config import AppConfig
from unitree_go2_robot_controller.core import RobotAgentService
from unitree_go2_robot_controller.speaker_backends import build_speaker_backend


VOICE_LAYER_PROMPT = (
    "You are the voice transport layer for a robot agent. "
    "Do not answer user questions yourself. "
    "You only transcribe user speech and speak back the exact assistant text provided by the application."
)

class RealtimeVoiceRuntime:
    def __init__(self, config: AppConfig, agent_service: RobotAgentService):
        self._config = config
        self._agent_service = agent_service
        self._client = AsyncOpenAI(api_key=config.openai_api_key)
        self._tts_client = OpenAI(api_key=config.openai_api_key)
        self._speaker = build_speaker_backend(config)
        self._session_id = uuid.uuid4().hex
        logging.info(
            "Audio output configured: go2_ip=%s go2_volume=%s",
            config.go2_ip,
            config.go2_speaker_volume,
        )

    async def _ask_agent(self, text: str) -> str:
        result = await asyncio.to_thread(
            self._agent_service.chat,
            text,
            self._session_id,
        )
        if result.get("status") != "ok":
            raise RuntimeError(json.dumps(result, ensure_ascii=True))
        return str(result.get("response", "")).strip()

    def _synthesize_tts_pcm(self, text: str) -> bytes:
        response = self._tts_client.audio.speech.create(
            model=self._config.voice_tts_model,
            voice=self._config.voice_name,
            input=text,
            response_format="pcm",
        )
        return response.read()

    async def _speak_text(self, text: str) -> None:
        if not text:
            return
        self._speaker.clear()
        pcm = await asyncio.to_thread(self._synthesize_tts_pcm, text)
        response_id = f"tts_{uuid.uuid4().hex}"
        self._speaker.add_pcm16(response_id=response_id, pcm_bytes=pcm)
        await self._speaker.finalize_response(response_id)

    async def run(self) -> None:
        async with self._client.realtime.connect(
            model=self._config.voice_realtime_model
        ) as connection:
            await self._speaker.start()
            await connection.session.update(
                session={
                    "type": "realtime",
                    "instructions": VOICE_LAYER_PROMPT,
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                            "noise_reduction": {"type": "near_field"},
                            "transcription": {
                                "model": self._config.voice_transcription_model,
                                "language": "en",
                            },
                            "turn_detection": {
                                "type": "server_vad",
                                "threshold": self._config.voice_vad_threshold,
                                "prefix_padding_ms": self._config.voice_prefix_padding_ms,
                                "silence_duration_ms": self._config.voice_silence_duration_ms,
                                "create_response": False,
                            },
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                            "voice": self._config.voice_name,
                        },
                    },
                }
            )

            mic_task = asyncio.create_task(stream_microphone_audio(connection))
            try:
                async for event in connection:
                    if event.type == "conversation.item.input_audio_transcription.completed":
                        transcript = str(getattr(event, "transcript", "")).strip()
                        if not transcript:
                            continue
                        if self._speaker.is_busy():
                            logging.info("Ignoring transcript while speaker is active: %s", transcript)
                            continue
                        logging.info("Transcript: %s", transcript)
                        reply = await self._ask_agent(transcript)
                        logging.info("Agent reply: %s", reply)
                        await self._speak_text(reply)
                        continue

                    if event.type == "error":
                        logging.error("Realtime error event: %s", event)
            finally:
                mic_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await mic_task
                await self._speaker.close()

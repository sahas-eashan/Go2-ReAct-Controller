from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import io
import json
import logging
import os
import tempfile
import time
import uuid
import wave
from pathlib import Path
from typing import Any

from unitree_go2_robot_controller.audio import SAMPLE_RATE
from unitree_go2_robot_controller.config import AppConfig


class BaseSpeakerBackend:
    async def start(self) -> None:
        return

    def clear(self) -> None:
        return

    def add_pcm16(self, response_id: str, pcm_bytes: bytes) -> None:
        raise NotImplementedError

    async def finalize_response(self, response_id: str) -> None:
        return

    async def close(self) -> None:
        return

    def is_busy(self) -> bool:
        return False


class Go2SpeakerBackend(BaseSpeakerBackend):
    _SUPPRESSED_DRIVER_LOG_FRAGMENTS = (
        "An error occurred with the old method:",
        "HTTPConnectionPool(host=",
        "Trying to send SDP using the old method...",
        "Falling back to the new method...",
    )

    def __init__(
        self,
        go2_ip: str,
        volume: int,
        sample_rate: int = SAMPLE_RATE,
    ):
        if sample_rate != 24000:
            raise RuntimeError(
                f"Go2 speaker backend requires SAMPLE_RATE=24000 (got {sample_rate})."
            )
        self._go2_ip = go2_ip
        self._volume = max(0, min(int(volume), 10))
        self._sample_rate = sample_rate
        # Keep playback responsive: larger upload chunks and no artificial delay.
        self._tail_wait_s = 0.10
        self._upload_chunk_base64_size = 65536
        self._upload_chunk_sleep_s = 0.00
        self._generation = 0
        self._buffers: dict[str, bytearray] = {}
        self._buffer_generation: dict[str, int] = {}
        self._queue: asyncio.Queue[tuple[str, bytes, int] | None] = asyncio.Queue()
        self._active_playback = False
        self._worker: asyncio.Task[None] | None = None

        self._Go2WebRTCConnection = None
        self._WebRTCConnectionMethod = None
        self._WebRTCAudioHub = None
        self._AUDIO_API = None

    async def start(self) -> None:
        if self._worker is not None:
            return
        self._load_webrtc_dependencies()
        self._worker = asyncio.create_task(self._worker_loop())

    def clear(self) -> None:
        self._buffers.clear()
        self._buffer_generation.clear()
        self._generation += 1

    def is_busy(self) -> bool:
        return self._active_playback or (not self._queue.empty()) or bool(self._buffers)

    def add_pcm16(self, response_id: str, pcm_bytes: bytes) -> None:
        if not pcm_bytes:
            return
        key = response_id.strip() or f"resp_{uuid.uuid4().hex}"
        bucket = self._buffers.get(key)
        if bucket is None:
            bucket = bytearray()
            self._buffers[key] = bucket
            self._buffer_generation[key] = self._generation
        bucket.extend(pcm_bytes)

    async def finalize_response(self, response_id: str) -> None:
        key = response_id.strip()
        if not key:
            return
        payload = self._buffers.pop(key, None)
        generation = self._buffer_generation.pop(key, self._generation)
        if payload:
            await self._queue.put((key, bytes(payload), generation))

    async def close(self) -> None:
        # Best effort flush buffered audio before shutdown.
        pending_ids = list(self._buffers.keys())
        for response_id in pending_ids:
            await self.finalize_response(response_id)

        if self._worker is None:
            return
        await self._queue.put(None)
        with contextlib.suppress(Exception):
            await self._worker
        self._worker = None

    def _load_webrtc_dependencies(self) -> None:
        try:
            from go2_webrtc_driver.webrtc_audiohub import WebRTCAudioHub
            from go2_webrtc_driver.webrtc_driver import Go2WebRTCConnection
            from go2_webrtc_driver.constants import AUDIO_API, WebRTCConnectionMethod
        except Exception as exc:
            raise RuntimeError(
                "Go2 speaker playback requires go2-webrtc-connect to be installed "
                "in this project venv."
            ) from exc

        self._Go2WebRTCConnection = Go2WebRTCConnection
        self._WebRTCConnectionMethod = WebRTCConnectionMethod
        self._WebRTCAudioHub = WebRTCAudioHub
        self._AUDIO_API = AUDIO_API

    @staticmethod
    def _parse_data_json_field(resp: dict[str, Any]) -> dict[str, Any]:
        raw = resp.get("data", {}).get("data", {})
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
        if isinstance(raw, dict):
            return raw
        return {}

    def _parse_audiohub_payload(self, resp: dict[str, Any]) -> list[dict[str, Any]]:
        data = self._parse_data_json_field(resp)
        items = data.get("audio_list", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_driver_exception(exc: BaseException) -> BaseException:
        # Some go2_webrtc_driver branches still call sys.exit(1).
        if isinstance(exc, SystemExit):
            code = getattr(exc, "code", None)
            return RuntimeError(f"go2_webrtc_driver exited unexpectedly (code={code}).")
        return exc

    @staticmethod
    def _pick_latest(items: list[dict[str, Any]], name_contains: str = "") -> dict[str, Any] | None:
        needle = name_contains.lower().strip()
        candidates: list[dict[str, Any]] = []
        for item in items:
            name = str(item.get("CUSTOM_NAME") or item.get("name") or "")
            if needle and needle not in name.lower():
                continue
            candidates.append(item)
        if not candidates:
            return None
        return max(candidates, key=lambda x: int(x.get("ADD_TIME", 0) or 0))

    @staticmethod
    def _pick_unique_id(item: dict[str, Any]) -> str:
        return str(item.get("UNIQUE_ID") or item.get("unique_id") or item.get("uuid") or "").strip()

    async def _set_vui_volume(self, conn: Any, level: int) -> bool:
        resp = await conn.datachannel.pub_sub.publish_request_new(
            "rt/api/vui/request",
            {"api_id": 1003, "parameter": json.dumps({"volume": level})},
        )
        status = resp.get("data", {}).get("header", {}).get("status", {}).get("code", 1)
        return int(status) == 0

    def _write_pcm_to_wav(self, pcm_bytes: bytes) -> tuple[Path, float]:
        fd, temp_name = tempfile.mkstemp(prefix="go2_tts_", suffix=".wav")
        os.close(fd)
        temp_path = Path(temp_name)
        with wave.open(str(temp_path), "wb") as wavf:
            wavf.setnchannels(1)
            wavf.setsampwidth(2)
            wavf.setframerate(self._sample_rate)
            wavf.writeframes(pcm_bytes)

        duration_s = max(0.5, len(pcm_bytes) / float(self._sample_rate * 2))
        return temp_path, duration_s

    async def _upload_audio_file_fast(self, hub: Any, wav_path: Path) -> None:
        assert self._AUDIO_API is not None
        audio_data = wav_path.read_bytes()
        file_md5 = hashlib.md5(audio_data).hexdigest()
        b64_data = base64.b64encode(audio_data).decode("ascii")
        chunks = [
            b64_data[i : i + self._upload_chunk_base64_size]
            for i in range(0, len(b64_data), self._upload_chunk_base64_size)
        ]
        total_chunks = len(chunks)
        if total_chunks <= 0:
            raise RuntimeError("No audio chunks generated for upload.")

        for idx, chunk in enumerate(chunks, start=1):
            payload = {
                "file_name": wav_path.stem,
                "file_type": "wav",
                "file_size": len(audio_data),
                "current_block_index": idx,
                "total_block_number": total_chunks,
                "block_content": chunk,
                "current_block_size": len(chunk),
                "file_md5": file_md5,
                "create_time": int(time.time() * 1000),
            }
            await hub.data_channel.pub_sub.publish_request_new(
                "rt/api/audiohub/request",
                {
                    "api_id": self._AUDIO_API["UPLOAD_AUDIO_FILE"],
                    "parameter": json.dumps(payload, ensure_ascii=True),
                },
            )
            if self._upload_chunk_sleep_s > 0.0 and idx < total_chunks:
                await asyncio.sleep(self._upload_chunk_sleep_s)

    @staticmethod
    def _is_benign_webrtc_teardown_context(context: dict[str, Any]) -> bool:
        exc = context.get("exception")
        if exc is not None and exc.__class__.__name__ == "MediaStreamError":
            return True
        message = str(context.get("message", "") or "")
        if "MediaStreamError" in message and "AsyncIOEventEmitter" in message:
            return True
        return False

    @contextlib.contextmanager
    def _suppress_benign_webrtc_teardown_errors(self):  # type: ignore[no-untyped-def]
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            yield
            return

        previous_handler = loop.get_exception_handler()

        def _handler(loop_obj: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
            if self._is_benign_webrtc_teardown_context(context):
                return
            if previous_handler is not None:
                previous_handler(loop_obj, context)
            else:
                loop_obj.default_exception_handler(context)

        loop.set_exception_handler(_handler)
        try:
            yield
        finally:
            loop.set_exception_handler(previous_handler)

    @contextlib.contextmanager
    def _suppress_known_driver_log_noise(self):  # type: ignore[no-untyped-def]
        class _NoiseFilter(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                msg = record.getMessage()
                return not any(
                    fragment in msg
                    for fragment in Go2SpeakerBackend._SUPPRESSED_DRIVER_LOG_FRAGMENTS
                )

        root_logger = logging.getLogger()
        noise_filter = _NoiseFilter()
        for handler in root_logger.handlers:
            handler.addFilter(noise_filter)
        try:
            yield
        finally:
            for handler in root_logger.handlers:
                with contextlib.suppress(Exception):
                    handler.removeFilter(noise_filter)

    async def _upload_and_play_once(self, wav_path: Path, wav_duration: float) -> None:
        assert self._Go2WebRTCConnection is not None
        assert self._WebRTCConnectionMethod is not None
        assert self._WebRTCAudioHub is not None

        root_logger = logging.getLogger()
        previous_level = root_logger.level
        sink = io.StringIO()
        conn = None
        with self._suppress_benign_webrtc_teardown_errors():
            try:
                # go2_webrtc_driver logs full audio chunks at INFO. Keep app logs readable.
                root_logger.setLevel(max(previous_level, logging.WARNING))
                with self._suppress_known_driver_log_noise():
                    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                        conn = self._Go2WebRTCConnection(
                            self._WebRTCConnectionMethod.LocalSTA, ip=self._go2_ip
                        )
                        await conn.connect()
                        volume_ok = await self._set_vui_volume(conn, self._volume)
                        if not volume_ok:
                            logging.warning("Failed to set Go2 volume to %s", self._volume)

                        hub = self._WebRTCAudioHub(conn)
                        try:
                            await self._upload_audio_file_fast(hub, wav_path)
                        except Exception:
                            # Keep compatibility with driver internals if fast path changes.
                            await hub.upload_audio_file(str(wav_path))
                        items = self._parse_audiohub_payload(await hub.get_audio_list())
                        selected = self._pick_latest(items, name_contains=wav_path.stem) or self._pick_latest(items)
                        if selected is None:
                            raise RuntimeError("Uploaded audio but no AudioHub item found.")

                        uid = self._pick_unique_id(selected)
                        if not uid:
                            raise RuntimeError("AudioHub item missing unique id.")
                        await hub.play_by_uuid(uid)
                        await asyncio.sleep(wav_duration + self._tail_wait_s)
            except BaseException as exc:
                normalized = self._normalize_driver_exception(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
            finally:
                root_logger.setLevel(previous_level)
                if conn is not None:
                    with contextlib.suppress(Exception):
                        with self._suppress_known_driver_log_noise():
                            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                                await conn.disconnect()

    async def _worker_loop(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            response_id, pcm_bytes, generation = item
            wav_path: Path | None = None
            try:
                if generation != self._generation:
                    self._queue.task_done()
                    continue
                wav_path, wav_duration = self._write_pcm_to_wav(pcm_bytes)
                logging.info(
                    "Go2 speaker playback: response_id=%s bytes=%s duration=%.2fs volume=%s ip=%s",
                    response_id,
                    len(pcm_bytes),
                    wav_duration,
                    self._volume,
                    self._go2_ip,
                )
                self._active_playback = True
                await self._upload_and_play_once(wav_path=wav_path, wav_duration=wav_duration)
            except asyncio.CancelledError:
                raise
            except BaseException:
                # Never let driver-level BaseException (for example SystemExit) kill voice runtime.
                logging.exception("Go2 speaker playback failed for response_id=%s", response_id)
            finally:
                self._active_playback = False
                if wav_path is not None:
                    with contextlib.suppress(Exception):
                        wav_path.unlink()
                self._queue.task_done()


def build_speaker_backend(config: AppConfig) -> BaseSpeakerBackend:
    return Go2SpeakerBackend(
        go2_ip=config.go2_ip,
        volume=config.go2_speaker_volume,
        sample_rate=SAMPLE_RATE,
    )

from __future__ import annotations

import asyncio
import base64
import threading

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 24000
CHANNELS = 1
CHUNK_LENGTH_S = 0.05


class AudioPlayer:
    def __init__(self, output_gain: float = 1.0, output_device: str | int | None = None) -> None:
        self._queue: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._output_gain = max(0.0, float(output_gain))
        device_arg: str | int | None = output_device
        if isinstance(output_device, str):
            normalized = output_device.strip()
            if not normalized or normalized.lower() == "default":
                device_arg = None
            elif normalized.isdigit():
                device_arg = int(normalized)
            else:
                device_arg = normalized
        self._stream = sd.OutputStream(
            callback=self._callback,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.int16,
            blocksize=int(CHUNK_LENGTH_S * SAMPLE_RATE),
            device=device_arg,
        )
        self._started = False

    def _callback(self, outdata, frames, time, status):  # noqa: ANN001
        with self._lock:
            data = np.empty(0, dtype=np.int16)
            while len(data) < frames and self._queue:
                chunk = self._queue.pop(0)
                frames_needed = frames - len(data)
                data = np.concatenate((data, chunk[:frames_needed]))
                if len(chunk) > frames_needed:
                    self._queue.insert(0, chunk[frames_needed:])

            if len(data) < frames:
                data = np.concatenate(
                    (data, np.zeros(frames - len(data), dtype=np.int16))
                )
        outdata[:] = data.reshape(-1, 1)

    def add_pcm16(self, data: bytes) -> None:
        chunk = np.frombuffer(data, dtype=np.int16)
        if self._output_gain != 1.0 and chunk.size > 0:
            scaled = chunk.astype(np.float32) * self._output_gain
            chunk = np.clip(scaled, -32768, 32767).astype(np.int16)
        with self._lock:
            self._queue.append(chunk)
        if not self._started:
            self._stream.start()
            self._started = True

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def close(self) -> None:
        if self._started:
            self._stream.stop()
        self._stream.close()
        self._started = False


async def stream_microphone_audio(connection) -> None:  # noqa: ANN001
    read_size = int(SAMPLE_RATE * 0.02)
    stream = sd.InputStream(
        channels=CHANNELS,
        samplerate=SAMPLE_RATE,
        dtype="int16",
    )
    stream.start()
    try:
        while True:
            if stream.read_available < read_size:
                await asyncio.sleep(0.01)
                continue

            data, _ = stream.read(read_size)
            await connection.send(
                {
                    "type": "input_audio_buffer.append",
                    "audio": base64.b64encode(data).decode("utf-8"),
                }
            )
            await asyncio.sleep(0)
    finally:
        stream.stop()
        stream.close()

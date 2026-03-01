"""
Real-time transcription using Voxtral Mini Transcribe Realtime.
Based on Mistral AI Realtime API documentation.
"""

import asyncio
import os
from typing import AsyncIterator, Callable, Optional

from mistralai import Mistral
from mistralai.extra.realtime import UnknownRealtimeEvent
from mistralai.models import (
    AudioFormat,
    RealtimeTranscriptionError,
    RealtimeTranscriptionSessionCreated,
    TranscriptionStreamDone,
    TranscriptionStreamTextDelta,
)


class VoxtralTranscriber:
    """
    Real-time transcriber using Voxtral Mini Transcribe Realtime model.
    
    Args:
        api_key: Mistral API key. If not provided, uses MISTRAL_API_KEY env var.
        model: Model ID to use for transcription.
        sample_rate: Audio sample rate in Hz (default: 16000).
        encoding: Audio encoding format (default: "pcm_s16le").
        target_delay_ms: Target streaming delay in milliseconds for improved accuracy.
    """
    
    DEFAULT_MODEL = "voxtral-mini-transcribe-realtime-2602"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        sample_rate: int = 16000,
        encoding: str = "pcm_s16le",
        target_delay_ms: Optional[int] = None,
    ):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Mistral API key is required. Provide it as an argument or "
                "set the MISTRAL_API_KEY environment variable."
            )
        
        self.model = model
        self.audio_format = AudioFormat(encoding=encoding, sample_rate=sample_rate)
        self.target_delay_ms = target_delay_ms
        self.client = Mistral(api_key=self.api_key)
        
        # Callbacks for real-time updates
        self.on_text_delta: Optional[Callable[[str], None]] = None
        self.on_session_created: Optional[Callable[[], None]] = None
        self.on_transcription_done: Optional[Callable[[], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
    ) -> str:
        """
        Transcribe audio from an async stream.
        
        Args:
            audio_stream: Async iterator yielding audio chunks as bytes.
            
        Returns:
            The complete transcribed text.
        """
        full_text = ""
        
        kwargs = {
            "audio_stream": audio_stream,
            "model": self.model,
            "audio_format": self.audio_format,
        }
        if self.target_delay_ms is not None:
            kwargs["target_streaming_delay_ms"] = self.target_delay_ms
        
        async for event in self.client.audio.realtime.transcribe_stream(**kwargs):
            if isinstance(event, RealtimeTranscriptionSessionCreated):
                if self.on_session_created:
                    self.on_session_created()
                    
            elif isinstance(event, TranscriptionStreamTextDelta):
                full_text += event.text
                if self.on_text_delta:
                    self.on_text_delta(event.text)
                    
            elif isinstance(event, TranscriptionStreamDone):
                if self.on_transcription_done:
                    self.on_transcription_done()
                break
                
            elif isinstance(event, RealtimeTranscriptionError):
                error_msg = f"Transcription error: {event.error}"
                if self.on_error:
                    self.on_error(error_msg)
                raise RuntimeError(error_msg)
                
            elif isinstance(event, UnknownRealtimeEvent):
                continue
        
        return full_text
    
    async def transcribe_microphone(
        self,
        chunk_duration_ms: int = 480,
    ) -> str:
        """
        Transcribe audio directly from the microphone.
        
        Args:
            chunk_duration_ms: Duration of each audio chunk in milliseconds.
            
        Returns:
            The complete transcribed text.
        """
        audio_stream = self._iter_microphone(chunk_duration_ms)
        return await self.transcribe_stream(audio_stream)
    
    def _iter_microphone(
        self,
        chunk_duration_ms: int,
    ) -> AsyncIterator[bytes]:
        """
        Create an async iterator that yields microphone PCM chunks.
        
        Args:
            chunk_duration_ms: Duration of each audio chunk in milliseconds.
            
        Yields:
            Audio chunks as bytes.
        """
        return iter_microphone(
            sample_rate=self.audio_format.sample_rate,
            chunk_duration_ms=chunk_duration_ms,
        )


async def iter_microphone(
    *,
    sample_rate: int,
    chunk_duration_ms: int,
) -> AsyncIterator[bytes]:
    """
    Yield microphone PCM chunks using PyAudio (16-bit mono).
    Encoding is always pcm_s16le.
    
    Args:
        sample_rate: Audio sample rate in Hz.
        chunk_duration_ms: Duration of each audio chunk in milliseconds.
        
    Yields:
        Audio chunks as bytes.
    """
    import pyaudio
    
    p = pyaudio.PyAudio()
    chunk_samples = int(sample_rate * chunk_duration_ms / 1000)
    
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_samples,
    )
    
    loop = asyncio.get_running_loop()
    try:
        while True:
            # stream.read is blocking; run it off-thread
            data = await loop.run_in_executor(None, stream.read, chunk_samples, False)
            yield data
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


class DualDelayTranscriber:
    """
    Dual-delay transcriber using both fast and slow streams for optimal
    balance between speed and accuracy.
    
    Args:
        api_key: Mistral API key.
        model: Model ID to use.
        sample_rate: Audio sample rate in Hz.
        fast_delay_ms: Target delay for fast stream (default: 240).
        slow_delay_ms: Target delay for slow stream (default: 2400).
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = VoxtralTranscriber.DEFAULT_MODEL,
        sample_rate: int = 16000,
        fast_delay_ms: int = 240,
        slow_delay_ms: int = 2400,
    ):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.model = model
        self.sample_rate = sample_rate
        self.fast_delay_ms = fast_delay_ms
        self.slow_delay_ms = slow_delay_ms
        self.audio_format = AudioFormat(encoding="pcm_s16le", sample_rate=sample_rate)
        self.client = Mistral(api_key=self.api_key)
        
        # Callbacks
        self.on_fast_text: Optional[Callable[[str], None]] = None
        self.on_slow_text: Optional[Callable[[str], None]] = None
        self.on_merged_text: Optional[Callable[[str, str], None]] = None
    
    async def transcribe(
        self,
        chunk_duration_ms: int = 10,
    ) -> tuple[str, str]:
        """
        Start dual-delay transcription from microphone.
        
        Args:
            chunk_duration_ms: Audio chunk duration in milliseconds.
            
        Returns:
            Tuple of (fast_text, slow_text).
        """
        fast_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
        slow_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
        
        # Start broadcaster
        broadcaster = asyncio.create_task(
            self._broadcast_microphone(
                sample_rate=self.sample_rate,
                chunk_duration_ms=chunk_duration_ms,
                queues=(fast_queue, slow_queue),
            )
        )
        
        # Start streams
        fast_task = asyncio.create_task(
            self._run_stream(
                delay_ms=self.fast_delay_ms,
                audio_stream=self._queue_audio_iter(fast_queue),
                is_fast=True,
            )
        )
        
        slow_task = asyncio.create_task(
            self._run_stream(
                delay_ms=self.slow_delay_ms,
                audio_stream=self._queue_audio_iter(slow_queue),
                is_fast=False,
            )
        )
        
        try:
            fast_text, slow_text = await asyncio.gather(fast_task, slow_task)
            return fast_text, slow_text
        finally:
            broadcaster.cancel()
            try:
                await broadcaster
            except asyncio.CancelledError:
                pass
    
    async def _run_stream(
        self,
        delay_ms: int,
        audio_stream: AsyncIterator[bytes],
        is_fast: bool,
    ) -> str:
        """Run a single transcription stream."""
        full_text = ""
        
        async for event in self.client.audio.realtime.transcribe_stream(
            audio_stream=audio_stream,
            model=self.model,
            audio_format=self.audio_format,
            target_streaming_delay_ms=delay_ms,
        ):
            if isinstance(event, TranscriptionStreamTextDelta):
                full_text += event.text
                if is_fast and self.on_fast_text:
                    self.on_fast_text(event.text)
                elif not is_fast and self.on_slow_text:
                    self.on_slow_text(event.text)
                    
            elif isinstance(event, TranscriptionStreamDone):
                break
                
            elif isinstance(event, RealtimeTranscriptionError):
                raise RuntimeError(f"Transcription error: {event.error}")
        
        return full_text
    
    async def _broadcast_microphone(
        self,
        *,
        sample_rate: int,
        chunk_duration_ms: int,
        queues: tuple[asyncio.Queue[bytes | None], asyncio.Queue[bytes | None]],
    ) -> None:
        """Read from microphone and broadcast to multiple queues."""
        try:
            async for chunk in iter_microphone(
                sample_rate=sample_rate,
                chunk_duration_ms=chunk_duration_ms,
            ):
                for queue in queues:
                    await queue.put(chunk)
        finally:
            for queue in queues:
                await queue.put(None)
    
    async def _queue_audio_iter(
        self,
        queue: asyncio.Queue[bytes | None],
    ) -> AsyncIterator[bytes]:
        """Yield audio chunks from a queue until None is received."""
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

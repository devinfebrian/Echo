"""Configuration settings for Live Captioning."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AutoClearConfig:
    """Configuration for auto-clear behavior."""
    enabled: bool = True
    clear_after_seconds: float = 1.0
    fade_out_duration_ms: int = 500
    min_display_seconds: float = 2.0
    smart_sentence_delay: bool = True  # Wait longer after sentences end
    sentence_extra_delay: float = 2.0  # Extra seconds after punctuation


@dataclass
class TranscriptionConfig:
    """Configuration for transcription settings."""
    api_key: Optional[str] = None
    model: str = "voxtral-mini-transcribe-realtime-2602"
    sample_rate: int = 16000
    chunk_duration_ms: int = 480
    target_delay_ms: Optional[int] = None


@dataclass
class ServerConfig:
    """Configuration for caption server."""
    host: str = "0.0.0.0"
    port: int = 8080
    auto_clear: AutoClearConfig = field(default_factory=AutoClearConfig)


@dataclass
class CaptionStyle:
    """Visual styling for captions (for URL generation)."""
    font_family: str = "'Segoe UI', system-ui, sans-serif"
    font_size: str = "28px"
    font_weight: str = "600"
    text_color: str = "#ffffff"
    bg_color: str = "rgba(0, 0, 0, 0.7)"
    stroke_color: str = "#000000"
    glow_color: str = "rgba(0, 0, 0, 0.5)"
    glow_size: str = "4px"
    padding: str = "12px 24px"
    border_radius: str = "8px"
    line_height: str = "1.4"
    position: str = "bottom"
    max_lines: int = 3

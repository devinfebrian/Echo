"""
Live Captioning for Streamers - Main Entry Point
Using Voxtral Mini Transcribe Realtime

Usage:
    uv run main.py [--delay-ms DELAY] [--host HOST] [--port PORT]
                   [--auto-clear/--no-auto-clear] [--clear-after SECONDS]
                   [--fade-out MS]
    
Environment Variables:
    MISTRAL_API_KEY: Your Mistral API key (required)
"""

import argparse
import asyncio
import os
import sys

from src.transcriber import VoxtralTranscriber
from src.server.caption_server import CaptionServer
from src.config import AutoClearConfig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live Captioning Server for Streamers"
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=None,
        help="Target streaming delay in milliseconds for improved accuracy",
    )
    parser.add_argument(
        "--chunk-duration",
        type=int,
        default=480,
        help="Audio chunk duration in milliseconds (default: 480)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Server port (default: 8080)",
    )
    parser.add_argument(
        "--server-only",
        action="store_true",
        help="Run only the caption server (no transcription)",
    )
    # Auto-clear options
    auto_clear_group = parser.add_argument_group("Auto-clear options")
    auto_clear_group.add_argument(
        "--auto-clear",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable/disable auto-clear (default: enabled)",
    )
    auto_clear_group.add_argument(
        "--clear-after",
        type=float,
        default=2.0,
        help="Seconds to wait before clearing captions (default: 2.0)",
    )
    auto_clear_group.add_argument(
        "--fade-out",
        type=int,
        default=500,
        help="Fade out duration in milliseconds (default: 500, 0 for instant)",
    )
    auto_clear_group.add_argument(
        "--min-display",
        type=float,
        default=2.0,
        help="Minimum display time in seconds (default: 2.0)",
    )

    return parser.parse_args()


def create_auto_clear_config(args: argparse.Namespace) -> AutoClearConfig:
    """Create auto-clear config from CLI arguments."""
    return AutoClearConfig(
        enabled=args.auto_clear,
        clear_after_seconds=args.clear_after,
        fade_out_duration_ms=args.fade_out,
        min_display_seconds=args.min_display,

    )


async def run_with_transcription(args: argparse.Namespace):
    """Run both caption server and transcription."""
    # Check for API key
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("Error: MISTRAL_API_KEY environment variable is not set.")
        print("\nTo set it:")
        print("  Windows PowerShell: $env:MISTRAL_API_KEY='your-api-key'")
        print("  Windows CMD:        set MISTRAL_API_KEY=your-api-key")
        print("  Linux/Mac:          export MISTRAL_API_KEY='your-api-key'")
        sys.exit(1)
    
    print("=" * 60)
    print("Live Captioning Server")
    print("=" * 60)
    
    # Create auto-clear config
    auto_clear_config = create_auto_clear_config(args)
    
    # Start caption server
    server = CaptionServer(
        host=args.host,
        port=args.port,
        auto_clear_config=auto_clear_config,
    )
    await server.start()
    
    print("\nOBS Browser Source Settings:")
    print(f"   URL: http://localhost:{args.port}")
    print(f"   Width: 1920 (or your canvas width)")
    print(f"   Height: 1080 (or your canvas height)")
    print(f"\n   Customization: http://localhost:{args.port}/config")
    print("-" * 60)
    print("Auto-clear settings:")
    print(f"   Enabled: {auto_clear_config.enabled}")
    print(f"   Clear after: {auto_clear_config.clear_after_seconds}s")
    print(f"   Fade out: {auto_clear_config.fade_out_duration_ms}ms")

    print("-" * 60)
    
    # Create transcriber
    transcriber = VoxtralTranscriber(
        api_key=api_key,
        target_delay_ms=args.delay_ms,
    )
    
    # Connect transcriber to server
    server.connect_transcriber(transcriber)
    
    # Start transcription
    print("Starting transcription...")
    print("   Speak into your microphone. Captions will appear in OBS.")
    print("   Captions will auto-clear after silence.")
    print("   Press Ctrl+C to stop.\n")
    
    transcription_task = asyncio.create_task(
        transcriber.transcribe_microphone(chunk_duration_ms=args.chunk_duration)
    )
    
    try:
        # Wait for transcription to complete (or user interrupt)
        full_text = await transcription_task
        print("\nTranscription complete.")
        
    except asyncio.CancelledError:
        print("\nStopped.")
    except KeyboardInterrupt:
        print("\nStopped by user.")
        transcription_task.cancel()
        try:
            await transcription_task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await server.stop()


async def run_server_only(args: argparse.Namespace):
    """Run only the caption server (for testing/external transcription)."""
    print("=" * 60)
    print("Live Captioning Server (Server Only Mode)")
    print("=" * 60)
    
    auto_clear_config = create_auto_clear_config(args)
    
    server = CaptionServer(
        host=args.host,
        port=args.port,
        auto_clear_config=auto_clear_config,
    )
    await server.start()
    
    print("\nOBS Browser Source Settings:")
    print(f"   URL: http://localhost:{args.port}")
    print(f"   Width: 1920 (or your canvas width)")
    print(f"   Height: 1080 (or your canvas height)")
    print(f"\n   Customization: http://localhost:{args.port}/config")
    print("\nHTTP API Endpoints:")
    print(f"   POST /api/caption?text=Your caption here")
    print(f"   POST /api/clear")
    print(f"   GET  /api/status")
    print(f"   GET  /api/config/auto-clear")
    print(f"   POST /api/config/auto-clear")
    print("-" * 60)
    print("Auto-clear settings:")
    print(f"   Enabled: {auto_clear_config.enabled}")
    print(f"   Clear after: {auto_clear_config.clear_after_seconds}s")
    print("-" * 60)
    print("Press Ctrl+C to stop.\n")
    
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        await server.stop()


async def main():
    args = parse_args()
    
    if args.server_only:
        await run_server_only(args)
    else:
        await run_with_transcription(args)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)

"""
Test script for Voxtral real-time transcription.
Usage: python test_transcription.py [--delay-ms DELAY]
"""

import argparse
import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from transcriber import VoxtralTranscriber


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Voxtral real-time transcription from microphone."
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=None,
        help="Target streaming delay in milliseconds (default: None)",
    )
    parser.add_argument(
        "--chunk-duration",
        type=int,
        default=480,
        help="Audio chunk duration in milliseconds (default: 480)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    # Check for API key
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print("Error: MISTRAL_API_KEY environment variable is not set.")
        print("Please set it with: export MISTRAL_API_KEY='your-api-key'")
        sys.exit(1)
    
    print("=" * 60)
    print("Voxtral Real-time Transcription Test")
    print("=" * 60)
    print(f"Model: voxtral-mini-transcribe-realtime-2602")
    if args.delay_ms:
        print(f"Target delay: {args.delay_ms}ms")
    print(f"Chunk duration: {args.chunk_duration}ms")
    print("-" * 60)
    print("Speak into your microphone. Press Ctrl+C to stop.")
    print("=" * 60)
    print()
    
    # Create transcriber
    transcriber = VoxtralTranscriber(
        api_key=api_key,
        target_delay_ms=args.delay_ms,
    )
    
    # Set up callbacks for real-time display
    def on_session_created():
        print("🎤 Listening... (speak now)")
        print()
    
    def on_text_delta(text: str):
        print(text, end="", flush=True)
    
    def on_transcription_done():
        print("\n\n✅ Transcription complete.")
    
    def on_error(error: str):
        print(f"\n❌ Error: {error}", file=sys.stderr)
    
    transcriber.on_session_created = on_session_created
    transcriber.on_text_delta = on_text_delta
    transcriber.on_transcription_done = on_transcription_done
    transcriber.on_error = on_error
    
    try:
        # Start transcription
        full_text = await transcriber.transcribe_microphone(
            chunk_duration_ms=args.chunk_duration
        )
        
        print("\n" + "=" * 60)
        print("Final Transcription:")
        print("=" * 60)
        print(full_text)
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopped by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

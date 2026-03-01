"""
FastAPI server for browser source caption overlay.
Provides HTTP endpoint for OBS browser source and WebSocket for real-time updates.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from ..config import AutoClearConfig


@dataclass
class CaptionState:
    """Global state for caption broadcasting and auto-clear management."""
    current_text: str = ""
    is_listening: bool = False
    connections: set = field(default_factory=set)
    auto_clear_config: AutoClearConfig = field(default_factory=AutoClearConfig)
    
    def __post_init__(self):
        self._lock = asyncio.Lock()
        self._clear_timer: Optional[asyncio.Task] = None
        self._text_last_updated: float = 0
        self._fade_out_timer: Optional[asyncio.Task] = None
        self._last_sent_text: str = ""  # Track what was last broadcast for delta calculation
    
    async def add_connection(self, websocket: WebSocket):
        async with self._lock:
            self.connections.add(websocket)
    
    async def remove_connection(self, websocket: WebSocket):
        async with self._lock:
            self.connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = set()
        async with self._lock:
            connections = self.connections.copy()
        
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.add(conn)
        
        # Clean up disconnected clients
        if disconnected:
            async with self._lock:
                self.connections -= disconnected
    
    def _calculate_clear_delay(self) -> float:
        """Calculate how long to wait before clearing."""
        return self.auto_clear_config.clear_after_seconds
    
    async def _schedule_clear(self):
        """Schedule the caption clear after timeout."""
        await asyncio.sleep(self._calculate_clear_delay())
        await self._do_clear()
    
    async def _do_clear(self):
        """Execute the clear operation with optional fade-out."""
        # Check minimum display time
        import time
        time_since_update = time.time() - self._text_last_updated
        min_display = self.auto_clear_config.min_display_seconds
        
        if time_since_update < min_display:
            # Wait for minimum display time
            remaining = min_display - time_since_update
            await asyncio.sleep(remaining)
        
        # Start fade-out if configured
        fade_duration = self.auto_clear_config.fade_out_duration_ms
        if fade_duration > 0:
            await self.broadcast({
                "type": "fade_out",
                "duration_ms": fade_duration,
            })
            await asyncio.sleep(fade_duration / 1000)
        
        # Clear the caption
        self.current_text = ""
        await self.broadcast({"type": "clear"})
    
    def _cancel_timers(self):
        """Cancel any pending clear or fade timers."""
        if self._clear_timer and not self._clear_timer.done():
            self._clear_timer.cancel()
        if self._fade_out_timer and not self._fade_out_timer.done():
            self._fade_out_timer.cancel()
    
    async def update_caption(self, text: str, is_final: bool = False):
        """Update current caption and broadcast delta to all clients."""
        import time
        
        # Cancel any pending clear timer
        self._cancel_timers()
        
        # Calculate delta (only the new text)
        delta = ""
        is_delta = False
        if text.startswith(self._last_sent_text):
            # New text extends previous text - send only the delta
            delta = text[len(self._last_sent_text):]
            is_delta = len(delta) > 0
        else:
            # Text changed unexpectedly (backspace, correction, etc.) - send full text
            delta = text
            is_delta = False
        
        # Update state
        self.current_text = text
        self._text_last_updated = time.time()
        self._last_sent_text = text
        
        # Broadcast delta to clients
        await self.broadcast({
            "type": "caption",
            "text": delta,
            "is_delta": is_delta,
            "is_final": is_final,
            "cancel_fade": True,
        })
        
        # Schedule auto-clear if enabled
        if self.auto_clear_config.enabled:
            self._clear_timer = asyncio.create_task(self._schedule_clear())
    
    async def clear_now(self):
        """Immediately clear the caption."""
        self._cancel_timers()
        self.current_text = ""
        self._last_sent_text = ""  # Reset delta tracking
        await self.broadcast({"type": "clear"})
    
    async def set_listening(self, is_listening: bool):
        """Update listening status and broadcast."""
        self.is_listening = is_listening
        await self.broadcast({
            "type": "status",
            "is_listening": is_listening,
        })
        
        # When stopping, trigger final clear countdown
        if not is_listening and self.auto_clear_config.enabled:
            self._cancel_timers()
            self._clear_timer = asyncio.create_task(self._schedule_clear())


# Global state instance
caption_state = CaptionState()

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    print("🚀 Caption server starting...")
    yield
    print("🛑 Caption server shutting down...")
    caption_state._cancel_timers()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Live Captioning Server",
        description="Browser source server for real-time captions in OBS",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # Static files for CSS/JS if needed
    static_dir = TEMPLATES_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def get_overlay(request: Request):
        """Main caption overlay page for OBS browser source."""
        return templates.TemplateResponse("overlay.html", {"request": request})
    
    @app.get("/config", response_class=HTMLResponse)
    async def get_config_page(request: Request):
        """Configuration page for styling the captions."""
        return templates.TemplateResponse("config.html", {"request": request})
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time caption updates."""
        await websocket.accept()
        await caption_state.add_connection(websocket)
        
        # Send current state to new client (full text, not delta)
        await websocket.send_json({
            "type": "caption",
            "text": caption_state.current_text,
            "is_delta": False,
            "is_final": True,
        })
        await websocket.send_json({
            "type": "status",
            "is_listening": caption_state.is_listening,
        })
        
        try:
            while True:
                # Keep connection alive and handle any client messages
                data = await websocket.receive_text()
                # Clients can send commands like "clear" or "ping"
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
                elif data == "clear":
                    await caption_state.clear_now()
        except WebSocketDisconnect:
            await caption_state.remove_connection(websocket)
        except Exception:
            await caption_state.remove_connection(websocket)
    
    @app.post("/api/caption")
    async def post_caption(text: str, is_final: bool = False):
        """HTTP endpoint to update caption (for testing/external integration)."""
        await caption_state.update_caption(text, is_final)
        return {"status": "ok", "text": text}
    
    @app.post("/api/clear")
    async def clear_caption():
        """Clear the current caption."""
        await caption_state.clear_now()
        return {"status": "ok"}
    
    @app.get("/api/status")
    async def get_status():
        """Get current caption status."""
        return {
            "is_listening": caption_state.is_listening,
            "current_text": caption_state.current_text,
            "connected_clients": len(caption_state.connections),
            "auto_clear": {
                "enabled": caption_state.auto_clear_config.enabled,
                "clear_after_seconds": caption_state.auto_clear_config.clear_after_seconds,
            },
        }
    
    @app.get("/api/config/auto-clear")
    async def get_auto_clear_config():
        """Get auto-clear configuration."""
        config = caption_state.auto_clear_config
        return {
            "enabled": config.enabled,
            "clear_after_seconds": config.clear_after_seconds,
            "fade_out_duration_ms": config.fade_out_duration_ms,
            "min_display_seconds": config.min_display_seconds,
        }
    
    @app.post("/api/config/auto-clear")
    async def update_auto_clear_config(
        enabled: Optional[bool] = None,
        clear_after_seconds: Optional[float] = None,
        fade_out_duration_ms: Optional[int] = None,
        min_display_seconds: Optional[float] = None,
    ):
        """Update auto-clear configuration."""
        config = caption_state.auto_clear_config
        
        if enabled is not None:
            config.enabled = enabled
        if clear_after_seconds is not None:
            config.clear_after_seconds = max(1.0, clear_after_seconds)
        if fade_out_duration_ms is not None:
            config.fade_out_duration_ms = max(0, fade_out_duration_ms)
        if min_display_seconds is not None:
            config.min_display_seconds = max(0.5, min_display_seconds)
        
        return {"status": "ok", "config": await get_auto_clear_config()}
    
    return app


class CaptionServer:
    """
    Caption server that manages the FastAPI app and transcriber integration.
    
    Usage:
        server = CaptionServer(host="0.0.0.0", port=8080)
        await server.start()
        
        # Connect transcriber
        server.connect_transcriber(transcriber)
        
        # Run until stopped
        await server.run()
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        auto_clear_config: Optional[AutoClearConfig] = None,
    ):
        self.host = host
        self.port = port
        self.app = create_app()
        self._server_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        # Apply auto-clear config if provided
        if auto_clear_config:
            caption_state.auto_clear_config = auto_clear_config
    
    async def start(self):
        """Start the server."""
        import uvicorn
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(server.serve())
        
        # Wait a moment for server to start
        await asyncio.sleep(0.5)
        print(f"📡 Caption server running at http://{self.host}:{self.port}")
        print(f"   OBS Browser Source URL: http://localhost:{self.port}")
    
    def connect_transcriber(self, transcriber):
        """Connect transcriber callbacks to broadcast captions."""
        original_on_text_delta = transcriber.on_text_delta
        original_on_session_created = transcriber.on_session_created
        original_on_transcription_done = transcriber.on_transcription_done
        
        async def broadcast_text(text: str):
            # Call original callback if exists
            if original_on_text_delta:
                original_on_text_delta(text)
            # Broadcast to browser clients
            new_text = caption_state.current_text + text
            await caption_state.update_caption(new_text, is_final=False)
        
        async def on_session_created():
            if original_on_session_created:
                original_on_session_created()
            await caption_state.set_listening(True)
            await caption_state.clear_now()
        
        async def on_transcription_done():
            if original_on_transcription_done:
                original_on_transcription_done()
            await caption_state.set_listening(False)
        
        # Wrap callbacks to handle both sync and async
        def wrap_callback(async_func):
            def wrapper(*args, **kwargs):
                asyncio.create_task(async_func(*args, **kwargs))
            return wrapper
        
        transcriber.on_text_delta = wrap_callback(broadcast_text)
        transcriber.on_session_created = wrap_callback(on_session_created)
        transcriber.on_transcription_done = wrap_callback(on_transcription_done)
    
    async def run(self):
        """Run until stopped."""
        await self._stop_event.wait()
    
    async def stop(self):
        """Stop the server."""
        self._stop_event.set()
        caption_state._cancel_timers()
        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass


async def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the caption server (standalone mode)."""
    import uvicorn
    
    app = create_app()
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(run_server())

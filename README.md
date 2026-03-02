# 🎙️ Echo

> Real-time AI captions for streamers. Just speak.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/)

## ✨ What is this?

**Echo** turns your speech into real-time captions for OBS/Streamlabs - using state-of-the-art Voxtral Mini Transcribe Realtime from Mistral AI. Your viewers never miss a word, even with audio off. Hard of hearing viewer focused.

### Why Streamers Love It

| Problem | Solution |
|---------|----------|
| 🔇 Viewers watch muted | Captions auto-appear on stream |
| 🌍 International audience | Read along in real-time |
| ♿ Accessibility | ADA-compliant captions |
| 🔇 Noisy environment | Your voice still visible |

## 🚀 Features

- ⚡ **Ultra-low latency** - Words appear as you speak
- 🎨 **Pixel-perfect customization** - Match your brand exactly
- 🌐 **OBS Browser Source** - Drag, drop, done
- 🔄 **Auto-clear** - Captions fade when you stop talking
- 📊 **Delta streaming** - Optimized for minimal bandwidth
- 🎯 **Smart presets** - Twitch, YouTube, Minimal, Retro styles

## 📦 Quick Start

### 1. Install

```bash
# Clone the repo
git clone https://github.com/devinfebrian/Echo.git

# Install dependencies
uv sync
```

### 2. Set API Key

Get your free API key at [console.mistral.ai](https://console.mistral.ai)

```bash
# Windows PowerShell
$env:MISTRAL_API_KEY="your-api-key-here"

# Linux/Mac
export MISTRAL_API_KEY="your-api-key-here"
```

### 3. Launch

```bash
uv run main.py
```

## 🎬 Usage

### 1. Configure Your Style

Open `http://localhost:8080/config` in your browser:

- Pick a preset (Twitch, YouTube, Minimal, Retro)
- Or customize every detail
- Click **Copy URL**

### 2. Add to OBS

1. In OBS, click **+** → **Browser Source**
2. Paste your copied URL
3. Set dimensions: **1920x1080**
4. Done! Captions appear as you speak.

### 3. Go Live

Start talking. Your captions appear automatically.

## 🎨 Customization

### Quick Presets

| Style | Description |
|-------|-------------|
| **Twitch** | Purple glow, bold text, streamer aesthetic |
| **YouTube Live** | Clean, professional, minimal |
| **Minimal** | Low profile, blends into gameplay |
| **Retro** | Terminal green, gaming nostalgia |

### Advanced Options

```bash
# Faster captions (100ms chunks)
uv run main.py --chunk-duration 100

# Longer display time
uv run main.py --clear-after 5

# No fade animation (instant clear)
uv run main.py --fade-out 0
```

## 🏗️ Architecture

```
┌─────────────┐    WebSocket     ┌─────────────┐
│  Mistral AI │ ◄────────────────│   Browser   │
│  Voxtral    │  Real-time Text  │  OBS Source │
└─────────────┘                  └─────────────┘
       │
       │  Delta Streaming
       │  (90% less bandwidth)
       ▼
┌─────────────┐
│   Config    │
│   Studio    │
└─────────────┘
```

### Tech Stack

- **Python 3.13+** - Async backend
- **FastAPI** - WebSocket server
- **Mistral AI** - Voxtral Mini Transcribe Realtime
- **WebSockets** - Low-latency text streaming
- **Vanilla JS** - Zero dependencies frontend

## 💡 Pro Tips

1. **Test first**: Open `http://localhost:8080` to see captions before going live
2. **Position matters**: Bottom-center works best for most games
3. **Font size**: 28-32px is readable at 1080p
4. **Glow effect**: Helps text pop on busy backgrounds
5. **Auto-clear**: 2-3 seconds feels natural for conversations

## 🔧 API Endpoints

```bash
# Get status
curl http://localhost:8080/api/status

# Manually set caption
curl -X POST "http://localhost:8080/api/caption?text=Hello+Chat"

# Clear captions
curl -X POST http://localhost:8080/api/clear
```

## 📊 Performance

| Metric | Value |
|--------|-------|
| Latency | ~200-400ms |
| Bandwidth | ~1-2 KB/s (delta streaming) |
| CPU Usage | <5% (modern CPU) |
| Memory | ~50-100 MB |

## 🤝 Contributing

PRs welcome! Areas to improve:
- [ ] Multi-language support
- [ ] Profanity filter
- [ ] Custom vocabulary
- [ ] Save transcripts to file
- [ ] System tray GUI

## 🙏 Acknowledgments

- [Mistral AI](https://mistral.ai/) for the amazing Voxtral API

---

**Made with 💜 for the streaming community**

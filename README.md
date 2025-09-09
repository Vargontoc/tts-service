# 🎙️ TTS Service (FastAPI + Piper)


Open-source **Text-to-Speech microservice** built with **Python 3.12, FastAPI, and Piper**.  
It provides a lightweight REST API to convert text into audio, designed for easy integration into multi-agent systems or other backends.

---

## ✨ Features
- REST API with `/health`, `/voices`, `/synthesize`
- Supports **WAV/MP3/OGG** output
- **API key** protection + **CORS**
- **Cache** for repeated requests

---

## 🚀 Quickstart

```bash
# Clone repo
git clone https://github.com/Vargontoc/tts-service
cd <tu-repo>

# Start with docker compose (downloads Piper model automatically)
docker compose  up --build
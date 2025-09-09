import io
import math
import struct
import time
from typing import Optional
import uuid
import wave
from fastapi import FastAPI, Security, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from .config import settings


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.API_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
def require_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key")
    return api_key


@app.get("/health")
def health():
    return { "status": "ok" }

@app.get("/voices")
def voices(api_key: str = Security(require_api_key)):
    return {
        "provider": "stub",
        "voices": [
            { "id": "stub-es-ES-1", "lang": "es-ES", "name": "Stub Español"},
            { "id": "stub-en-US-1", "lang": "en-US", "name": "Stub Ingles"}
        ]
    }
    
class SyntheziseRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Texto a sintetizar (stub)")
    voice: Optional[str] = Field(None, description="ID de voz (no usado en stub)")
    format: str = Field("wav", pattern="^(wav)$", description=".wav format")
    sample_rate: int = Field(16000, ge=8000, le=48000)
    duration_sec: float = Field(1.5, ge=0.2, le=10.0, description="Duracion del audio")
    freq_hz: float = Field(440.0, ge=50.0, le=2000.0, description="Frecuencia de la onda")
    
def _generate_sine_wav(sr: int, seconds: float, freq: float) -> bytes:
    n_frames = int(sr * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        amplitude = 0.4
        for i in range(n_frames):
            t = i / sr
            sample = int(amplitude * 32767 * math.sin(2 * math.pi * freq * t))
            wf.writeframes(struct.pack("<h", sample))
    return buf.getvalue()

@app.post("/synthesize")
def synthesize(req: SyntheziseRequest, api_key: str = Security(require_api_key)):
    if req.format != "wav":
        raise HTTPException(status_code=400, detail="Only WAV supported")
    audio_bytes = _generate_sine_wav(req.sample_rate, req.duration_sec, req.freq_hz)
    filename = f"tts-{int(time.time())}-{uuid.uuid4().hex[:8]}.wav"
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav",headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Stub-Info": f"text:len={len(req.text)};voice={req.voice or 'stub'}"
    })
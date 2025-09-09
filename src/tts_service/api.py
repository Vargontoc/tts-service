import io
import json
import math
from pathlib import Path
import struct
import time
from typing import Any, Dict, Optional
import uuid
import wave
from fastapi import FastAPI, Security, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

from tts_service.engines.piper import PiperEngine
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

_VOICES_PATH = Path(__file__).resolve().parents[1] / "tts_service" / "models" / "voices.json"
with _VOICES_PATH.open("r", encoding="utf-8") as f:
    VOICE_INDEX: Dict[str, Any] = json.load(f)

def _get_voice(voice_id: str) -> Optional[Dict[str, Any]]:
    for v in VOICE_INDEX.get("voices", []):
        if v.get("id") == voice_id:
            return v
    return None

def require_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key")
    return api_key


@app.get("/health")
def health():
    return { "status": "ok" }

@app.get("/voices")
def voices(api_key: str = Security(require_api_key)):
    return VOICE_INDEX
    
class SyntheziseRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: Optional[str] = Field(None, description="ID de voz (de /voices)")
    format: str = Field("wav", pattern="^(wav)$", description=".wav format")
    sample_rate: Optional[int] = Field(None, ge=8000, le=48000)
    length_scale: Optional[float] = Field(None, ge=0.5, le=2.0)
    noise_scale: Optional[float] = Field(None, ge=0.0, le=1.0)
    noise_w: Optional[float] = Field(None, ge=0.0, le=1.0)
    speaker: Optional[int] = Field(None, ge=0)
    


@app.post("/synthesize")
def synthesize(req: SyntheziseRequest, api_key: str = Security(require_api_key)):
    if req.format != "wav":
        raise HTTPException(status_code=400, detail="Only WAV supported")
    
    voice = _get_voice(req.voice)
    if not voice:
        raise HTTPException(status_code=404, detail=f"Voice not found: {req.voice}")
    
    engine = PiperEngine(model_path=voice["model"], config_path=voice.get("config"))
    sr = req.sample_rate or voice.get("sample_rate")
   
    try:
        audio_byes = engine.synthesize_wav(
            text=req.text,
            sample_rate=sr,
            length_scale=req.length_scale,
            noise_scale=req.noise_scale,
            noise_w=req.noise_w,
            speaker=req.speaker
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    filename = f'{req.voice}.wav'
    return StreamingResponse(io.BytesIO(audio_byes), media_type="audio/wav", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })
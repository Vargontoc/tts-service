import io
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, Security, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field
from pydub import AudioSegment

from tts_service.engines.piper import PiperEngine  # ensure registration
from tts_service.engines.coqui import CoquiEngine  # ensure registration
from tts_service.engines.base import get_engine
from tts_service.utils import cache
from tts_service.utils.prosody import apply_prosody
from tts_service.utils.text_norm import normalize_numbers_es
from tts_service.utils.emotions import resolve_emotion
from tts_service.utils.logging import get_logger, log_api_request, log_error_with_context
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

_VOICES_JSON = settings.get_voices_config_path()
_UNIFIED_JSON = settings.get_unified_config_path()

# Logger para API
logger = get_logger("tts_service.api")

def _load_config() -> Dict[str, Any]:
    unified: Dict[str, Any] = {}
    if _UNIFIED_JSON.exists():
        with _UNIFIED_JSON.open("r", encoding="utf-8") as f:
            unified = json.load(f)
    voices: list[Dict[str, Any]] = []
    if unified.get("voices"):
        voices.extend(unified["voices"])
    elif _VOICES_JSON.exists():  # legacy fallback
        with _VOICES_JSON.open("r", encoding="utf-8") as f:
            legacy = json.load(f)
            voices.extend(legacy.get("voices", []))
    # extra coqui models
    coqui_cfg = unified.get("coqui", {})
    for m in coqui_cfg.get("extra_models", []) or []:
        if not any(v.get("model") == m for v in voices):
            vid = m.replace("/", "-")
            voices.append({
                "id": f"coqui-{vid}",
                "provider": "coqui",
                "lang": "es-ES",
                "name": f"Coqui dynamic {m}",
                "model": m,
                "sample_rate": unified.get("defaults", {}).get("sample_rate", 22050)
            })
    return {
        "voices": voices,
        "emotions": unified.get("emotions", {}),
        "defaults": unified.get("defaults", {}),
        "coqui": coqui_cfg,
        "prosody_presets": unified.get("prosody_presets", {})
    }

CONFIG = _load_config()
VOICE_INDEX: Dict[str, Any] = {"voices": CONFIG["voices"]}
EMOTIONS_INDEX: Dict[str, Any] = CONFIG.get("emotions", {})
DEFAULTS_CFG: Dict[str, Any] = CONFIG.get("defaults", {})

def _get_voice(voice_id: str) -> Optional[Dict[str, Any]]:
    for v in VOICE_INDEX.get("voices", []):
        if v.get("id") == voice_id:
            return v
    return None

def _find_fallback_voice(lang: str) -> Optional[Dict[str, Any]]:
    for v in VOICE_INDEX.get("voices", []):
        if v.get("provider") == "piper" and v.get("lang") == lang:
            return v
    return None

def require_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API Key")
    return api_key


@app.get("/health")
def health():
    logger.debug("Health check requested")
    return { "status": "ok" }

@app.get("/voices")
def voices(api_key: str = Security(require_api_key)):
    request_id = str(uuid.uuid4())[:8]
    log_api_request(logger, "/voices", request_id)

    logger.info(f"Returning {len(VOICE_INDEX.get('voices', []))} available voices",
                extra={"request_id": request_id})
    return VOICE_INDEX
    
class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: Optional[str] = Field(None, description="ID de voz (de /voices)")
    format: str = Field("wav", description=".wav / mp3 / ogg format")
    sample_rate: Optional[int] = Field(None, ge=8000, le=48000)
    length_scale: Optional[float] = Field(None, ge=0.5, le=2.0)
    noise_scale: Optional[float] = Field(None, ge=0.0, le=1.0)
    noise_w: Optional[float] = Field(None, ge=0.0, le=1.0)
    speaker: Optional[int] = Field(None, ge=0)
    speaking_rate: Optional[float] = Field(None, ge=0.5, le=2.0, description="Factor velocidad post-proceso")
    pitch_shift: Optional[float] = Field(None, ge=-12, le=12, description="Semitonos")
    energy: Optional[float] = Field(None, ge=0.5, le=2.0, description="Ganancia multiplicativa")
    emotion: Optional[str] = Field(
        None,
        description="Emoción: neutral|happy|sad|angry|calm o personalizada en EMOTION_PRESETS"
    )
    


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest, api_key: str = Security(require_api_key)):
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]

    log_api_request(
        logger, "/synthesize", request_id,
        voice_id=req.voice, text_length=len(req.text), format=req.format
    )

    voice = _get_voice(req.voice)
    if not voice:
        log_error_with_context(
            logger, ValueError(f"Voice not found: {req.voice}"),
            {"request_id": request_id, "voice_id": req.voice}
        )
        raise HTTPException(status_code=404, detail=f"Voice not found: {req.voice}")
    if settings.TTS_NORMALIZE_NUMBERS:
        try:
            req.text = normalize_numbers_es(req.text)
        except Exception:
            pass
    
    fmt = req.format.lower()
    if fmt not in ["wav", "mp3", "ogg"]:
        raise HTTPException(status_code=400, detail="Format must be wav, mp3 or ogg")
    
    sr_default = DEFAULTS_CFG.get("sample_rate", 22050)
    sr = req.sample_rate or voice.get("sample_rate", sr_default)
    provider = voice.get("provider", "piper")
    model = voice.get("model")
    config_path = voice.get("config")
    # Emotion presets (unified config)
    if req.emotion:
        preset = None
        val = EMOTIONS_INDEX.get(req.emotion)
        if isinstance(val, (list, tuple)) and len(val) == 3:
            preset = (float(val[0]), float(val[1]), float(val[2]))
        else:
            preset = resolve_emotion(req.emotion, {})
        if preset:
            rate_p, pitch_p, energy_p = preset
            if req.speaking_rate is None:
                req.speaking_rate = rate_p
            if req.pitch_shift is None:
                req.pitch_shift = pitch_p
            if req.energy is None:
                req.energy = energy_p
    key_v3 = cache.make_key_v3(
        req.text, provider, model, req.voice, sr, fmt,
        req.speaking_rate, req.pitch_shift, req.energy
    ) if DEFAULTS_CFG.get("enable_prosody", True) else None
    key_v2 = cache.make_key_v2(req.text, provider, model, req.voice, sr, fmt)

    # Compatibilidad: buscar clave v2, luego legacy
    cache_hit = False
    if key_v3 and cache.exists(key_v3, fmt):
        audio_bytes = cache.load(key_v3, fmt)
        cache_hit = True
        logger.info("Cache hit (v3)", extra={"request_id": request_id, "cache_key": "v3"})
    elif cache.exists(key_v2, fmt):
        audio_bytes = cache.load(key_v2, fmt)
        cache_hit = True
        logger.info("Cache hit (v2)", extra={"request_id": request_id, "cache_key": "v2"})
    else:
        legacy_key = cache.make_key(req.text, req.voice, sr, fmt)
        if cache.exists(legacy_key, fmt):
            audio_bytes = cache.load(legacy_key, fmt)
            cache_hit = True
            logger.info("Cache hit (legacy)", extra={"request_id": request_id, "cache_key": "legacy"})
        else:
            # Selección engine
            def _run(provider_sel: str, voice_obj: Dict[str, Any]):
                eng_kwargs = {}
                if provider_sel == "piper":
                    eng_kwargs = {"config_path": voice_obj.get("config")}
                elif provider_sel == "coqui":
                    # GPU policy
                    use_gpu = None
                    if settings.COQUI_USE_GPU.lower() in ("true", "false"):
                        use_gpu = settings.COQUI_USE_GPU.lower() == "true"
                    eng_kwargs = {"use_gpu": use_gpu}
                engine = get_engine(provider_sel, voice_obj.get("model"), **eng_kwargs)
                return engine.synthesize_wav(
                    text=req.text,
                    sample_rate=sr,
                    length_scale=req.length_scale if provider_sel == "piper" else None,
                    noise_scale=req.noise_scale if provider_sel == "piper" else None,
                    noise_w=req.noise_w if provider_sel == "piper" else None,
                    speaker=req.speaker
                )

            logger.info(f"Starting synthesis with {provider} engine",
                       extra={"request_id": request_id, "provider": provider, "voice_id": req.voice})

            try:
                wav_bytes = _run(provider, voice)
            except Exception as e:
                log_error_with_context(
                    logger, e,
                    {"request_id": request_id, "provider": provider, "voice_id": req.voice, "operation": "synthesis"}
                )
                if provider != "piper" and settings.ENABLE_FALLBACK:
                    logger.warning(f"Attempting fallback to Piper after {provider} failure",
                                 extra={"request_id": request_id, "original_provider": provider})
                    fb = _find_fallback_voice(voice.get("lang", ""))
                    if not fb:
                        log_error_with_context(
                            logger, ValueError("No fallback voice available"),
                            {"request_id": request_id, "lang": voice.get("lang", "")}
                        )
                        raise HTTPException(status_code=500, detail=f"Engine {provider} fallo y no hay fallback disponible: {e}")
                    try:
                        wav_bytes = _run("piper", fb)
                        logger.info("Fallback synthesis successful",
                                  extra={"request_id": request_id, "fallback_voice": fb.get("id")})
                    except Exception as e2:
                        log_error_with_context(
                            logger, e2,
                            {"request_id": request_id, "provider": "piper", "operation": "fallback_synthesis"}
                        )
                        raise HTTPException(status_code=500, detail=f"Fallback Piper fallo: {e2}")
                else:
                    raise HTTPException(status_code=500, detail=f"Engine {provider} error: {e}")

            # Prosodia post-proceso
            if DEFAULTS_CFG.get("enable_prosody", True):
                wav_bytes = apply_prosody(
                    wav_bytes,
                    req.speaking_rate,
                    req.pitch_shift,
                    req.energy
                )
            if fmt == "wav":
                audio_bytes = wav_bytes
            else:
                audio = AudioSegment.from_file(io.BytesIO(wav_bytes), format="wav")
                out_buf = io.BytesIO()
                audio.export(out_buf, format=fmt)
                audio_bytes = out_buf.getvalue()
            cache.save(key_v3 if key_v3 else key_v2, fmt, audio_bytes)

    # Log de finalización exitosa
    duration = time.time() - start_time
    logger.info(
        f"Synthesis request completed successfully",
        extra={
            "request_id": request_id,
            "duration": f"{duration:.2f}s",
            "output_size": len(audio_bytes),
            "cache_hit": cache_hit,
            "format": fmt
        }
    )

    filename = f'{req.voice}.{fmt}'
    return StreamingResponse(io.BytesIO(audio_bytes), media_type=f"audio/{'wav' if fmt == 'wav' else fmt}", headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })
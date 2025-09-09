from fastapi import FastAPI, Security, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
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
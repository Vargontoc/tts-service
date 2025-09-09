import uvicorn
from .config import settings

if __name__ == "__main__":
    uvicorn.run("tts_service.api:app", host=settings.HOST, port=settings.PORT,reload=True)
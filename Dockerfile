FROM python:3.12-slim AS build
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt* ./
RUN pip install --upgrade pip && \
    if [ -f requirements.txt ]; then pip install -r requirements.txt; fi


FROM python:3.12-slim AS runtime

RUN useradd -ms /bin/bash appuser
USER appuser

WORKDIR /app

COPY --from=build /usr/local /usr/local

COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser models ./models
COPY --chown=appuser:appuser .env.example ./

RUN mkdir -p cache

ENV PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000

CMD ["python", "-m", "tts_service"]

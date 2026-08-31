FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        git \
        libsndfile1 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements.txt

COPY backend /app/backend
COPY configs /app/configs

RUN mkdir -p \
    /app/generated \
    /app/database \
    /app/models \
    /app/secrets

EXPOSE 8000

CMD [
    "python",
    "-m",
    "uvicorn",
    "backend.app:app",
    "--host",
    "0.0.0.0",
    "--port",
    "8000"
]

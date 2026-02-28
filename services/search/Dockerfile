FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/model_cache \
    TRANSFORMERS_CACHE=/app/model_cache

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser \
    && mkdir -p /app/model_cache && chown -R appuser:appuser /app/model_cache

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

USER appuser
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
    print('Downloading Bi-Encoder...'); \
    SentenceTransformer('paraphrase-multilingual-mpnet-base-v2', cache_folder='/app/model_cache'); \
    print('Downloading Cross-Encoder...'); \
    CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2');"
        
COPY --chown=appuser:appuser . .
        
EXPOSE 8000
        
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

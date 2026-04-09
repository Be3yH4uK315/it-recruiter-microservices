FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/opt/model-cache/huggingface \
    TRANSFORMERS_CACHE=/opt/model-cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/opt/model-cache/sentence_transformers \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser \
    && useradd -r -g appuser -d /app -s /usr/sbin/nologin appuser \
    && mkdir -p /app /opt/model-cache/huggingface /opt/model-cache/sentence_transformers \
    && chown -R appuser:appuser /app /opt/model-cache

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

USER appuser
    
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', cache_folder='/opt/model-cache/sentence_transformers'); \
CrossEncoder('cross-encoder/mmarco-mMiniLMv2-L12-H384-v1', cache_folder='/opt/model-cache/sentence_transformers')"
    
EXPOSE 8000
    
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

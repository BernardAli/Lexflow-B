FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LEXFLOW_DATA_DIR=/data LEXFLOW_SEED_DEMO=1
WORKDIR /opt/lexflow
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-deu tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN addgroup --system lexflow && adduser --system --ingroup lexflow lexflow \
    && mkdir -p /data && chown -R lexflow:lexflow /data /opt/lexflow
USER lexflow
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4)" || exit 1
CMD ["python","-m","uvicorn","lexflow.main:app","--host","0.0.0.0","--port","8000"]

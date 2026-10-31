FROM python:3.12.8-slim

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY src ./src

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "mkdir -p /tunnel && chown 65532:65532 /tunnel && python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]

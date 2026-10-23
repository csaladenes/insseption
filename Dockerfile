FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/api

COPY pyproject.toml README.md LICENSE ./
COPY api ./api
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[server]"

EXPOSE 8787
CMD ["uvicorn", "insseption.main:app", "--host", "0.0.0.0", "--port", "8787"]

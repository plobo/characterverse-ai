# API + procedural render worker image (CPU only).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CV_SHARED_DIR=/srv/shared
RUN useradd --create-home --uid 10001 app
WORKDIR /srv/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY shared /srv/shared
COPY backend /srv/backend
USER app
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:app_factory", "--host", "0.0.0.0", "--port", "8000"]

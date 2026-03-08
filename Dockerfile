# ── Frontend build ────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build


# ── Frontend serve ────────────────────────────────────────────────────────────
FROM nginx:alpine AS frontend

COPY --from=frontend-build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]


# ── Backend base ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS backend

RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps chromium

COPY backend/ .
RUN mkdir -p data logs

EXPOSE 8000
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]


# ── Job matcher ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS job_matcher

WORKDIR /app
COPY job_matcher/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY job_matcher/ .
RUN mkdir -p resume output chroma_db

# Default: run the matcher pipeline.
# Override: docker compose run --rm job_matcher python chroma_store.py
CMD ["python", "main.py"]

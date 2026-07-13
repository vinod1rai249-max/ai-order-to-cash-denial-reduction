# ---------- Stage 1: Build Frontend ----------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json .oxlintrc.json ./
COPY src/ ./src/
COPY public/ ./public/

ARG VITE_API_URL=/api
ARG VITE_FIREBASE_PROJECT_ID=adpo-healthcare-agent
ARG VITE_FIREBASE_AUTH_DOMAIN=adpo-healthcare-agent.firebaseapp.com
ARG VITE_FIREBASE_API_KEY=placeholder
ARG VITE_USE_MOCK_AUTH=true

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID
ENV VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY
ENV VITE_USE_MOCK_AUTH=$VITE_USE_MOCK_AUTH

RUN npm run build

# ---------- Stage 2: Python Backend + Nginx ----------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY main.py ./
COPY agents/ ./agents/
COPY auth/ ./auth/
COPY data/ ./data/
COPY gateway/ ./gateway/
COPY governance/ ./governance/
COPY ml/ ./ml/
COPY orchestrator/ ./orchestrator/
COPY schema/ ./schema/
COPY tests/ ./tests/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist /app/static

# Nginx config: serve frontend + reverse proxy /api to uvicorn
COPY nginx_default.conf /etc/nginx/sites-available/default

# Supervisor config: run nginx + uvicorn together
COPY supervisord_app.conf /etc/supervisor/conf.d/app.conf

EXPOSE 8080

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

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
RUN cat > /etc/nginx/sites-available/default <<'NGINX' \
server { \
    listen 8080; \
    server_name _; \
 \
    root /app/static; \
    index index.html; \
 \
    # Frontend SPA — serve index.html for all non-file routes \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
 \
    # Reverse proxy API calls to uvicorn backend \
    location /api/ { \
        proxy_pass http://127.0.0.1:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_read_timeout 120s; \
    } \
 \
    # Health check passthrough \
    location = /health { \
        proxy_pass http://127.0.0.1:8000/; \
    } \
} \
NGINX

# Supervisor config: run nginx + uvicorn together
RUN cat > /etc/supervisor/conf.d/app.conf <<'SUPERVISOR' \
[supervisord] \
nodaemon=true \
logfile=/dev/stdout \
logfile_maxbytes=0 \
 \
[program:uvicorn] \
command=uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2 \
directory=/app \
autostart=true \
autorestart=true \
stdout_logfile=/dev/stdout \
stdout_logfile_maxbytes=0 \
stderr_logfile=/dev/stderr \
stderr_logfile_maxbytes=0 \
 \
[program:nginx] \
command=nginx -g "daemon off;" \
autostart=true \
autorestart=true \
stdout_logfile=/dev/stdout \
stdout_logfile_maxbytes=0 \
stderr_logfile=/dev/stderr \
stderr_logfile_maxbytes=0 \
SUPERVISOR

EXPOSE 8080

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]

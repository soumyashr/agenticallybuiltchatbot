# 09 — DOCKER.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build all Docker config files. Test local container run end-to-end.
# Prerequisites: 08_FRONTEND.md must be COMPLETE and VERIFIED.

---

## STEP 1 — Create docker/ directory

```bash
mkdir -p /Users/soumya.shrivastava/AgenticallyBuiltChatBot/docker
```

---

## STEP 2 — docker/Dockerfile.backend

Write to `docker/Dockerfile.backend`:
```dockerfile
# ── Stage 1: Builder ──────────────────────────────────────────
FROM --platform=linux/arm64 python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY backend/app ./app

RUN mkdir -p data vector_store

RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## STEP 3 — docker/Dockerfile.frontend

Write to `docker/Dockerfile.frontend`:
```dockerfile
# ── Stage 1: Build ────────────────────────────────────────────
FROM --platform=linux/arm64 node:20-alpine AS builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ .
RUN npm run build

# ── Stage 2: Serve ────────────────────────────────────────────
FROM --platform=linux/arm64 nginx:alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

---

## STEP 4 — docker/nginx.conf

Write to `docker/nginx.conf`:
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # API proxy → backend
    location /auth/ {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }

    location /chat {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_read_timeout 120s;
    }

    location /admin/ {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_read_timeout 120s;
    }

    location /documents/ {
        proxy_pass         http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_read_timeout 120s;
    }

    location /health {
        proxy_pass http://backend:8000;
    }

    # React Router — serve index.html for all frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|ico|svg|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
}
```

---

## STEP 5 — docker/docker-compose.yml

Write to `docker/docker-compose.yml`:
```yaml
version: "3.9"

services:

  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    container_name: hm_backend
    restart: unless-stopped
    env_file: ../.env
    environment:
      - DATA_DIR=/app/data
      - VECTOR_STORE_DIR=/app/vector_store
    volumes:
      - pdf_data:/app/data
      - vector_index:/app/vector_store
      - sqlite_data:/app
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 25s
    networks:
      - hm_net

  frontend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.frontend
    container_name: hm_frontend
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - hm_net

volumes:
  pdf_data:    { name: hm_pdf_data    }
  vector_index:{ name: hm_vector_index }
  sqlite_data: { name: hm_sqlite_data  }

networks:
  hm_net:
    name: hm_network
    driver: bridge
```

---

## STEP 6 — docker/.dockerignore

Write to `docker/.dockerignore`:
```
__pycache__/
*.pyc
*.pyo
.venv/
venv/
backend/.venv/
node_modules/
frontend/node_modules/
frontend/dist/
backend/data/
backend/vector_store/
backend/users.db
backend/documents.db
*.db
.env
.git/
.gitignore
*.md
docs/
.DS_Store
*.log
.pytest_cache/
.idea/
.vscode/
```

---

## STEP 7 — docker/.env.example

Write to `docker/.env.example`:
```
AI_PROVIDER=azure_openai
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.1
EMBEDDING_MODEL=text-embedding-ada-002
OPENAI_API_KEY=sk-your-key-here
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
AZURE_SEARCH_ENDPOINT=
AZURE_SEARCH_ADMIN_KEY=
AZURE_SEARCH_INDEX=
JWT_SECRET=change-this-to-a-long-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8
AGENT_MAX_ITERATIONS=5
DYNAMO_TABLE=hm-documents
DYNAMO_REGION=ap-south-1
DATA_DIR=data
VECTOR_STORE_DIR=vector_store
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
RETRIEVER_TOP_K=5
MAX_HISTORY_TURNS=10
```

---

## STEP 8 — docker/deploy.sh

Write to `docker/deploy.sh`:
```bash
#!/bin/bash
# ────────────────────────────────────────────────────
# Happiest Minds Knowledge Hub — Deploy Script
# Usage:
#   ./docker/deploy.sh local          → build + run containers
#   ./docker/deploy.sh stop           → stop all containers
#   ./docker/deploy.sh logs           → tail live logs
#   ./docker/deploy.sh status         → show container health
#   ./docker/deploy.sh rebuild        → force rebuild all images
# ────────────────────────────────────────────────────
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
log()     { echo -e "${CYAN}[HM]${NC} $1"; }
ok()      { echo -e "${GREEN}[✅]${NC} $1"; }
warn()    { echo -e "${YELLOW}[⚠️]${NC} $1"; }
fail()    { echo -e "${RED}[❌]${NC} $1"; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="docker compose -f $ROOT/docker/docker-compose.yml"

pre_flight() {
  command -v docker >/dev/null 2>&1 || fail "Docker not installed."
  docker compose version >/dev/null 2>&1 || fail "Docker Compose not available."
  [ -f "$ROOT/.env" ] || fail ".env not found. Run: cp docker/.env.example .env — then add your OPENAI_API_KEY."
  source "$ROOT/.env"
  [ -n "$OPENAI_API_KEY" ] || fail "OPENAI_API_KEY is empty in .env"
  ok "Pre-flight checks passed."
}

local_deploy() {
  pre_flight
  log "Building images (this takes ~2 min on first run)..."
  $COMPOSE build

  log "Starting containers..."
  $COMPOSE up -d

  log "Waiting for backend to become healthy..."
  for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
      ok "Backend is healthy."
      break
    fi
    [ "$i" -eq 20 ] && fail "Backend failed to start. Run: ./docker/deploy.sh logs"
    sleep 3
    log "Waiting… ($i/20)"
  done

  echo ""
  echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
  echo -e "${BOLD}${GREEN}  Happiest Minds Knowledge Hub is LIVE! 🎓  ${NC}"
  echo -e "${BOLD}${GREEN}══════════════════════════════════════${NC}"
  echo ""
  echo -e "  ${CYAN}App:${NC}     http://localhost"
  echo -e "  ${CYAN}API:${NC}     http://localhost:8000"
  echo -e "  ${CYAN}Swagger:${NC} http://localhost:8000/docs"
  echo ""
  echo -e "  ${YELLOW}Login credentials:${NC}"
  echo -e "    admin    / HMAdmin@2024"
  echo -e "    faculty1 / HMFaculty@2024"
  echo -e "    student1 / HMStudent@2024"
  echo ""
}

case "${1:-local}" in
  local)   local_deploy ;;
  stop)    log "Stopping..."; $COMPOSE down; ok "Stopped." ;;
  logs)    $COMPOSE logs -f ;;
  status)  $COMPOSE ps && echo "" && curl -sf http://localhost:8000/health && echo " ✅ healthy" || echo " ❌ not responding" ;;
  rebuild) log "Rebuilding..."; $COMPOSE down; $COMPOSE build --no-cache; $COMPOSE up -d; ok "Rebuilt and running." ;;
  *)       echo "Usage: ./docker/deploy.sh [local|stop|logs|status|rebuild]"; exit 1 ;;
esac
```

Make it executable:
```bash
chmod +x /Users/soumya.shrivastava/AgenticallyBuiltChatBot/docker/deploy.sh
```

---

## STEP 9 — Create root .env

```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot
cp docker/.env.example .env
# Open .env and add your OPENAI_API_KEY
```

---

## STEP 10 — Run it

```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot
./docker/deploy.sh local
```

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 10.

- [ ] `./docker/deploy.sh local` completes without errors
- [ ] `docker ps` shows both `hm_backend` and `hm_frontend` with status `healthy`
- [ ] `curl http://localhost:8000/health` returns `{"status":"ok"}`
- [ ] `http://localhost` loads the Happiest Minds Knowledge Hub login screen in browser
- [ ] Login works from the containerised app (not just localhost:3000)
- [ ] Chat returns an answer from within the container
- [ ] `./docker/deploy.sh logs` streams logs from both containers
- [ ] `./docker/deploy.sh stop` stops both containers cleanly
- [ ] `./docker/deploy.sh rebuild` rebuilds and restarts successfully
- [ ] Docker volumes `hm_pdf_data`, `hm_vector_index`, `hm_sqlite_data` exist (`docker volume ls`)
- [ ] Data persists after `./docker/deploy.sh stop` and `./docker/deploy.sh local`

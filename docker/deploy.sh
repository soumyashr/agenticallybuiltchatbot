#!/bin/bash
# ────────────────────────────────────────────────────
# Happiest Minds Knowledge Hub — Deploy Script
# Usage:
#   ./docker/deploy.sh local          → build + run containers
#   ./docker/deploy.sh stop           → stop all containers
#   ./docker/deploy.sh logs           → tail live logs
#   ./docker/deploy.sh status         → show container health
#   ./docker/deploy.sh rebuild        → force rebuild all images
#   ./docker/deploy.sh aws            → build, push to ECR, deploy on EC2
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

aws_deploy() {
  pre_flight

  # Validate AWS vars
  [ -n "$AWS_ACCOUNT_ID" ] || fail "AWS_ACCOUNT_ID not set in .env"
  [ -n "$AWS_REGION"     ] || fail "AWS_REGION not set in .env"
  [ -n "$EC2_HOST"       ] || fail "EC2_HOST not set in .env"
  [ -n "$EC2_KEY_PATH"   ] || fail "EC2_KEY_PATH not set in .env"
  [ -f "${EC2_KEY_PATH/#\~/$HOME}" ] || fail "SSH key not found at $EC2_KEY_PATH"

  ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  BACKEND_REPO="${ECR_BACKEND_REPO:-hm-knowledge-hub-backend}"
  FRONTEND_REPO="${ECR_FRONTEND_REPO:-hm-knowledge-hub-frontend}"
  VERSION=$(date +%Y%m%d-%H%M%S)
  BACKEND_IMG="${ECR_BASE}/${BACKEND_REPO}:${VERSION}"
  FRONTEND_IMG="${ECR_BASE}/${FRONTEND_REPO}:${VERSION}"

  log "Authenticating with ECR..."
  aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_BASE"
  ok "ECR login successful."

  log "Building backend image..."
  docker build --platform linux/arm64 \
    -f "$ROOT/docker/Dockerfile.backend" \
    -t "$BACKEND_IMG" "$ROOT"
  docker push "$BACKEND_IMG"
  ok "Backend pushed: $BACKEND_IMG"

  log "Building frontend image..."
  docker build --platform linux/arm64 \
    -f "$ROOT/docker/Dockerfile.frontend" \
    -t "$FRONTEND_IMG" "$ROOT"
  docker push "$FRONTEND_IMG"
  ok "Frontend pushed: $FRONTEND_IMG"

  log "Deploying on EC2: $EC2_HOST ..."
  KEY="${EC2_KEY_PATH/#\~/$HOME}"

  # Copy .env to EC2
  scp -i "$KEY" -o StrictHostKeyChecking=no \
    "$ROOT/.env" "ec2-user@${EC2_HOST}:/opt/AgenticallyBuiltChatBot/.env"

  # Copy compose file
  scp -i "$KEY" -o StrictHostKeyChecking=no \
    "$ROOT/docker/docker-compose.yml" "ec2-user@${EC2_HOST}:/opt/AgenticallyBuiltChatBot/docker-compose.yml"

  # Remote deploy
  ssh -i "$KEY" -o StrictHostKeyChecking=no "ec2-user@${EC2_HOST}" << REMOTE
    set -e
    cd /opt/AgenticallyBuiltChatBot

    # Authenticate ECR from EC2
    aws ecr get-login-password --region ${AWS_REGION} | \
      docker login --username AWS --password-stdin ${ECR_BASE}

    # Update compose with new image tags
    export BACKEND_IMAGE=${BACKEND_IMG}
    export FRONTEND_IMAGE=${FRONTEND_IMG}

    # Pull new images
    docker pull ${BACKEND_IMG}
    docker pull ${FRONTEND_IMG}

    # Restart with new images
    BACKEND_IMAGE=${BACKEND_IMG} FRONTEND_IMAGE=${FRONTEND_IMG} \
      docker-compose up -d --remove-orphans

    echo "Deployed version: ${VERSION}"
REMOTE

  ok "Deployed to AWS."
  echo ""
  echo -e "  ${CYAN}App:${NC}     http://${EC2_HOST}"
  echo -e "  ${CYAN}API:${NC}     http://${EC2_HOST}:8000"
  echo -e "  ${CYAN}Version:${NC} ${VERSION}"
  echo ""
}

case "${1:-local}" in
  local)   local_deploy ;;
  stop)    log "Stopping..."; $COMPOSE down; ok "Stopped." ;;
  logs)    $COMPOSE logs -f ;;
  status)  $COMPOSE ps && echo "" && curl -sf http://localhost:8000/health && echo " ✅ healthy" || echo " ❌ not responding" ;;
  rebuild) log "Rebuilding..."; $COMPOSE down; $COMPOSE build --no-cache; $COMPOSE up -d; ok "Rebuilt and running." ;;
  aws)     aws_deploy ;;
  *)       echo "Usage: ./docker/deploy.sh [local|stop|logs|status|rebuild|aws]"; exit 1 ;;
esac

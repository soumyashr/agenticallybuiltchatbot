#!/bin/bash
# ────────────────────────────────────────────────────────────
# setup_aws.sh — One-time AWS infrastructure setup
#
# Run ONCE before first deploy.
# Requires: aws CLI configured with sufficient IAM permissions.
#
# What it does:
#   1. Creates two ECR repositories (backend + frontend)
#   2. Prints EC2 setup instructions (manual step)
# ────────────────────────────────────────────────────────────
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/.env"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${CYAN}[AWS Setup]${NC} $1"; }
ok()   { echo -e "${GREEN}[✅]${NC} $1"; }
warn() { echo -e "${YELLOW}[⚠️]${NC} $1"; }
fail() { echo -e "${RED}[❌]${NC} $1"; exit 1; }

# Validate required vars
[ -n "$AWS_ACCOUNT_ID" ] || fail "AWS_ACCOUNT_ID not set in .env"
[ -n "$AWS_REGION"     ] || fail "AWS_REGION not set in .env"

ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ── 1. Create ECR repositories ───────────────────────────────
log "Creating ECR repository: ${ECR_BACKEND_REPO:-hm-knowledge-hub-backend}"
aws ecr create-repository \
  --repository-name "${ECR_BACKEND_REPO:-hm-knowledge-hub-backend}" \
  --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true \
  2>/dev/null && ok "Backend ECR repo created." || warn "Backend ECR repo may already exist."

log "Creating ECR repository: ${ECR_FRONTEND_REPO:-hm-knowledge-hub-frontend}"
aws ecr create-repository \
  --repository-name "${ECR_FRONTEND_REPO:-hm-knowledge-hub-frontend}" \
  --region "$AWS_REGION" \
  --image-scanning-configuration scanOnPush=true \
  2>/dev/null && ok "Frontend ECR repo created." || warn "Frontend ECR repo may already exist."

# ── 2. EC2 manual setup instructions ─────────────────────────
echo ""
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  MANUAL STEPS — Complete these in AWS Console before      ${NC}"
echo -e "${YELLOW}  running ./docker/deploy.sh aws                            ${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  1. Launch EC2 instance:"
echo "     - AMI:           Amazon Linux 2023 (arm64)"
echo "     - Instance type: t4g.medium (ARM, ~\$30/month)"
echo "     - Storage:       20 GB gp3"
echo "     - Security group: allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)"
echo "     - IAM role:      attach a role with AmazonEC2ContainerRegistryReadOnly"
echo ""
echo "  2. SSH into EC2 and run:"
cat << 'REMOTE_SETUP'
     sudo yum update -y
     sudo yum install -y docker
     sudo systemctl enable docker
     sudo systemctl start docker
     sudo usermod -aG docker ec2-user
     sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" -o /usr/local/bin/docker-compose
     sudo chmod +x /usr/local/bin/docker-compose
     mkdir -p /opt/AgenticallyBuiltChatBot
REMOTE_SETUP
echo ""
echo "  3. Update .env with your EC2 public IP/domain:"
echo "     EC2_HOST=<your-ec2-public-ip>"
echo "     EC2_KEY_PATH=~/.ssh/your-key.pem"
echo ""
echo -e "${GREEN}  Then run: ./docker/deploy.sh aws${NC}"
echo ""

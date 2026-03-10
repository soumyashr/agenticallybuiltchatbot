# 10 — AWS_DEPLOY.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build AWS deployment scripts with placeholder credentials.
# Prerequisites: 09_DOCKER.md must be COMPLETE and VERIFIED.

---

## What Gets Built

### Option A — EC2 (original spec)
```
Local Mac  →  docker build  →  ECR (image registry)
                                    ↓
                              EC2 t3.medium
                              (pulls + runs containers)
                              nginx on port 80
                              HTTPS via Let's Encrypt
```

### Option B — AWS App Runner (current deployment)
```
Local Mac  →  docker build  →  ECR (image registry)
                                    ↓
                              AWS App Runner
                              (fully managed, auto-scaling)
                              HTTPS by default
                              URL: https://c2cnjknssm.ap-south-1.awsapprunner.com
```

### App Runner Backend Environment Variables
The following env vars must be set in the App Runner service configuration:
```
OPENAI_API_KEY          ← required
AI_PROVIDER=azure_openai
LLM_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-ada-002
AZURE_OPENAI_ENDPOINT=  ← required if AI_PROVIDER=azure_openai
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
AZURE_SEARCH_ENDPOINT=  ← required if AI_PROVIDER=azure_openai
AZURE_SEARCH_ADMIN_KEY=
AZURE_SEARCH_INDEX=
DYNAMO_TABLE=hm-documents
DYNAMO_REGION=ap-south-1
JWT_SECRET=<production-secret>
DATA_DIR=data
VECTOR_STORE_DIR=vector_store
```

### IAM Role
The App Runner service uses instance role `apprunner-hm-instance-role` with
`AmazonDynamoDBFullAccess` policy attached. This allows the backend to
read/write the `hm-documents` DynamoDB table without explicit AWS credentials.

### Frontend Build Arg
The frontend Docker build must pass the backend URL as a build arg:
```
docker build --build-arg VITE_API_URL=https://<backend-url> ...
```
This is consumed in `constants.js`:
```js
export const API_BASE = import.meta.env.VITE_API_URL || '';
```

### Stateless Container Limitation
App Runner containers are stateless. PDF files uploaded to `data/` are lost
on redeployment. However, document metadata now persists in DynamoDB
(table: hm-documents) and survives redeployments. The vector store
(Azure AI Search) is also cloud-hosted and persistent.

CORS in `main.py` includes the App Runner URL:
```python
allow_origins=[..., "https://c2cnjknssm.ap-south-1.awsapprunner.com"]
```

---

## STEP 1 — Add AWS variables to docker/.env.example

Append these lines to `docker/.env.example`:
```
# ── AWS (fill before running deploy.sh aws) ──────────────────
AWS_ACCOUNT_ID=YOUR_ACCOUNT_ID_HERE
AWS_REGION=ap-south-1
EC2_HOST=YOUR_EC2_PUBLIC_IP_OR_DOMAIN
EC2_KEY_PATH=~/.ssh/your-key.pem
ECR_BACKEND_REPO=hm-knowledge-hub-backend
ECR_FRONTEND_REPO=hm-knowledge-hub-frontend
```

---

## STEP 2 — docker/setup_aws.sh

Write to `docker/setup_aws.sh`:
```bash
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
```

Make executable:
```bash
chmod +x docker/setup_aws.sh
```

---

## STEP 3 — Update docker/deploy.sh to add aws command

Add the `aws_deploy` function and `aws` case to `docker/deploy.sh`.

Append this function BEFORE the `case` statement in deploy.sh:
```bash
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
```

Update the `case` block in deploy.sh to include:
```bash
  aws)     aws_deploy ;;
```

---

## STEP 4 — docker/ec2_setup.sh (copy-paste ready for EC2)

Write to `docker/ec2_setup.sh`:
```bash
#!/bin/bash
# ────────────────────────────────────────────────────────────
# ec2_setup.sh — Run this script ON the EC2 instance (once)
# SSH into EC2 first: ssh -i your-key.pem ec2-user@<ec2-ip>
# Then run: bash ec2_setup.sh
# ────────────────────────────────────────────────────────────
set -e

echo "Installing Docker..."
sudo yum update -y
sudo yum install -y docker awscli
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ec2-user

echo "Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

echo "Creating app directory..."
sudo mkdir -p /opt/AgenticallyBuiltChatBot
sudo chown ec2-user:ec2-user /opt/AgenticallyBuiltChatBot

echo ""
echo "✅ EC2 setup complete."
echo "Next: run ./docker/deploy.sh aws from your local machine."
```

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL.

- [ ] `docker/setup_aws.sh` runs without error (after AWS credentials configured)
- [ ] Two ECR repositories appear in AWS Console: hm-knowledge-hub-backend, hm-knowledge-hub-frontend
- [ ] `docker/deploy.sh aws` builds both images and pushes to ECR
- [ ] Images appear in ECR with the version timestamp tag
- [ ] SSH connection to EC2 succeeds from deploy.sh
- [ ] `.env` is copied to EC2 at `/opt/AgenticallyBuiltChatBot/.env`
- [ ] Containers start on EC2 (`docker ps` shows both healthy)
- [ ] `http://<EC2_HOST>` loads the login screen
- [ ] Login and chat work from the EC2 URL
- [ ] `docker volume ls` on EC2 shows the 3 named volumes

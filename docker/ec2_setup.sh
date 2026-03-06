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
echo "EC2 setup complete."
echo "Next: run ./docker/deploy.sh aws from your local machine."

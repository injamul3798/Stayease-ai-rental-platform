# EC2 Deployment Guide

This guide deploys the project on a single EC2 instance with:
- frontend on the same server
- FastAPI backend on the same server
- PostgreSQL in Docker
- Redis in Docker
- Nginx as the public reverse proxy

## 1. Launch EC2

Use these settings in AWS Console:

- Name: `stayease-prod`
- AMI: `Ubuntu Server 24.04 LTS`
- Architecture: `64-bit (x86)`
- Instance type: `m7i-flex.large` recommended, `t3.medium` acceptable
- Storage: `30 GiB gp3`
- Auto-assign public IP: `Enable`
- Security group inbound:
  - `22` from `My IP`
  - `80` from `Anywhere`
  - `443` from `Anywhere`

Do not open:
- `5432`
- `5433`
- `6379`
- `8000`

After launch, attach an Elastic IP.

## 2. Connect to the server

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

## 3. Install system packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git python3 python3-venv python3-pip nginx ca-certificates curl
```

## 4. Install Docker Engine and Compose plugin

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu
exit
```

SSH in again:

```bash
ssh -i your-key.pem ubuntu@YOUR_EC2_PUBLIC_IP
```

## 5. Clone the repo

```bash
git clone <YOUR_REPO_URL>
cd Stayease-ai-rental-platform
```

## 6. Create the production `.env`

```bash
cat > .env <<'EOF'
ENVIRONMENT=production
LOG_LEVEL=INFO
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=gpt-4.1-mini
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5433/stayease
REDIS_URL=redis://127.0.0.1:6379/0
APP_HOST=127.0.0.1
APP_PORT=8000
CORS_ORIGINS=http://YOUR_EC2_PUBLIC_IP
EOF
```

If you use a domain later, update `CORS_ORIGINS` to `https://yourdomain.com`.

## 7. Create Python environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 8. Start PostgreSQL and Redis

```bash
docker compose up -d
docker compose ps
```

## 9. Seed the database

```bash
source .venv/bin/activate
python scripts/seed_listings.py
```

## 10. Update frontend conversation ID generation

```bash
cp frontend/app.js frontend/app.js.bak
python3 - <<'PY'
from pathlib import Path

path = Path("frontend/app.js")
text = path.read_text(encoding="utf-8")

old1 = """void initializeChat();

function loadConversationId() {
"""
new1 = """void initializeChat();

function generateConversationId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `conv-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadConversationId() {
"""

old2 = """  const freshId = crypto.randomUUID();"""
new2 = """  const freshId = generateConversationId();"""

text = text.replace(old1, new1)
text = text.replace(old2, new2, 2)

path.write_text(text, encoding="utf-8")
print("updated frontend/app.js")
PY
```

## 11. Test the app once

```bash
source .venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

In another SSH tab:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/
```

If it works, stop Uvicorn with `Ctrl+C`.

## 12. Create the systemd service file

```bash
sudo tee /etc/systemd/system/stayease.service > /dev/null <<'EOF'
[Unit]
Description=StayEase FastAPI App
After=network.target docker.service
Requires=docker.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/Stayease-ai-rental-platform
Environment="PATH=/home/ubuntu/Stayease-ai-rental-platform/.venv/bin"
ExecStart=/home/ubuntu/Stayease-ai-rental-platform/.venv/bin/gunicorn -w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 main:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

Enable and start the app service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable stayease
sudo systemctl start stayease
sudo systemctl status stayease
```

## 13. Create the Nginx site config

```bash
sudo tee /etc/nginx/sites-available/stayease > /dev/null <<'EOF'
server {
    listen 80;
    server_name YOUR_EC2_PUBLIC_IP;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
```

Enable Nginx config and reload:

```bash
sudo ln -sf /etc/nginx/sites-available/stayease /etc/nginx/sites-enabled/stayease
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

## 14. Open the site publicly

Visit:

```text
http://YOUR_EC2_PUBLIC_IP
```

## 15. Optional: add SSL with a domain

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 16. Useful commands later

```bash
sudo journalctl -u stayease -f
docker compose logs -f
sudo systemctl restart stayease
git pull
source .venv/bin/activate && pip install -r requirements.txt
docker compose up -d
sudo systemctl restart stayease
```

## Important

- Keep ports `5433`, `6379`, and `8000` closed in AWS Security Group.
- This repo uses PostgreSQL, not MySQL.
- `.env` should stay only on the server and never be committed.
- For this codebase, use `gunicorn` with `nginx` for deployment.

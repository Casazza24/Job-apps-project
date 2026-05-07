#!/usr/bin/env bash
set -euo pipefail

# VM startup script — run once after VM creation or on reboot

sudo apt-get update && sudo apt-get install -y \
  python3-pip python3-venv git postgresql postgresql-contrib \
  chromium chromium-driver xvfb \
  libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0

cd /home/$(logname) || cd /root

if [ ! -d "job-agent" ]; then
  git clone https://github.com/YOUR_HANDLE/job-agent.git
fi

cd job-agent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

playwright install chromium
playwright install-deps

# Set up local Postgres
sudo -u postgres psql -c "CREATE DATABASE jobagent;" 2>/dev/null || echo "DB exists"
sudo -u postgres psql -c "CREATE USER jobagent WITH PASSWORD 'jobagent';" 2>/dev/null || echo "User exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE jobagent TO jobagent;" 2>/dev/null || true
psql -U jobagent -d jobagent -h localhost -f db/schema.sql 2>/dev/null || echo "Schema may already exist"

sudo cp infra/job-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable job-agent
sudo systemctl start job-agent

echo "VM setup complete"

#!/usr/bin/env bash
# Установка BCC Shield на Linux-сервер: Docker, если есть, иначе venv + systemd.
set -euo pipefail
cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"
[ -f .env ] || cp .env.example .env
PORT=$(grep -E "^BCC_PORT=" .env | cut -d= -f2); PORT=${PORT:-8000}

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo ">> Docker найден, запускаю docker compose"
  docker compose up -d --build
else
  echo ">> Docker не найден, ставлю через Python venv + systemd"
  if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    echo "!! Нужен Python 3.11+, сейчас: $(python3 --version 2>&1)"; exit 1
  fi
  python3 -m venv .venv 2>/dev/null || { sudo apt-get update && sudo apt-get install -y python3-venv && python3 -m venv .venv; }
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  sudo tee /etc/systemd/system/bcc-shield.service >/dev/null <<UNIT
[Unit]
Description=BCC Shield demo
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python -m app
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable --now bcc-shield
  sudo systemctl restart bcc-shield
fi

if command -v ufw >/dev/null 2>&1 && sudo -n ufw status 2>/dev/null | grep -q "Status: active"; then
  sudo ufw allow 8000/tcp
fi

sleep 8
if curl -sf http://127.0.0.1:$PORT/api/config >/dev/null; then
  echo ">> Готово: http://$(hostname -I | awk '{print $1}'):$PORT"
else
  echo "!! Сервер не ответил. Логи: journalctl -u bcc-shield -n 50  (или docker compose logs)"
fi

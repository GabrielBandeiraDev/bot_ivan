#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Ambiente virtual não encontrado. Rode: python -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

# .env é criado pelo main.py se não existir
./venv/bin/python main.py

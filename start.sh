#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
nohup python -m src.main > nohup.out 2>&1 &
echo "TradeExtension запущен (PID $!)"
echo $! > .pid

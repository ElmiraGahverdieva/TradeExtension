#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
nohup python -m src.main > nohup.out 2>&1 &
PID=$!
echo $PID > .pid
echo "TradeExtension запущен (PID $PID)"
# Не даём Mac засыпать пока работает приложение
caffeinate -i -w $PID &
echo "Режим без сна активирован"

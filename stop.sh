#!/bin/bash
cd "$(dirname "$0")"
if [ -f .pid ]; then
    kill $(cat .pid) 2>/dev/null && echo "TradeExtension остановлен"
    rm .pid
else
    pkill -f "src.main" && echo "TradeExtension остановлен"
fi

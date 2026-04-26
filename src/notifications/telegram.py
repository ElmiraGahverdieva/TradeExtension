import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

from src import config
from src.strategy.signal_engine import Signal, SignalType

logger = logging.getLogger(__name__)


def _format_telegram(signal: Signal) -> str:
    arrow = "BUY" if signal.signal_type == SignalType.BUY else "SELL"
    dt = datetime.fromtimestamp(signal.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"*{arrow} SIGNAL — {signal.symbol}*",
        f"Strength: {signal.strength.value} ({signal.score}/{signal.max_score})",
        f"Price: `{signal.price:,.4f}`",
        "",
        "*Conditions:*",
    ]
    for name, hit in signal.conditions.items():
        mark = "YES" if hit else "NO "
        lines.append(f"  [{mark}] {name}")
    lines.append(f"\n_{dt}_")

    return "\n".join(lines)


async def send_telegram(signal: Signal):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.debug("Telegram not configured, skipping")
        return

    text = _format_telegram(signal)
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error("Telegram API error %d: %s", resp.status, body)
                else:
                    logger.info("Telegram message sent for %s", signal.symbol)
    except Exception as exc:
        logger.error("Telegram send failed: %s", exc)

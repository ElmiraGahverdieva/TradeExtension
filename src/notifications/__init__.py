import asyncio
import logging

from src import config
from src.strategy.signal_engine import Signal
from src.notifications.desktop import send_desktop
from src.notifications.telegram import send_telegram

logger = logging.getLogger(__name__)


async def dispatch(signal: Signal):
    """Send signal via all configured notification channels."""
    logger.info(
        "SIGNAL %s %s score=%d/%d price=%.4f",
        signal.signal_type.value, signal.symbol,
        signal.score, signal.max_score, signal.price,
    )

    mode = config.NOTIFICATION_MODE.lower()

    if mode in ("desktop", "both"):
        await asyncio.get_event_loop().run_in_executor(None, send_desktop, signal)

    if mode in ("telegram", "both"):
        await send_telegram(signal)

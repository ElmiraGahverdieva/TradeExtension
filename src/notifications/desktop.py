import logging
from datetime import datetime, timezone

from src.strategy.signal_engine import Signal, SignalType

logger = logging.getLogger(__name__)


def _format_message(signal: Signal) -> tuple[str, str]:
    """Return (title, body) for the notification."""
    icon = "BUY" if signal.signal_type == SignalType.BUY else "SELL"
    dt = datetime.fromtimestamp(signal.timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    title = f"{icon} SIGNAL — {signal.symbol} [{signal.strength.value}]"

    lines = [
        f"Price:    {signal.price:,.4f}",
        f"Score:    {signal.score}/{signal.max_score}",
        "",
    ]
    for name, hit in signal.conditions.items():
        mark = "YES" if hit else "NO "
        lines.append(f"  [{mark}] {name}")
    lines.append("")
    lines.append(f"Time: {dt}")

    return title, "\n".join(lines)


def send_desktop(signal: Signal):
    title, body = _format_message(signal)
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=body,
            app_name="TradeExtension",
            timeout=10,
        )
        logger.info("Desktop notification sent: %s", title)
    except Exception as exc:
        logger.warning("Desktop notification failed (%s), printing to console", exc)
        _print_to_console(title, body)


def _print_to_console(title: str, body: str):
    sep = "=" * 50
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)
    print(body)
    print(sep)

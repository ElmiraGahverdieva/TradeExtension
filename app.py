"""
TradeExtension — GUI launcher
Run: python app.py
"""
import asyncio
import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext
from typing import Optional

# ── ensure project root is on path ────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from src import config
from src.api.rest_client import DzengiRestClient
from src.api.ws_client import DzengiWsClient
from src.strategy.signal_engine import SignalEngine
from src.notifications import dispatch

# ── colours ───────────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
BG2      = "#16213e"
BG3      = "#0f3460"
GREEN    = "#00b894"
RED      = "#d63031"
YELLOW   = "#fdcb6e"
TEXT     = "#dfe6e9"
TEXT_DIM = "#636e72"
FONT_LOG = ("Menlo", 11)
FONT_UI  = ("SF Pro Display", 13)
FONT_BIG = ("SF Pro Display", 15, "bold")


# ── logging → queue ───────────────────────────────────────────────────────────
class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self._q = q

    def emit(self, record):
        self._q.put(self.format(record))


# ── main app ──────────────────────────────────────────────────────────────────
class App:
    def __init__(self):
        self._log_q: queue.Queue = queue.Queue()
        self._stop_event: threading.Event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._caffeinate: Optional[subprocess.Popen] = None
        self._engine = SignalEngine()

        self._setup_logging()
        self._build_ui()

    # ── logging ───────────────────────────────────────────────────────────────
    def _setup_logging(self):
        fmt = "%(asctime)s  %(message)s"
        handler = _QueueHandler(self._log_q)
        handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/trading.log", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt))
        root_logger.addHandler(file_handler)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = tk.Tk()
        root.title("TradeExtension")
        root.configure(bg=BG)
        root.geometry("800x560")
        root.resizable(True, True)
        self.root = root

        # ── header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=BG2, pady=12)
        hdr.pack(fill=tk.X)

        tk.Label(hdr, text="TradeExtension", bg=BG2, fg=TEXT,
                 font=FONT_BIG).pack(side=tk.LEFT, padx=16)

        # status dot + label
        self._dot = tk.Label(hdr, text="●", bg=BG2, fg=RED, font=("Menlo", 18))
        self._dot.pack(side=tk.LEFT, padx=(8, 2))
        self._status_lbl = tk.Label(hdr, text="Остановлен", bg=BG2,
                                    fg=TEXT_DIM, font=FONT_UI)
        self._status_lbl.pack(side=tk.LEFT)

        # symbols info
        syms = ", ".join(config.SYMBOLS)
        tk.Label(hdr, text=f"{syms}  •  {config.TIMEFRAME}",
                 bg=BG2, fg=TEXT_DIM, font=FONT_UI).pack(side=tk.RIGHT, padx=16)

        # ── controls ──────────────────────────────────────────────────────────
        ctrl = tk.Frame(root, bg=BG, pady=10)
        ctrl.pack(fill=tk.X, padx=16)

        self._btn = tk.Button(
            ctrl, text="▶  Начать мониторинг",
            bg=GREEN, fg="white", activebackground="#00cec9",
            font=FONT_BIG, relief=tk.FLAT, padx=24, pady=8,
            cursor="hand2", command=self._toggle,
        )
        self._btn.pack(side=tk.LEFT)

        self._sleep_lbl = tk.Label(ctrl, text="", bg=BG, fg=TEXT_DIM,
                                   font=FONT_UI)
        self._sleep_lbl.pack(side=tk.LEFT, padx=16)

        # ── log area ──────────────────────────────────────────────────────────
        log_frame = tk.Frame(root, bg=BG3, padx=2, pady=2)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        self._log_box = scrolledtext.ScrolledText(
            log_frame, bg="#0d0d1a", fg=TEXT, font=FONT_LOG,
            state=tk.DISABLED, relief=tk.FLAT, wrap=tk.WORD,
        )
        self._log_box.pack(fill=tk.BOTH, expand=True)

        # colour tags
        self._log_box.tag_config("candle", foreground="#74b9ff")
        self._log_box.tag_config("signal", foreground=YELLOW)
        self._log_box.tag_config("error",  foreground=RED)
        self._log_box.tag_config("info",   foreground=TEXT_DIM)

        # ── start polling ─────────────────────────────────────────────────────
        self._poll_logs()

    # ── toggle start / stop ───────────────────────────────────────────────────
    def _toggle(self):
        if self._thread and self._thread.is_alive():
            self._stop()
        else:
            self._start()

    def _start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()

        # prevent Mac from sleeping
        try:
            self._caffeinate = subprocess.Popen(["caffeinate", "-i"])
            self._sleep_lbl.config(text="☕ Режим без сна включён")
        except FileNotFoundError:
            pass

        self._btn.config(text="■  Остановить мониторинг",
                         bg=RED, activebackground="#e17055")
        self._dot.config(fg=YELLOW)
        self._status_lbl.config(text="Подключение…", fg=YELLOW)

    def _stop(self):
        self._stop_event.set()
        if self._caffeinate:
            self._caffeinate.terminate()
            self._caffeinate = None
        self._sleep_lbl.config(text="")
        self._btn.config(text="▶  Начать мониторинг",
                         bg=GREEN, activebackground="#00cec9")
        self._dot.config(fg=RED)
        self._status_lbl.config(text="Остановлен", fg=TEXT_DIM)

    # ── asyncio in background thread ──────────────────────────────────────────
    def _run_async(self):
        asyncio.run(self._async_main())

    async def _async_main(self):
        logger = logging.getLogger(__name__)

        # load history
        self.root.after(0, lambda: self._status_lbl.config(
            text="Загрузка истории…", fg=YELLOW))
        async with DzengiRestClient() as rest:
            for symbol in config.SYMBOLS:
                try:
                    klines = await rest.get_klines(
                        symbol, config.TIMEFRAME, config.CANDLE_BUFFER_SIZE)
                    buf = self._engine.get_buffer(symbol)
                    buf.clear()
                    buf.load_klines(klines)
                    logger.info("  %s: загружено %d свечей", symbol, len(klines))
                except Exception as exc:
                    logger.error("Ошибка загрузки %s: %s", symbol, exc)

        self.root.after(0, lambda: (
            self._dot.config(fg=GREEN),
            self._status_lbl.config(text="Мониторинг активен", fg=GREEN),
        ))

        ws = DzengiWsClient(config.SYMBOLS, config.TIMEFRAME, self._on_candle)

        async def _watch_stop():
            while not self._stop_event.is_set():
                await asyncio.sleep(0.5)
            await ws.stop()

        await asyncio.gather(ws.run(), _watch_stop(), self._volume_loop())

    async def _on_candle(self, symbol: str, candle: dict):
        logging.getLogger(__name__).info(
            "Candle %-20s O=%-9.2f H=%-9.2f L=%-9.2f C=%.2f",
            symbol, candle["open"], candle["high"], candle["low"], candle["close"],
        )
        signal = self._engine.on_new_candle(symbol, candle)
        if signal:
            await dispatch(signal)

    async def _volume_loop(self):
        await asyncio.sleep(65)
        while not self._stop_event.is_set():
            try:
                async with DzengiRestClient() as rest:
                    for symbol in config.SYMBOLS:
                        klines = await rest.get_klines(
                            symbol, config.TIMEFRAME, config.CANDLE_BUFFER_SIZE)
                        buf = self._engine.get_buffer(symbol)
                        buf.clear()
                        buf.load_klines(klines)
            except Exception as exc:
                logging.getLogger(__name__).warning("Volume refresh: %s", exc)
            await asyncio.sleep(60)

    # ── log polling ───────────────────────────────────────────────────────────
    def _poll_logs(self):
        try:
            while True:
                msg = self._log_q.get_nowait()
                self._add_log(msg)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_logs)

    def _add_log(self, msg: str):
        box = self._log_box
        box.config(state=tk.NORMAL)

        if "Candle" in msg:
            tag = "candle"
        elif "SIGNAL" in msg or "BUY" in msg or "SELL" in msg:
            tag = "signal"
        elif "ERROR" in msg or "error" in msg.lower():
            tag = "error"
        else:
            tag = "info"

        box.insert(tk.END, msg + "\n", tag)
        box.see(tk.END)

        # keep last 500 lines
        lines = int(box.index("end-1c").split(".")[0])
        if lines > 500:
            box.delete("1.0", f"{lines - 500}.0")

        box.config(state=tk.DISABLED)

    # ── run ───────────────────────────────────────────────────────────────────
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self._stop()
        self.root.destroy()


if __name__ == "__main__":
    App().run()

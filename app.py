"""
TradeExtension — Web dashboard
Run: python app.py
Opens automatically in your browser at http://localhost:5678
"""
import asyncio
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))

from src import config
from src.api.rest_client import DzengiRestClient
from src.api.ws_client import DzengiWsClient
from src.strategy.signal_engine import SignalEngine
from src.notifications import dispatch

# ── shared state ──────────────────────────────────────────────────────────────
_log_buffer: deque = deque(maxlen=300)
_sse_queues: list = []
_sse_lock = threading.Lock()
_status = {"running": False, "status_text": "Остановлен", "prices": {}}
_engine = SignalEngine()
_stop_event = threading.Event()
_monitor_thread: Optional[threading.Thread] = None
_caffeinate: Optional[subprocess.Popen] = None


# ── logging → SSE ─────────────────────────────────────────────────────────────
class _SSEHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        entry = {"t": time.strftime("%H:%M:%S"), "msg": msg}
        _log_buffer.append(entry)
        with _sse_lock:
            for q in list(_sse_queues):
                try:
                    q.put_nowait(entry)
                except Exception:
                    pass


def _setup_logging():
    fmt = "%(asctime)s  %(message)s"
    handler = _SSEHandler()
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    os.makedirs("logs", exist_ok=True)
    fh = logging.FileHandler("logs/trading.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)


# ── trading engine ─────────────────────────────────────────────────────────────
def start_monitoring():
    global _monitor_thread, _caffeinate
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _stop_event.clear()
    _engine.__init__()  # reset engine
    _status.update(running=True, status_text="Загрузка…")
    _monitor_thread = threading.Thread(target=_run_async, daemon=True)
    _monitor_thread.start()
    try:
        _caffeinate = subprocess.Popen(["caffeinate", "-i"])
    except FileNotFoundError:
        pass


def stop_monitoring():
    global _caffeinate
    _stop_event.set()
    _status.update(running=False, status_text="Остановлен")
    if _caffeinate:
        _caffeinate.terminate()
        _caffeinate = None


def _run_async():
    asyncio.run(_async_main())


async def _async_main():
    logger = logging.getLogger(__name__)
    _status["status_text"] = "Загрузка истории…"

    async with DzengiRestClient() as rest:
        for symbol in config.SYMBOLS:
            for tf in config.TIMEFRAMES:
                try:
                    klines = await rest.get_klines(symbol, tf, config.CANDLE_BUFFER_SIZE)
                    buf = _engine.get_buffer(symbol, tf)
                    buf.clear()
                    buf.load_klines(klines)
                    logger.info("📦 %s [%s]: загружено %d свечей", symbol, tf, len(klines))
                except Exception as exc:
                    logger.error("❌ Ошибка загрузки %s [%s]: %s", symbol, tf, exc)
                await asyncio.sleep(0.4)

    _status["status_text"] = "Мониторинг активен"

    ws = DzengiWsClient(config.SYMBOLS, config.TIMEFRAMES, _on_candle)

    async def _watch_stop():
        while not _stop_event.is_set():
            await asyncio.sleep(0.5)
        await ws.stop()

    await asyncio.gather(ws.run(), _watch_stop(), _volume_loop())


async def _on_candle(symbol: str, candle: dict):
    _status["prices"][symbol] = candle["close"]
    logging.getLogger(__name__).info(
        "🕯 %-22s  O=%-10.2f  H=%-10.2f  L=%-10.2f  C=%.2f",
        symbol, candle["open"], candle["high"], candle["low"], candle["close"],
    )
    signal = _engine.on_new_candle(symbol, candle)
    if signal:
        await dispatch(signal)


async def _volume_loop():
    await asyncio.sleep(65)
    while not _stop_event.is_set():
        try:
            async with DzengiRestClient() as rest:
                for symbol in config.SYMBOLS:
                    for tf in config.TIMEFRAMES:
                        klines = await rest.get_klines(symbol, tf, config.CANDLE_BUFFER_SIZE)
                        buf = _engine.get_buffer(symbol, tf)
                        buf.clear()
                        buf.load_klines(klines)
                        await asyncio.sleep(0.4)
        except Exception as exc:
            logging.getLogger(__name__).warning("Volume refresh: %s", exc)
        await asyncio.sleep(60)


# ── HTML page ─────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradeExtension</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0d1117; color: #e6edf3; font-family: -apple-system, sans-serif; height: 100vh; display: flex; flex-direction: column; }

  header { background: #161b22; border-bottom: 1px solid #30363d; padding: 14px 24px; display: flex; align-items: center; gap: 16px; }
  header h1 { font-size: 18px; font-weight: 600; letter-spacing: .5px; }

  .dot { width: 11px; height: 11px; border-radius: 50%; background: #f85149; transition: background .4s; flex-shrink: 0; }
  .dot.active { background: #3fb950; box-shadow: 0 0 8px #3fb950; }
  .dot.loading { background: #d29922; box-shadow: 0 0 8px #d29922; }

  #status-text { font-size: 13px; color: #8b949e; }

  .prices { margin-left: auto; display: flex; gap: 20px; }
  .price-item { text-align: right; }
  .price-sym { font-size: 11px; color: #8b949e; }
  .price-val { font-size: 14px; font-weight: 600; color: #e6edf3; font-variant-numeric: tabular-nums; }

  .controls { padding: 14px 24px; background: #0d1117; border-bottom: 1px solid #21262d; display: flex; gap: 12px; align-items: center; }

  btn { display: inline-flex; align-items: center; gap: 8px; padding: 9px 22px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all .2s; }
  #btn-start { background: #238636; color: #fff; }
  #btn-start:hover { background: #2ea043; }
  #btn-stop  { background: #da3633; color: #fff; }
  #btn-stop:hover  { background: #f85149; }

  #sleep-note { font-size: 12px; color: #8b949e; margin-left: 4px; }

  #log-wrap { flex: 1; overflow-y: auto; padding: 12px 24px; scroll-behavior: smooth; }

  .log-line { padding: 3px 0; font-size: 13px; font-family: "SF Mono", Menlo, monospace; line-height: 1.55; white-space: pre-wrap; word-break: break-all; }
  .log-line .ts { color: #484f58; margin-right: 8px; }
  .log-candle  .body { color: #58a6ff; }
  .log-signal  .body { color: #ffa657; font-weight: 600; }
  .log-error   .body { color: #f85149; }
  .log-info    .body { color: #8b949e; }
  .log-ok      .body { color: #3fb950; }

  #empty { text-align: center; margin-top: 80px; color: #484f58; font-size: 15px; }

  footer { padding: 8px 24px; background: #161b22; border-top: 1px solid #21262d; font-size: 11px; color: #484f58; display: flex; justify-content: space-between; }
</style>
</head>
<body>
<header>
  <div class="dot" id="dot"></div>
  <h1>TradeExtension</h1>
  <span id="status-text">Остановлен</span>
  <div class="prices" id="prices"></div>
</header>

<div class="controls">
  <button id="btn-start" onclick="startMonitor()">▶&nbsp; Начать мониторинг</button>
  <button id="btn-stop"  onclick="stopMonitor()" style="display:none">■&nbsp; Остановить</button>
  <span id="sleep-note"></span>
</div>

<div id="log-wrap">
  <div id="empty">Нажмите «Начать мониторинг»</div>
  <div id="log"></div>
</div>

<footer>
  <span id="footer-syms">__SYMBOLS__  •  __TF__</span>
  <span>TradeExtension</span>
</footer>

<script>
let evtSource = null;
let lineCount = 0;

function classify(msg) {
  if (msg.includes('🕯') || msg.includes('Candle')) return 'log-candle';
  if (msg.includes('SIGNAL') || msg.includes('BUY') || msg.includes('SELL') || msg.includes('🟢') || msg.includes('🔴')) return 'log-signal';
  if (msg.includes('ERROR') || msg.includes('❌')) return 'log-error';
  if (msg.includes('✅') || msg.includes('загружено') || msg.includes('📦')) return 'log-ok';
  return 'log-info';
}

function addLine(entry) {
  const empty = document.getElementById('empty');
  if (empty) empty.remove();

  const wrap = document.getElementById('log');
  const div = document.createElement('div');
  div.className = 'log-line ' + classify(entry.msg);
  div.innerHTML = '<span class="ts">' + entry.t + '</span><span class="body">' + escHtml(entry.msg.replace(/^\\d{2}:\\d{2}:\\d{2}\\s+/, '')) + '</span>';
  wrap.appendChild(div);
  lineCount++;
  if (lineCount > 300) wrap.removeChild(wrap.firstChild);
  document.getElementById('log-wrap').scrollTop = 999999;
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function pollStatus() {
  fetch('/status').then(r=>r.json()).then(d => {
    const dot = document.getElementById('dot');
    const st  = document.getElementById('status-text');
    dot.className = 'dot' + (d.running ? (d.status_text.includes('…') ? ' loading' : ' active') : '');
    st.textContent = d.status_text;
    const prices = document.getElementById('prices');
    prices.innerHTML = Object.entries(d.prices).map(([sym, val]) =>
      '<div class="price-item"><div class="price-sym">' + sym.replace('_LEVERAGE','') + '</div><div class="price-val">' + val.toLocaleString('en', {minimumFractionDigits:2, maximumFractionDigits:2}) + '</div></div>'
    ).join('');
    document.getElementById('btn-start').style.display = d.running ? 'none' : '';
    document.getElementById('btn-stop').style.display  = d.running ? '' : 'none';
    document.getElementById('sleep-note').textContent = d.running ? '☕ Mac не уснёт' : '';
  }).catch(()=>{});
  setTimeout(pollStatus, 1500);
}

function startSSE() {
  if (evtSource) evtSource.close();
  evtSource = new EventSource('/events');
  evtSource.onmessage = e => { try { addLine(JSON.parse(e.data)); } catch(_){} };
}

function startMonitor() {
  fetch('/start', {method:'POST'}).then(() => { startSSE(); pollStatus(); });
}

function stopMonitor() {
  fetch('/stop', {method:'POST'}).then(() => pollStatus());
  if (evtSource) { evtSource.close(); evtSource = null; }
}

pollStatus();
</script>
</body>
</html>
""".replace("__SYMBOLS__", ", ".join(config.SYMBOLS)).replace("__TF__", ", ".join(config.TIMEFRAMES))


# ── HTTP server ────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self._send(200, "text/html", HTML.encode())
        elif self.path == "/status":
            self._send(200, "application/json", json.dumps(_status).encode())
        elif self.path == "/logs":
            data = json.dumps(list(_log_buffer)).encode()
            self._send(200, "application/json", data)
        elif self.path == "/events":
            self._sse()
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        if self.path == "/start":
            start_monitoring()
        elif self.path == "/stop":
            stop_monitoring()
        self._send(200, "application/json", b'{"ok":true}')

    def _send(self, code, ct, body):
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q: queue.Queue = queue.Queue()
        with _sse_lock:
            _sse_queues.append(q)
        # send buffered history
        for entry in list(_log_buffer):
            try:
                self.wfile.write(f"data: {json.dumps(entry)}\n\n".encode())
            except Exception:
                break
        try:
            while True:
                try:
                    entry = q.get(timeout=15)
                    self.wfile.write(f"data: {json.dumps(entry)}\n\n".encode())
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except Exception:
            pass
        finally:
            with _sse_lock:
                if q in _sse_queues:
                    _sse_queues.remove(q)

    def log_message(self, *_):
        pass  # silence HTTP access logs


def _run_server(server: HTTPServer):
    server.serve_forever()


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _setup_logging()
    PORT = 5678
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=_run_server, args=(server,), daemon=True)
    t.start()

    url = f"http://localhost:{PORT}"
    print(f"TradeExtension запущен → {url}")
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_monitoring()
        server.shutdown()
        print("Остановлено.")

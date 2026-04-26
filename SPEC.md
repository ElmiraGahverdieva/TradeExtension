# ТЗ: Trading Notification Extension для Dzengi.com

## 1. Цель проекта

Создать Python-расширение, которое в реальном времени мониторит рынок на платформе Dzengi.com и отправляет уведомления пользователю при совпадении нескольких технических индикаторов, сигнализируя о потенциальных точках входа в сделку.

---

## 2. Платформа: Dzengi.com API

### 2.1 REST API

| Среда | Base URL |
|---|---|
| **Demo** | `https://demo-api-adapter.dzengi.com` |
| Live | `https://api-adapter.dzengi.com` |

**Типы эндпоинтов:**
- `PUBLIC` — без аутентификации, для рыночных данных
- `SIGNED` — требует API-ключ + HMAC SHA256 подпись

**Аутентификация:**
- Заголовок: `X-MBX-APIKEY: <api_key>`
- Подпись: `HMAC_SHA256(secret_key, query_string)` → параметр `signature`
- Обязателен параметр `timestamp` (миллисекунды)

**Основные публичные эндпоинты:**
```
GET /api/v1/exchangeInfo                  — список символов, настройки
GET /api/v1/klines?symbol=&interval=&limit= — свечи OHLCV
GET /api/v1/depth?symbol=&limit=          — стакан ордеров
GET /api/v1/ticker/price?symbol=          — текущая цена
GET /api/v1/ticker/24hr?symbol=           — статистика за 24ч
```

**Приватные эндпоинты (SIGNED):**
```
GET  /api/v1/account                      — баланс аккаунта
POST /api/v1/order                        — создать ордер
GET  /api/v1/openOrders                   — открытые ордера
GET  /api/v1/tradingPositions             — текущие позиции
GET  /api/v1/tradingPositionsHistory      — история позиций
```

**Параметры свечей (`interval`):**
`1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M`

> **Важно:** Для демо-аккаунта доступна только версия API v1.

### 2.2 WebSocket API

| Среда | URL |
|---|---|
| **Demo** | `wss://demo-api-adapter.dzengi.com/connect` |
| Live | `wss://api-adapter.dzengi.com/connect` |

**Каналы подписки:**
```json
{ "method": "SUBSCRIBE", "params": ["wss:OHLCMarketData.subscribe"], "id": 1 }
{ "method": "SUBSCRIBE", "params": ["wss:depthMarketData"],           "id": 2 }
{ "method": "SUBSCRIBE", "params": ["wss:tradeMarketData"],            "id": 3 }
```

- Дефолтный интервал для `OHLCMarketData`: `1m`
- Соединение закрывается если нет ping в течение 30 секунд

---

## 3. Торговая стратегия: Multi-Indicator Confluence

### 3.1 Концепция

Сигнал формируется только при совпадении **минимум 3 из 5** технических индикаторов. Это снижает количество ложных сигналов и повышает точность входа.

### 3.2 Индикаторы

#### RSI (Relative Strength Index) — период 14
Измеряет скорость и изменение ценовых движений. Один из самых надёжных momentum-индикаторов.

| Значение | Сигнал |
|---|---|
| RSI < 30 | BUY — зона перепроданности |
| RSI > 70 | SELL — зона перекупленности |
| RSI < 40 (для подтверждения) | Мягкий BUY |
| RSI > 60 (для подтверждения) | Мягкий SELL |

#### EMA Cross (Exponential Moving Average) — 9 / 21
Пересечение быстрой и медленной EMA — классический трендовый сигнал.

| Событие | Сигнал |
|---|---|
| EMA(9) пересекает EMA(21) снизу вверх | BUY — начало бычьего тренда |
| EMA(9) пересекает EMA(21) сверху вниз | SELL — начало медвежьего тренда |
| EMA(9) > EMA(21) | Бычий тренд активен |
| EMA(9) < EMA(21) | Медвежий тренд активен |

#### MACD (Moving Average Convergence/Divergence) — 12/26/9
Показывает взаимосвязь между двумя EMA. Второй по популярности индикатор после RSI.

| Событие | Сигнал |
|---|---|
| MACD пересекает Signal снизу вверх | BUY |
| MACD пересекает Signal сверху вниз | SELL |
| Гистограмма растёт в плюс | Усиление бычьего импульса |
| Гистограмма растёт в минус | Усиление медвежьего импульса |

Параметры: `fast_period=12, slow_period=26, signal_period=9`

#### Bollinger Bands — период 20, StdDev 2
Определяет волатильность и относительные уровни цены.

| Событие | Сигнал |
|---|---|
| Цена ≤ Нижней полосы | BUY — цена у нижней границы |
| Цена ≥ Верхней полосы | SELL — цена у верхней границы |
| Сжатие полос (squeeze) | Ожидается сильное движение |

Параметры: `period=20, std_dev=2.0`

#### Volume (Объём) — SMA 20
Объём подтверждает или опровергает сигнал.

| Условие | Значение |
|---|---|
| Текущий объём > 1.5x от среднего | Подтверждение сигнала |
| Объём падает при движении цены | Слабый сигнал, возможная ловушка |

---

### 3.3 Логика генерации сигналов

```
BUY сигнал:
  ✓ RSI < 35 (перепроданность)
  ✓ EMA(9) > EMA(21) или свежий golden cross (≤ 2 свечи назад)
  ✓ MACD гистограмма растёт или MACD пересёк Signal снизу вверх
  ✓ Цена ≤ BB Lower + 0.5% (у нижней полосы)
  ✓ Volume > 1.3x SMA(20)

SELL сигнал:
  ✓ RSI > 65 (перекупленность)
  ✓ EMA(9) < EMA(21) или свежий death cross (≤ 2 свечи назад)
  ✓ MACD гистограмма падает или MACD пересёк Signal сверху вниз
  ✓ Цена ≥ BB Upper - 0.5% (у верхней полосы)
  ✓ Volume > 1.3x SMA(20)

Порог активации:
  - STRONG signal:  4-5 условий ✓
  - MEDIUM signal:  3 условия ✓
  - WEAK signal:    1-2 условия (только лог, без уведомления)
```

### 3.4 Рекомендуемые таймфреймы

| Таймфрейм | Применение |
|---|---|
| `5m` | Скальпинг, краткосрочные входы |
| `15m` | Основной рабочий таймфрейм (рекомендован) |
| `1h` | Среднесрочные сделки, фильтр тренда |
| `4h` | Долгосрочные позиции |

> Стратегия Multi-Timeframe: получить тренд на 1h, войти на 15m.

---

## 4. Архитектура системы

```
TradeExtension/
├── src/
│   ├── main.py                    # Точка входа, главный цикл
│   ├── config.py                  # Конфигурация из .env
│   ├── api/
│   │   ├── rest_client.py         # HTTP клиент Dzengi REST API
│   │   └── ws_client.py           # WebSocket клиент Dzengi
│   ├── indicators/
│   │   ├── rsi.py                 # RSI(14)
│   │   ├── ema.py                 # EMA(9), EMA(21)
│   │   ├── macd.py                # MACD(12,26,9)
│   │   ├── bollinger.py           # Bollinger Bands(20,2)
│   │   └── volume.py              # Volume SMA(20)
│   ├── strategy/
│   │   └── signal_engine.py       # Логика совмещения индикаторов
│   └── notifications/
│       ├── desktop.py             # Системные уведомления
│       └── telegram.py            # Telegram bot уведомления
├── tests/
│   ├── test_indicators.py
│   └── test_strategy.py
├── requirements.txt
├── .env.example
└── .gitignore
```

### 4.1 Поток данных

```
WebSocket (real-time OHLCV)
         │
         ▼
   CandleBuffer (скользящее окно 200 свечей)
         │
         ▼
   IndicatorEngine
   ┌─────┬─────┬──────┬──────┬────────┐
   RSI  EMA  MACD  BB  Volume
   └─────┴─────┴──────┴──────┴────────┘
         │
         ▼
   SignalEngine (confluence check)
         │
   ┌─────┴─────┐
   │           │
 STRONG/     WEAK
 MEDIUM      (лог)
   │
   ▼
NotificationManager
   ├── Desktop notification
   └── Telegram message
```

---

## 5. Конфигурация (.env)

```env
# Dzengi API
DZENGI_API_KEY=your_api_key_here
DZENGI_SECRET_KEY=your_secret_key_here
DZENGI_ENV=demo                        # demo | live

# Торговые настройки
SYMBOLS=BTCUSDT,ETHUSDT,XRPUSDT       # Список символов для мониторинга
TIMEFRAME=15m                          # Основной таймфрейм
MIN_SIGNALS=3                          # Минимум совпадений для уведомления

# Индикаторы
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
EMA_FAST=9
EMA_SLOW=21
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
BB_PERIOD=20
BB_STD_DEV=2.0
VOLUME_PERIOD=20
VOLUME_MULTIPLIER=1.3

# Уведомления
NOTIFICATION_MODE=desktop              # desktop | telegram | both
TELEGRAM_BOT_TOKEN=                    # Опционально
TELEGRAM_CHAT_ID=                      # Опционально

# Логирование
LOG_LEVEL=INFO
LOG_FILE=logs/trading.log
```

---

## 6. Формат уведомления

```
🟢 BUY SIGNAL — BTCUSDT [15m]
━━━━━━━━━━━━━━━━━━━━━━━━
Цена:     $43,250.00
Сила:     STRONG (4/5)
━━━━━━━━━━━━━━━━━━━━━━━━
✅ RSI(14) = 28.4 — перепроданность
✅ EMA Cross — golden cross 1 свечу назад
✅ MACD — пересечение вверх
✅ Volume — 2.1x от среднего
⬜ Bollinger — не у нижней полосы
━━━━━━━━━━━━━━━━━━━━━━━━
Время:    2024-01-15 14:30:00 UTC
```

---

## 7. Стек технологий

| Компонент | Библиотека |
|---|---|
| HTTP клиент | `aiohttp` |
| WebSocket | `websockets` |
| Технический анализ | `pandas`, `numpy` |
| Конфигурация | `python-dotenv` |
| Desktop уведомления | `plyer` |
| Telegram | `python-telegram-bot` |
| Логирование | `logging` (stdlib) |
| Тесты | `pytest`, `pytest-asyncio` |

---

## 8. Этапы разработки

| Этап | Задача | Приоритет |
|---|---|---|
| 1 | REST API клиент + получение исторических свечей | HIGH |
| 2 | Расчёт всех 5 индикаторов | HIGH |
| 3 | Signal Engine (логика совмещения) | HIGH |
| 4 | WebSocket клиент (real-time данные) | HIGH |
| 5 | Desktop уведомления | MEDIUM |
| 6 | Telegram уведомления | MEDIUM |
| 7 | Мониторинг нескольких символов | MEDIUM |
| 8 | Тесты | MEDIUM |

---

## 9. Ограничения и важные замечания

- **Demo vs Live:** Demo поддерживает только API v1. Все URL настраиваются через `DZENGI_ENV=demo`.
- **Rate Limits:** Dzengi использует weight-based rate limiting (аналогично Binance). Публичные эндпоинты — 1200 weight/min.
- **Не является торговым ботом:** Система только уведомляет. Сделки совершает пользователь вручную.
- **Работа с WebSocket:** Необходим ping каждые 20 секунд (лимит сервера — 30 сек).
- **Исторические данные для инициализации:** При старте загружается 200 свечей через REST для корректного расчёта индикаторов, затем переключается на WebSocket.

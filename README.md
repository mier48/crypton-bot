# Crypton Bot 🚀🤖

[![Version: 2.1.0](https://img.shields.io/badge/Version-2.1.0-blue.svg)](./README.md)  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Crypton Bot** es un bot de trading de criptomonedas totalmente automatizado que combina análisis técnico, machine learning y AI para optimizar decisiones de compra y venta.

---

## ⚙️ Características Principales

- **📈 Análisis Técnico Avanzado**: RSI, MACD, Bollinger Bands, ADX y más para evaluar tendencias.
- **🔍 Detección de Burbujas**: Módulo `BubbleDetector` evita compras en activos con subidas anómalas.
- **🔄 Adaptador de Estrategias Dinámicas**: Selecciona Trend Following, Mean Reversion, Breakout o Scalping según régimen de mercado.
- **⚖️ Dimensión Proporcional al Riesgo**: `InvestmentCalculator` ajusta porcentaje de inversión según puntuación de confianza.
- **🔔 Notificaciones Multi-Canal**: Telegram (ampliable a WhatsApp, Email…) con mensajes enriquecidos.
- **🛑 Trailing Stop-Loss Dinámico**: Captura beneficios máximos y ajusta stop loss automáticamente.
- **🤖 AI y Sentiment Analysis**: OpenAI y análisis de noticias/redes para decisiones informadas.
- **🔗 Múltiples APIs**: Binance, CoinGecko, NewsAPI, Reddit, etc.

---

## 🏗️ Arquitectura del Proyecto

```
src/
├── app/
│   ├── analyzers/            # MarketAnalyzer, SentimentAnalyzer, BubbleDetector, PreTradeAnalyzer
│   ├── executors/            # TradeExecutor (envío de órdenes)
│   ├── managers/             # BuyManager, SellManager, TradeManager
│   ├── notifiers/            # TelegramNotifier (y futuros servicios)
│   └── services/             # PriceCalculator, QuantityCalculator, SellDecisionEngine, StrategyAdapter, InvestmentCalculator
├── api/                      # Integraciones con Binance, CoinGecko, OpenAI, News
├── config/                   # Ajustes y parámetros (default.py, container.py, telegram.py)
├── utils/                    # Logger, helpers
└── main.py                   # Punto de entrada
```

---

## 📌 Tecnologías

- **Python** 🐍
- **Librerías**: pandas, numpy, requests, prettytable
- **AI & NLP**: OpenAI API, TextBlob

---

## 🚀 Instalación y Ejecución

```bash
git clone https://github.com/yourusername/crypton-bot.git
cd crypton-bot
pip install -r requirements.txt
cp .env.example .env  # configurar claves y settings
python src/main.py
```

---

## ⚙️ Configuración de Estrategias y Parámetros

En `config/default.py`:
```python
BUBBLE_DETECT_WINDOW = 12       # Velas para medir crecimiento
BUBBLE_MAX_GROWTH = 5.0         # % máximo permitido en ese window
DEFAULT_PROFIT_MARGIN = 1.5     # % objetivo de ganancia
DEFAULT_STOP_LOSS_MARGIN = 2.0  # % stop-loss
DEFAULT_INvestMENT_AMOUNT = 50  # USDC por trade
DEFAULT_SLEEP_INTERVAL = 60     # segundos entre ciclos
```
Y en `config/settings.py` o `.env`:
- Ajusta `PROFIT_MARGIN`, `STOP_LOSS_MARGIN`, `MIN_TRADE_USD`, etc.

---

## 📢 Notificaciones de Trading

Ejemplo de mensaje en Telegram:
```
🟢 *PROFIT TARGET REACHED* _(at 2025-04-26 00:23:00)_
*Asset:* `BTCUSDC`
*Side:* `SELL`
*Quantity:* `0.0050`
*Price:* `$45,200.1234`
*Total:* `$226.00`
*Balance:* `$774.00`
🟢 *P&L:* `+2.00%`
🔔 _Automatically generated notification_
```

---

## 🛠️ Contribuciones

¡Contribuciones bienvenidas!:
1. Haz un fork
2. Crea rama (`git checkout -b feature/x`)
3. Envía PR

---

## 📜 Licencia

MIT © **Alberto Mier**

---

## 📧 Contacto

Alberto Mier – [info@albertomier.com](mailto:info@albertomier.com)
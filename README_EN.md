# Crypton Bot 🚀🤖

[![Version: 2.1.0](https://img.shields.io/badge/Version-2.1.0-blue.svg)](./README_EN.md)  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Crypton Bot** is a fully automated cryptocurrency trading bot combining technical analysis, machine learning, and AI to optimize buy and sell decisions.

---

## ⚙️ Key Features

- **📈 Advanced Technical Analysis**: Indicators like RSI, MACD, Bollinger Bands, ADX to assess market trends.
- **🔍 Bubble Detection**: `BubbleDetector` module avoids buys during abnormal price surges.
- **🔄 Dynamic Strategy Adapter**: Chooses Trend Following, Mean Reversion, Breakout, or Scalping based on market regime.
- **⚖️ Risk-Proportional Investment**: `InvestmentCalculator` adjusts position size according to confidence score.
- **🔔 Multi-Channel Notifications**: Telegram (extendable to WhatsApp, Email…) with rich messages.
- **🛑 Dynamic Trailing Stop-Loss**: Captures peak gains and adjusts stop-loss automatically.
- **🤖 AI & Sentiment Analysis**: OpenAI and news/social data feed for informed decisions.
- **🔗 Multiple API Integrations**: Binance, CoinGecko, NewsAPI, Reddit, etc.

---

## 🏗️ Project Architecture

```
src/
├── app/
│   ├── analyzers/            # MarketAnalyzer, SentimentAnalyzer, BubbleDetector, PreTradeAnalyzer
│   ├── executors/            # TradeExecutor (order execution)
│   ├── managers/             # BuyManager, SellManager, TradeManager
│   ├── notifiers/            # TelegramNotifier (and future channels)
│   └── services/             # PriceCalculator, QuantityCalculator, SellDecisionEngine, StrategyAdapter, InvestmentCalculator
├── api/                      # Integrations: Binance, CoinGecko, OpenAI, News
├── config/                   # Settings (default.py, container.py, telegram.py)
├── utils/                    # Logger, helpers
└── main.py                   # Entry point
```

---

## 📌 Technologies

- **Python** 🐍
- **Libraries**: pandas, numpy, requests, prettytable
- **AI & NLP**: OpenAI API, TextBlob

---

## 🚀 Installation & Usage

```bash
git clone https://github.com/yourusername/crypton-bot.git
cd crypton-bot
pip install -r requirements.txt
cp .env.example .env  # configure API keys and settings
python src/main.py
```

---

## ⚙️ Strategy & Parameter Configuration

Edit `config/default.py`:
```python
BUBBLE_DETECT_WINDOW = 12       # Candles for growth window
BUBBLE_MAX_GROWTH = 5.0         # Max % allowed in window
DEFAULT_PROFIT_MARGIN = 1.5     # % profit target
DEFAULT_STOP_LOSS_MARGIN = 2.0  # % stop-loss
DEFAULT_INVESTMENT_AMOUNT = 50  # USDC per trade
DEFAULT_SLEEP_INTERVAL = 60     # seconds between cycles
```
And override in `config/settings.py` or `.env`:
- `PROFIT_MARGIN`, `STOP_LOSS_MARGIN`, `MIN_TRADE_USD`, etc.

---

## 📢 Trade Notifications

Example Telegram message:
```
🟢 *PROFIT TARGET REACHED* _(at 2025-04-26 00:25:00)_
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

## 🛠️ Contributing

Contributions are welcome!:
1. Fork the repo
2. Create a branch (`git checkout -b feature/your-feature`)
3. Submit a pull request

---

## 📜 License

MIT © **Alberto Mier**

---

## 📧 Contact

Alberto Mier – [info@albertomier.com](mailto:info@albertomier.com)

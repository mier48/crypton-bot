# Crypton Bot 🚀🤖

[![Version: 2.0.0-beta](https://img.shields.io/badge/Version-2.0.0--beta-blue.svg)](./README.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Crypton Bot** is an automated trading bot designed to operate with cryptocurrencies across multiple exchanges. It leverages advanced trading strategies based on technical analysis, artificial intelligence, and natural language processing to optimize buying and selling decisions.

---

## ⚙️ Key Features

- **📈 Advanced Technical Analysis**: Utilizes indicators such as RSI, MACD, Bollinger Bands, and ADX to assess market trends.
- **🧠 Artificial Intelligence**: Implements machine learning models (RNN, LSTM) for price predictions and sentiment analysis with OpenAI.
- **🔄 Full Automation**: Executes buy and sell orders automatically based on market analysis and user-defined settings.
- **💬 Real-Time Notifications**: Telegram integration for instant alerts on executed trades.
- **📊 Portfolio Management**: Tracks real-time asset performance, executed trades, and profitability.
- **🔗 Multiple Data Sources**: Gathers market data from Binance, CoinGecko, Reddit, and NewsAPI for comprehensive analysis.
- **🛡️ Security & Compliance**: Secure authentication, encrypted API key management, and regulatory compliance with KYC/AML.

---

## 🏗️ Project Architecture

```
📂 src/
 ├── 📁 app/                    # Core bot logic
 │   ├── 📁 analyzers/          # Market and sentiment analysis modules
 │   ├── 📁 executors/          # Order execution modules
 │   ├── 📁 managers/           # Buy and sell strategy management
 │   ├── notifier.py            # Notifications and alerts
 │   ├── validator.py           # Order and asset validation
 │
 ├── 📁 api/                    # Connectors for Binance, OpenAI, CoinGecko, etc.
 │   ├── 📁 binance/            # Binance API integration
 │   ├── 📁 coingecko/          # CoinGecko API integration
 │   ├── 📁 news/               # News and social media data sources
 │
 ├── 📁 config/                 # Bot configuration
 │   ├── default.py             # Default settings
 │   ├── telegram.py            # Telegram configuration
 │
 ├── 📁 utils/                  # General utilities
 │   ├── logger.py              # Logging system
 │ 
 ├── main.py                    # Bot entry point
```

---

## 📌 Technologies Used

- **Language**: Python 🐍
- **Frameworks & Libraries**:
  - `Pandas`, `NumPy` for data analysis.
  - `TextBlob`, `OpenAI API` for sentiment analysis.

---

## 🚀 Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yourusername/crypton-bot.git
cd crypton-bot
```

### 2️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Configure Environment Variables
Copy the provided `.env.example` file and rename it to `.env`:
```bash
cp .env.example .env
```
Then, edit the `.env` file and replace the placeholder values with your actual API credentials.

### 4️⃣ Run the Bot
```bash
python src/main.py
```

---

## 📊 Strategy Configuration

The bot allows strategy customization via `config/default.py`:

```
DEFAULT_PROFIT_MARGIN = 1.5  # Profit margin in %
DEFAULT_STOP_LOSS_MARGIN = 2.0  # Stop loss in %
DEFAULT_INVESTMENT_AMOUNT = 50  # Investment per trade in USDT
DEFAULT_SLEEP_INTERVAL = 60  # Interval between executions (seconds)
```

You can also adjust trading strategies in:
- `app/analyzers/market_analyzer.py` (Technical analysis)
- `app/analyzers/pre_trade_analyzer.py` (Market conditions analysis)
- `app/analyzers/sentiment_analyzer.py` (Sentiment analysis)

---

## 📢 Trading Notifications

The bot sends real-time alerts via Telegram when trades are executed.

Example notification:
```
🟢 TRADE EXECUTED
🔹 Asset: BTCUSDT
🔹 Quantity: 0.002 BTC
🔹 Price: $45,000.00
💵 Balance: $500.00
📅 Date & Time: 2025-02-25 14:30:00
```

To enable notifications, configure the settings in `config/telegram.py` and `.env`.

---

## 🛠️ Contributing

Contributions are welcome! 🛠️ If you'd like to improve this project:
1. **Fork** this repository.
2. **Create a new branch** (`git checkout -b feature-new-feature`).
3. **Make changes and submit a PR**.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 📧 Contact

Developed by **Alberto Mier**.  
For inquiries, contact me at: [info@albertomier.com](mailto:info@albertomier.com)
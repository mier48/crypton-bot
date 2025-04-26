import argparse
from datetime import datetime, timedelta
import pandas as pd
import backtrader as bt

from api.binance.data_manager import BinanceDataManager
from app.backtest.strategy import CryptoStrategy


def fetch_data(symbol: str, months: int, interval: str) -> pd.DataFrame:
    """
    Descarga datos históricos de Binance y convierte a DataFrame.
    """
    end = datetime.utcnow()
    start = end - timedelta(days=30 * months)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)

    dm = BinanceDataManager()
    klines = dm.fetch_historical_data(symbol, start_ms, end_ms, interval=interval)

    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['datetime'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('datetime', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df


def main():
    parser = argparse.ArgumentParser(description='Backtest trading strategy')
    parser.add_argument('--symbol', default='BTCUSDC', help='Símbolo (e.g. BTCUSDC)')
    parser.add_argument('--months', type=int, default=3, help='Meses de histórico')
    parser.add_argument('--interval', default='1h', help='Intervalo de datos')
    args = parser.parse_args()

    data = fetch_data(args.symbol, args.months, args.interval)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    feed = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(feed, name=args.symbol)
    cerebro.addstrategy(
        CryptoStrategy,
        symbol=args.symbol,
        from_date=datetime.utcnow() - timedelta(days=30 * args.months),
        to_date=datetime.utcnow(),
        interval=args.interval
    )

    print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f} USDC")
    cerebro.run()
    print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f} USDC")


if __name__ == '__main__':
    main()

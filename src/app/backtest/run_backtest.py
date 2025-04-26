import argparse
from datetime import datetime, timedelta, timezone
import pandas as pd
import backtrader as bt

from api.binance.data_manager import BinanceDataManager
from app.optimization.parameter_optimizer import ParameterOptimizer
from app.monitoring.overfitting_detector import OverfittingDetector
from app.monitoring.anomaly_detector import AnomalyDetector
from app.backtest.strategy import CryptoStrategy
from config.settings import settings


def fetch_data(symbol: str, months: int, interval: str) -> pd.DataFrame:
    """
    Descarga datos históricos de Binance y convierte a DataFrame.
    """
    end = datetime.now(timezone.utc)
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
    parser.add_argument('--optimize', action='store_true', help='Run Bayesian optimization')
    parser.add_argument('--symbol', default='BTCUSDC', help='Símbolo (e.g. BTCUSDC)')
    parser.add_argument('--months', type=int, default=3, help='Meses de histórico')
    parser.add_argument('--interval', default='1h', help='Intervalo de datos')
    args = parser.parse_args()

    data = fetch_data(args.symbol, args.months, args.interval)

    # Optimization flow
    if args.optimize:
        # Define parameter space for optimization (example)
        param_space = settings.OPTUNA_PARAM_SPACE
        def objective_fn(params):
            cerebro_opt = bt.Cerebro()
            cerebro_opt.broker.setcash(10000.0)
            cerebro_opt.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)
            feed = bt.feeds.PandasData(dataname=data)
            cerebro_opt.adddata(feed, name=args.symbol)
            cerebro_opt.addstrategy(CryptoStrategy, symbol=args.symbol, **params)
            results = cerebro_opt.run()
            returns = results[0].analyzers.timereturn.get_analysis()
            # maximize final portfolio value
            return cerebro_opt.broker.getvalue()
        optimizer = ParameterOptimizer(n_trials=settings.OPTUNA_TRIALS)
        best = optimizer.optimize(param_space, objective_fn)
        print('Best parameters:', best)
        return
    # Backtest train/test and detect overfitting
    split = int(len(data) * 0.7)
    train, test = data.iloc[:split], data.iloc[split:]
    def run_strategy(df):
        cerebro_run = bt.Cerebro()
        cerebro_run.broker.setcash(10000.0)
        cerebro_run.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)
        feed = bt.feeds.PandasData(dataname=df)
        cerebro_run.adddata(feed, name=args.symbol)
        cerebro_run.addstrategy(CryptoStrategy, symbol=args.symbol,
                                 from_date=settings.BACKTEST_START,
                                 to_date=settings.BACKTEST_END,
                                 interval=args.interval)
        results = cerebro_run.run()
        tr = results[0].analyzers.timereturn.get_analysis()
        return pd.Series(tr)
    train_returns = run_strategy(train)
    test_returns = run_strategy(test)
    of_detector = OverfittingDetector(threshold=settings.OVERFITTING_THRESHOLD)
    if of_detector.is_overfitting(train_returns, test_returns):
        print('Overfitting detected: train-test performance gap exceeds threshold')
        return
    # Run full backtest and detect anomalies
    full_returns = run_strategy(data)
    ad = AnomalyDetector(contamination=settings.ANOMALY_CONTAMINATION)
    ad.fit(train_returns.to_frame(name='ret'))
    anomalies = ad.detect(full_returns.to_frame(name='ret'))
    if anomalies.any():
        print('Anomalous periods detected on:', anomalies[anomalies].index.tolist())
    # Final full backtest
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(10000.0)
    feed = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(feed, name=args.symbol)
    cerebro.addstrategy(CryptoStrategy, symbol=args.symbol,
                         from_date=settings.BACKTEST_START,
                         to_date=settings.BACKTEST_END,
                         interval=args.interval)
    print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f} USDC")
    cerebro.run()
    print(f"Final Portfolio Value: {cerebro.broker.getvalue():.2f} USDC")


if __name__ == '__main__':
    main()

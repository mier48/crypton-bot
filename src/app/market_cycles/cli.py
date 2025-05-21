import argparse
import json
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from tabulate import tabulate
import time
import os
import sys

from src.api.binance.data_manager import BinanceDataManager
from src.app.market_cycles.detector import MarketCycleDetector, MarketCycle
from src.app.market_cycles.integrator import MarketCycleIntegrator
from src.app.market_cycles.strategy_manager import AdaptiveStrategyManager
from src.config.settings import settings
from loguru import logger


def print_color(text, color='white'):
    """Imprime texto con color en la terminal."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'bold': '\033[1m',
        'end': '\033[0m'
    }
    print(f"{colors.get(color, '')}{text}{colors['end']}")


def show_market_cycle(manager):
    """Muestra información detallada sobre el ciclo de mercado actual."""
    # Forzar actualización del ciclo
    manager.update_market_state(force=True)
    
    # Obtener información detallada
    cycle_info = manager.get_current_cycle_info()
    
    # Colores para diferentes ciclos
    cycle_colors = {
        'accumulation': 'blue',
        'uptrend': 'green',
        'distribution': 'yellow',
        'downtrend': 'red',
        'unknown': 'white'
    }
    
    # Mostrar información principal
    cycle_color = cycle_colors.get(cycle_info['cycle'], 'white')
    print("\n" + "=" * 80)
    print_color(f"CICLO DE MERCADO ACTUAL: {cycle_info['cycle'].upper()}", color=cycle_color)
    print_color(f"Confianza: {cycle_info['confidence']:.2f}", color=cycle_color)
    print_color(f"Última actualización: {cycle_info['last_updated']}", color='white')
    print("=" * 80)
    
    # Mostrar descripción
    print("\nDESCRIPCIÓN:")
    print(cycle_info['description'])
    
    # Mostrar recomendaciones
    print("\nRECOMENDACIONES:")
    print(cycle_info['recommendations'])
    
    # Mostrar métricas clave
    print("\nMÉTRICAS CLAVE:")
    metrics = cycle_info.get('metrics', {})
    if metrics:
        metrics_table = [
            ["Métrica", "Valor"],
            ["Precio BTC", f"${metrics.get('price', 0):.2f}"],
            ["% desde máximo", f"{metrics.get('pct_from_high', 0)*100:.2f}%"],
            ["% desde mínimo", f"{metrics.get('pct_from_low', 0)*100:.2f}%"],
            ["Volatilidad", f"{metrics.get('volatility', 0)*100:.2f}%"],
            ["Tendencia volumen", f"{metrics.get('volume_trend', 0)*100:.2f}%"]
        ]
        print(tabulate(metrics_table, headers="firstrow", tablefmt="grid"))
    
    # Mostrar historial reciente de ciclos
    print("\nHISTORIAL RECIENTE DE CICLOS:")
    history = cycle_info.get('history', [])
    if history:
        history_table = [["Fecha", "Ciclo", "Confianza", "Duración (días)"]]
        for entry in history[-5:]:  # Mostrar los últimos 5 ciclos
            history_table.append([
                entry.get('timestamp', '').split('T')[0],
                entry.get('cycle', '').value,
                f"{entry.get('confidence', 0):.2f}",
                entry.get('duration_days', 0)
            ])
        print(tabulate(history_table, headers="firstrow", tablefmt="grid"))
    
    # Mostrar parámetros adaptados
    print("\nPARÁMETROS ADAPTADOS:")
    adaptations = manager.current_adaptations
    if adaptations:
        # Portfolio adaptations
        portfolio = adaptations.get('portfolio', {})
        if portfolio:
            print_color("\nPortfolio:", color='cyan')
            for k, v in portfolio.items():
                if k != 'recommendations':
                    print(f"  - {k}: {v}")
        
        # Buy manager adaptations
        buy = adaptations.get('buy_manager', {})
        if buy:
            print_color("\nCompras:", color='green')
            for k, v in buy.items():
                print(f"  - {k}: {v}")
        
        # Sell manager adaptations
        sell = adaptations.get('sell_manager', {})
        if sell:
            print_color("\nVentas:", color='yellow')
            for k, v in sell.items():
                print(f"  - {k}: {v}")
    
    print("\n" + "=" * 80)
    

def main():
    """Función principal de la CLI."""
    parser = argparse.ArgumentParser(description="Herramienta de análisis de ciclos de mercado")
    parser.add_argument('--action', type=str, default='status', 
                        choices=['status', 'monitor', 'analyze'],
                        help='Acción a realizar')
    parser.add_argument('--days', type=int, default=90, 
                        help='Número de días de datos históricos')
    parser.add_argument('--interval', type=str, default='1d',
                        help='Intervalo de los datos (ej: 1h, 4h, 1d)')
    
    args = parser.parse_args()
    
    # Inicializar componentes
    data_manager = BinanceDataManager()
    strategy_manager = AdaptiveStrategyManager(data_manager)
    
    if args.action == 'status':
        # Mostrar información sobre el ciclo actual
        show_market_cycle(strategy_manager)
        
    elif args.action == 'monitor':
        # Monitorear ciclo en tiempo real
        print_color("Monitor de ciclo de mercado - Presiona Ctrl+C para salir", color='cyan')
        try:
            while True:
                show_market_cycle(strategy_manager)
                print("\nActualizando en 60 segundos...")
                time.sleep(60)
        except KeyboardInterrupt:
            print_color("\nMonitor finalizado.", color='yellow')
            
    elif args.action == 'analyze':
        # Análisis detallado con visualizaciones
        print_color("Realizando análisis detallado del mercado...", color='cyan')
        
        # Obtener datos
        btc_klines = data_manager.get_historical_klines(
            symbol="BTCUSDT",
            interval=args.interval,
            limit=args.days
        )
        
        if not btc_klines or len(btc_klines) < 20:
            print_color("Error: No se pudieron obtener suficientes datos.", color='red')
            return
            
        # Convertir a DataFrame
        btc_df = pd.DataFrame(btc_klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignored'
        ])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            btc_df[col] = btc_df[col].astype(float)
            
        # Convertir timestamps a fechas
        btc_df['date'] = pd.to_datetime(btc_df['open_time'], unit='ms')
        
        # Calcular indicadores básicos
        btc_df['sma20'] = btc_df['close'].rolling(window=20).mean()
        btc_df['sma50'] = btc_df['close'].rolling(window=50).mean()
        btc_df['returns'] = btc_df['close'].pct_change()
        btc_df['volatility'] = btc_df['returns'].rolling(window=14).std()
        
        # Mostrar estadísticas
        print("\nESTADÍSTICAS DEL MERCADO:")
        stats_table = [
            ["Métrica", "Valor"],
            ["Precio actual", f"${btc_df['close'].iloc[-1]:.2f}"],
            ["Cambio 7 días", f"{btc_df['close'].iloc[-1]/btc_df['close'].iloc[-7]-1:.2%}"],
            ["Cambio 30 días", f"{btc_df['close'].iloc[-1]/btc_df['close'].iloc[-30]-1:.2%}"],
            ["Máximo (periodo)", f"${btc_df['high'].max():.2f}"],
            ["Mínimo (periodo)", f"${btc_df['low'].min():.2f}"],
            ["Volatilidad (14d)", f"{btc_df['volatility'].iloc[-1]*100:.2f}%"],
            ["Volumen promedio", f"${btc_df['volume'].mean():.2f}"]
        ]
        print(tabulate(stats_table, headers="firstrow", tablefmt="grid"))
        
        # Mostrar ciclo actual y recomendaciones
        show_market_cycle(strategy_manager)
        
        # Generar y guardar gráfico
        try:
            plt.figure(figsize=(12, 8))
            plt.subplot(2, 1, 1)
            plt.plot(btc_df['date'], btc_df['close'], label='BTC/USDT')
            plt.plot(btc_df['date'], btc_df['sma20'], label='SMA 20', linestyle='--')
            plt.plot(btc_df['date'], btc_df['sma50'], label='SMA 50', linestyle='-.')
            plt.title('BTC/USDT - Precio y Medias Móviles')
            plt.ylabel('Precio (USDT)')
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            plt.subplot(2, 1, 2)
            plt.bar(btc_df['date'], btc_df['volume'], label='Volumen', alpha=0.7)
            plt.title('Volumen de Trading')
            plt.ylabel('Volumen')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            # Guardar gráfico
            plt.savefig('market_analysis.png')
            print_color("\nGráfico guardado como 'market_analysis.png'", color='green')
        except Exception as e:
            print_color(f"No se pudo generar el gráfico: {e}", color='red')
    
    print("\nAnálisis completado.")

if __name__ == "__main__":
    main()

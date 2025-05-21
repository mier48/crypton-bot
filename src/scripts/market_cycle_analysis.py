#!/usr/bin/env python3
"""
Analizador de ciclos de mercado para Crypton Bot

Este script permite visualizar el ciclo de mercado actual, las recomendaciones
y las adaptaciones que se estu00e1n aplicando a la estrategia.
"""

import sys
import os
import argparse
import json
from datetime import datetime
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd
import time

# Agregar la ruta del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.api.binance.data_manager import BinanceDataManager
from src.app.managers.risk_manager import RiskManager
from src.app.market_cycles.detector import MarketCycle
from loguru import logger

# Configurar logger
logger.remove()
logger.add(sys.stderr, level=settings.LOG_LEVEL)


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


def show_cycle_info(risk_manager):
    """Muestra informaciu00f3n sobre el ciclo de mercado actual y adaptaciones."""
    cycle_info = risk_manager.get_market_cycle_info()
    
    if not cycle_info.get('enabled', False):
        print_color("Sistema de adaptación a ciclos de mercado DESACTIVADO", color='yellow')
        print(f"Razón: {cycle_info.get('message', 'No disponible')}")
        return
        
    if 'error' in cycle_info:
        print_color(f"Error al obtener información del ciclo: {cycle_info['error']}", color='red')
        return
        
    # Extraer información del ciclo
    cycle_data = cycle_info.get('cycle', {})
    adaptations = cycle_info.get('adaptations', {})
    
    # Colores para diferentes ciclos
    cycle_colors = {
        'accumulation': 'blue',
        'uptrend': 'green',
        'distribution': 'yellow',
        'downtrend': 'red',
        'unknown': 'white'
    }
    
    # Mostrar información principal
    current_cycle = cycle_data.get('cycle', 'unknown')
    cycle_color = cycle_colors.get(current_cycle, 'white')
    print("\n" + "=" * 80)
    print_color(f"CICLO DE MERCADO ACTUAL: {current_cycle.upper()}", color=cycle_color)
    print_color(f"Confianza: {cycle_data.get('confidence', 0):.2f}", color=cycle_color)
    print_color(f"Última actualización: {cycle_data.get('last_updated', 'N/A')}", color='white')
    print("=" * 80)
    
    # Mostrar descripción
    print("\nDESCRIPCIÓN:")
    print(cycle_data.get('description', 'No disponible'))
    
    # Mostrar recomendaciones
    print("\nRECOMENDACIONES:")
    print(cycle_data.get('recommendations', 'No disponible'))
    
    # Mostrar métricas clave
    print("\nMÉTRICAS CLAVE:")
    metrics = cycle_data.get('metrics', {})
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
    history = cycle_data.get('history', [])
    if history:
        history_table = [["Fecha", "Ciclo", "Confianza", "Duración (días)"]]
        for entry in history[-5:]:  # Mostrar los últimos 5 ciclos
            history_table.append([
                entry.get('timestamp', '').split('T')[0],
                entry.get('cycle', ''),
                f"{entry.get('confidence', 0):.2f}",
                entry.get('duration_days', 0)
            ])
        print(tabulate(history_table, headers="firstrow", tablefmt="grid"))
    
    # Mostrar parámetros adaptados
    print("\nPARÁMETROS ADAPTADOS:")
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


def generate_market_analysis(data_manager, risk_manager, days=90):
    """Genera un análisis gráfico del mercado y ciclos."""
    print_color("Generando análisis de mercado...", color='cyan')
    
    # Obtener datos históricos de BTC
    btc_klines = data_manager.get_historical_klines(
        symbol="BTCUSDT",
        interval="1d",
        limit=days
    )
    
    if not btc_klines or len(btc_klines) < 20:
        print_color("Error: No se pudieron obtener suficientes datos históricos.", color='red')
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
    
    # Generar gráfico
    try:
        plt.figure(figsize=(12, 8))
        
        # Obtener información del ciclo actual
        cycle_info = risk_manager.get_market_cycle_info()
        cycle_data = cycle_info.get('cycle', {})
        current_cycle = cycle_data.get('cycle', 'unknown')
        
        # Subgráfico de precios
        plt.subplot(2, 1, 1)
        plt.plot(btc_df['date'], btc_df['close'], label='BTC/USDT')
        plt.plot(btc_df['date'], btc_df['sma20'], label='SMA 20', linestyle='--')
        plt.plot(btc_df['date'], btc_df['sma50'], label='SMA 50', linestyle='-.')
        
        # Colorear según el ciclo actual
        cycle_colors = {
            'accumulation': 'blue',
            'uptrend': 'green',
            'distribution': 'orange',
            'downtrend': 'red',
            'unknown': 'gray'
        }
        plt.title(f'BTC/USDT - Ciclo actual: {current_cycle.upper()}', 
                 color=cycle_colors.get(current_cycle, 'black'))
        plt.ylabel('Precio (USDT)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        # Subgráfico de volumen
        plt.subplot(2, 1, 2)
        plt.bar(btc_df['date'], btc_df['volume'], label='Volumen', alpha=0.7)
        plt.title('Volumen de Trading')
        plt.ylabel('Volumen')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Guardar gráfico
        filename = f'market_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        plt.savefig(filename)
        print_color(f"\nGráfico guardado como '{filename}'", color='green')
        
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
        
    except Exception as e:
        print_color(f"Error al generar gráfico: {e}", color='red')


def main():
    """
Función principal del analizador de ciclos.
    """
    parser = argparse.ArgumentParser(description="Analizador de ciclos de mercado para Crypton Bot")
    parser.add_argument('--action', type=str, default='status', 
                        choices=['status', 'monitor', 'analyze', 'simulate'],
                        help='Acción a realizar')
    parser.add_argument('--days', type=int, default=90, 
                        help='Número de días de datos históricos')
    parser.add_argument('--interval', type=int, default=60, 
                        help='Intervalo de actualización en segundos (solo para monitor)')
    parser.add_argument('--simulate-cycle', type=str, default=None,
                        choices=['accumulation', 'uptrend', 'distribution', 'downtrend'],
                        help='Simular un ciclo específico para pruebas')
    
    args = parser.parse_args()
    
    # Inicializar componentes
    data_manager = BinanceDataManager()
    risk_manager = RiskManager(data_manager, None)  # Sin executor por ahora
    
    if args.action == 'status':
        # Mostrar estado actual del ciclo
        print_color("===== ESTADO ACTUAL DEL CICLO DE MERCADO =====", color='bold')
        show_cycle_info(risk_manager)
    
    elif args.action == 'monitor':
        # Monitoreo continuo
        print_color("===== MONITOR DE CICLOS DE MERCADO =====\n", color='bold')
        print_color("Presiona Ctrl+C para salir", color='yellow')
        try:
            while True:
                show_cycle_info(risk_manager)
                print(f"\nActualizando en {args.interval} segundos...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print_color("\nMonitor finalizado", color='yellow')
    
    elif args.action == 'analyze':
        # Análisis detallado con gráficos
        print_color("===== ANÁLISIS DETALLADO DEL MERCADO =====\n", color='bold')
        show_cycle_info(risk_manager)
        generate_market_analysis(data_manager, risk_manager, days=args.days)
    
    elif args.action == 'simulate':
        # Simular un ciclo específico para pruebas
        if not args.simulate_cycle:
            print_color("Error: Debes especificar un ciclo con --simulate-cycle", color='red')
            return
            
        print_color(f"Simulando ciclo: {args.simulate_cycle.upper()}", color='cyan')
        # Esta simulación solo imprime lo que haría, no modifica realmente el sistema
        cycle_map = {
            'accumulation': 'ACCUMULATION',
            'uptrend': 'UPTREND',
            'distribution': 'DISTRIBUTION',
            'downtrend': 'DOWNTREND'
        }
        
        if risk_manager.strategy_manager and hasattr(risk_manager.strategy_manager.cycle_integrator, 'cycle_detector'):
            print("Ciclo actual antes de la simulación:")
            show_cycle_info(risk_manager)
            
            print("\nEjemplo de adaptaciones que se aplicarían en este ciclo:")
            print("---------------------------------------------------")
            print_color(f"PORTFOLIO:", color='cyan')
            print(f"- Risk Aversion: {0.5 if args.simulate_cycle == 'accumulation' else 0.3 if args.simulate_cycle == 'uptrend' else 0.7 if args.simulate_cycle == 'distribution' else 0.9}")
            print(f"- Max Allocation per Asset: {15 if args.simulate_cycle == 'accumulation' else 25 if args.simulate_cycle == 'uptrend' else 10 if args.simulate_cycle == 'distribution' else 5}%")
            print(f"- Cash Reserve: {20 if args.simulate_cycle == 'accumulation' else 10 if args.simulate_cycle == 'uptrend' else 40 if args.simulate_cycle == 'distribution' else 60}%")
            
            print_color(f"\nCOMPRAS:", color='green')
            print(f"- Investment Multiplier: {1.5 if args.simulate_cycle == 'accumulation' else 1.3 if args.simulate_cycle == 'uptrend' else 0.8 if args.simulate_cycle == 'distribution' else 0.5}")
            print(f"- Confidence Threshold: {60 if args.simulate_cycle == 'accumulation' else 70 if args.simulate_cycle == 'uptrend' else 80 if args.simulate_cycle == 'distribution' else 90}")
            
            print_color(f"\nVENTAS:", color='yellow')
            print(f"- Stop Loss Multiplier: {1.0 if args.simulate_cycle == 'accumulation' else 0.8 if args.simulate_cycle == 'uptrend' else 0.7 if args.simulate_cycle == 'distribution' else 0.5}")
            print(f"- Take Profit Multiplier: {1.2 if args.simulate_cycle == 'accumulation' else 1.5 if args.simulate_cycle == 'uptrend' else 1.0 if args.simulate_cycle == 'distribution' else 0.8}")
            
            # Nota: Esta es solo una simulación visual, no se cambia realmente el ciclo detectado
            print("\nNOTA: Esta es solo una simulación para visualizar las adaptaciones.")
            print("Para forzar un ciclo específico habría que modificar el código.")
        else:
            print_color("Error: El sistema de adaptación a ciclos no está activado o inicializado correctamente", color='red')


if __name__ == "__main__":
    main()

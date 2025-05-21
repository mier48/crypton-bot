from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np
from datetime import datetime
from src.api.binance.data_manager import BinanceDataManager
from src.app.portfolio.models.portfolio_state import PortfolioState
from src.app.portfolio.components.quantity_calculator import QuantityCalculator
from src.app.portfolio.adapters import BinanceDataProviderAdapter
from src.config.settings import settings
from loguru import logger

# Import database related components
from sqlalchemy.orm import Session
from src.config.database import SessionLocal
from src.models.asset import Asset
from src.utils.database_manager import DatabaseManager

class Rebalancer:
    """
    Componente responsable de ejecutar las operaciones de rebalanceo del portafolio.
    """
    
    def __init__(self, data_manager: BinanceDataManager, min_order_value: float = 10.0):
        """
        Inicializa el rebalanceador.
        
        Args:
            data_manager: Gestor de datos de Binance para ejecutar órdenes
            min_order_value: Valor mínimo en USDC para considerar una orden
        """
        self.data_manager = data_manager
        self.min_order_value = min_order_value
        
        # Crear adaptador para pasar al calculador de cantidades
        data_provider = BinanceDataProviderAdapter(data_manager)
        self.quantity_calculator = QuantityCalculator(data_provider=data_provider)
        
        # Configurar acceso a base de datos para verificar precios de compra
        self.min_profit_percentage = 0.01  # 1% de beneficio mínimo requerido
        self.db_session = SessionLocal()
        
        # Límites para operaciones
        self.min_asset_value = 1.0     # No hacer nada con activos de menos de $1
        self.min_buy_value = 5.0       # No comprar menos de $5 de un activo
    
    def calculate_rebalance_trades(self, state: PortfolioState) -> List[Dict[str, Any]]:
        """
        Calcula las operaciones necesarias para rebalancear el portafolio.
        
        Args:
            state: Estado del portafolio con asignaciones actuales y objetivo
            
        Returns:
            List[Dict[str, Any]]: Lista de operaciones a realizar
        """
        trades = []
        
        try:
            # Verificar si hay una asignación objetivo
            if not state.target_allocation:
                logger.warning("No se encontró asignación objetivo para rebalanceo")
                return []
                
            # Registro para diagnóstico
            logger.debug(f"Estado actual del portafolio para rebalanceo:\n" + 
                       f"  Total value: {state.total_value:.2f} USDC\n" + 
                       f"  USDC balance: {state.usdc_balance:.2f}\n" + 
                       f"  Activos: {len(state.current_assets)} símbolos\n" + 
                       f"  Asignación actual: {state.current_allocation}\n" + 
                       f"  Asignación objetivo: {state.target_allocation}")
            
            if not state.current_allocation or state.total_value <= 0:
                logger.warning("No hay suficiente información para calcular operaciones de rebalanceo")
                return trades
                
            # Calcular el valor objetivo para cada activo
            target_values = {}
            for symbol, target_weight in state.target_allocation.items():
                target_values[symbol] = state.total_value * target_weight
            
            # Calcular el valor actual de cada activo
            current_values = {}
            for symbol, allocation in state.current_allocation.items():
                current_values[symbol] = state.total_value * allocation
            
            # Identificar activos a vender (valor actual > valor objetivo)
            sells = []
            for symbol, current_value in current_values.items():
                if symbol == 'USDC':
                    continue  # No vendemos USDC directamente
                
                target_value = target_values.get(symbol, 0.0)
                if current_value > target_value:
                    # Determinar cuánto vender
                    value_to_sell = current_value - target_value
                    
                    # Log de diagnóstico
                    logger.debug(f"Evaluando venta de {symbol}: valor actual={current_value:.2f}, valor objetivo={target_value:.2f}, diferencia={value_to_sell:.2f} USDC")
                    
                    # Verificar si el activo tiene un valor muy pequeño (menos de $1)
                    if current_value < self.min_asset_value:
                        logger.info(f"Ignorando {symbol}: su valor actual (${current_value:.2f}) es menor al mínimo de ${self.min_asset_value:.2f}")
                        continue
                    
                    # Solo considerar ventas significativas
                    if value_to_sell >= self.min_order_value:
                        # Obtener precio actual
                        price = None
                        if symbol in state.current_assets:
                            price = state.current_assets[symbol]['current_price']
                        
                        if not price or price <= 0:
                            ticker = f"{symbol}USDC"
                            price = self.data_manager.get_price(ticker) or 0
                        
                        if price > 0:
                            # Verificar precio de compra para asegurar beneficio
                            should_sell = True
                            try:
                                # Crear sesión DB si no existe
                                if not self.db_session:
                                    self.db_session = SessionLocal()
                                    
                                # Consultar activo en la base de datos
                                db_manager = DatabaseManager(self.db_session)
                                asset = db_manager.get_asset_by_symbol(symbol)
                                
                                if asset:
                                    # Calcular porcentaje de beneficio
                                    purchase_price = asset.purchase_price
                                    profit_percentage = (price - purchase_price) / purchase_price
                                    
                                    # Solo vender si hay al menos 1% de beneficio
                                    if profit_percentage < self.min_profit_percentage:
                                        logger.info(f"No se venderá {symbol}: Precio actual ${price:.4f}, precio compra ${purchase_price:.4f}, beneficio {profit_percentage*100:.2f}% < {self.min_profit_percentage*100:.0f}%")
                                        should_sell = False
                                    else:
                                        logger.info(f"Se puede vender {symbol}: Precio actual ${price:.4f}, precio compra ${purchase_price:.4f}, beneficio {profit_percentage*100:.2f}% >= {self.min_profit_percentage*100:.0f}%")
                                else:
                                    logger.warning(f"No se encontró {symbol} en la base de datos para verificar precio de compra")
                            except Exception as e:
                                logger.error(f"Error verificando precio de compra para {symbol}: {e}")
                            
                            # Continuar solo si debemos vender
                            if not should_sell:
                                continue
                                
                            # Calcular cantidad a vender
                            quantity = value_to_sell / price
                            
                            # Redondear la cantidad según las reglas del mercado
                            quantity = self.quantity_calculator.calculate_sell_quantity(
                                symbol=symbol,
                                price=price,
                                usdc_amount=value_to_sell
                            )
                            
                            if quantity > 0:
                                sells.append({
                                    'symbol': f"{symbol}USDC",
                                    'type': 'SELL',
                                    'quantity': quantity,
                                    'price': price,
                                    'value': quantity * price
                                })
            
            # Calcular el total de USDC después de ventas
            usdc_after_sells = state.usdc_balance
            for sell in sells:
                usdc_after_sells += sell['value']
            
            # USDC disponible para compras = USDC actual + ventas - USDC objetivo
            usdc_target = target_values.get('USDC', 0.0)
            usdc_available = usdc_after_sells - usdc_target
            
            # Identificar activos a comprar (valor actual < valor objetivo)
            buys = []
            for symbol, target_value in target_values.items():
                if symbol == 'USDC':
                    continue  # No compramos USDC directamente
                
                current_value = current_values.get(symbol, 0.0)
                if current_value < target_value:
                    # Determinar cuánto comprar
                    value_to_buy = target_value - current_value
                    
                    # Log de diagnóstico
                    logger.debug(f"Evaluando compra de {symbol}: valor actual={current_value:.2f}, valor objetivo={target_value:.2f}, diferencia={value_to_buy:.2f} USDC, USDC disponible={usdc_available:.2f}")
                    
                    # No comprar menos del valor mínimo establecido ($5)
                    if value_to_buy < self.min_buy_value:
                        logger.info(f"No se comprará {symbol}: el valor a comprar (${value_to_buy:.2f}) es menor al mínimo de ${self.min_buy_value:.2f}")
                        continue
                    
                    # Solo considerar compras significativas y si hay USDC disponible
                    if value_to_buy >= self.min_order_value and usdc_available > 0:
                        # Limitar al USDC disponible
                        value_to_buy = min(value_to_buy, usdc_available)
                        
                        # Obtener precio actual
                        price = None
                        if symbol in state.current_assets:
                            price = state.current_assets[symbol]['current_price']
                        
                        if not price or price <= 0:
                            ticker = f"{symbol}USDC"
                            price = self.data_manager.get_price(ticker) or 0
                        
                        if price > 0:
                            # Calcular cantidad a comprar
                            quantity = self.quantity_calculator.calculate_buy_quantity(
                                symbol=symbol,
                                price=price,
                                usdc_amount=value_to_buy
                            )
                            
                            if quantity > 0:
                                buys.append({
                                    'symbol': f"{symbol}USDC",
                                    'type': 'BUY',
                                    'quantity': quantity,
                                    'price': price,
                                    'value': quantity * price
                                })
                                
                                # Actualizar USDC disponible
                                usdc_available -= (quantity * price)
            
            # Combinar ventas y compras
            trades = sells + buys
            logger.info(f"Planificadas {len(sells)} ventas y {len(buys)} compras para rebalanceo")
            
            return trades
            
        except Exception as e:
            logger.error(f"Error calculando operaciones de rebalanceo: {e}")
            return []
    
    def __del__(self):
        """
        Destructor para cerrar la sesión de base de datos cuando el objeto es eliminado.
        """
        try:
            if self.db_session:
                self.db_session.close()
        except Exception as e:
            logger.error(f"Error al cerrar la sesión de base de datos: {e}")
    
    def execute_rebalance(self, trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ejecuta las operaciones de rebalanceo en Binance.
        
        Este método aplica la protección contra ventas a pérdidas:  
        - Solo se venden activos con al menos 1% de beneficio respecto al precio de compra
        - El precio de compra se consulta desde la base de datos SQLite
        
        Args:
            trades: Lista de operaciones a realizar
            
        Returns:
            List[Dict[str, Any]]: Lista de operaciones ejecutadas con resultados
        """
        executed_trades = []
        
        # Primero ejecutar todas las ventas para asegurar liquidez
        sells = [t for t in trades if t['type'] == 'SELL']
        buys = [t for t in trades if t['type'] == 'BUY']
        
        # Ordenar operaciones: primero ventas, luego compras
        ordered_trades = sells + buys
        
        for trade in ordered_trades:
            try:
                symbol = trade['symbol']
                quantity = trade['quantity']
                operation = trade['type']
                
                # Ejecutar la operación usando el data_manager para crear órdenes
                try:
                    if operation == 'SELL':
                        result = self.data_manager.create_order(
                            symbol=symbol,
                            side='SELL',
                            type_='MARKET',
                            quantity=quantity
                        )
                    else:  # BUY
                        result = self.data_manager.create_order(
                            symbol=symbol,
                            side='BUY',
                            type_='MARKET',
                            quantity=quantity
                        )
                except Exception as e:
                    logger.error(f"Error ejecutando {operation} en {symbol}: {e}")
                    result = None
                
                if result and result.get('status', '') == 'FILLED':
                    executed_price = float(result.get('price', 0))
                    executed_qty = float(result.get('executedQty', 0))
                    fee = float(result.get('fee', 0))
                    
                    executed_trade = {
                        **trade,
                        'success': True,
                        'executed_price': executed_price,
                        'executed_qty': executed_qty,
                        'value': executed_price * executed_qty,
                        'fee': fee
                    }
                    
                    # Actualizar la base de datos
                    try:
                        # Si es compra, registrar nuevo activo
                        if trade['type'] == 'BUY':
                            # Extraer su00edmbolo base (sin USDC)
                            base_symbol = symbol.replace('USDC', '')
                            
                            # Verificar si ya existe el activo
                            db_manager = DatabaseManager(self.db_session)
                            existing_asset = db_manager.get_asset_by_symbol(base_symbol)
                            
                            if existing_asset:
                                # Actualizar activo existente (promedio ponderado)
                                current_amount = existing_asset.amount
                                current_price = existing_asset.purchase_price
                                new_amount = executed_qty
                                new_price = executed_price
                                
                                # Calcular nuevo precio promedio ponderado
                                total_amount = current_amount + new_amount
                                weighted_price = ((current_amount * current_price) + (new_amount * new_price)) / total_amount
                                
                                db_manager.update_asset(
                                    asset_id=existing_asset.id,
                                    amount=total_amount,
                                    purchase_price=weighted_price
                                )
                                logger.info(f"Actualizado activo en DB: {base_symbol}, cantidad: {total_amount}, precio: {weighted_price}")
                            else:
                                # Crear nuevo activo
                                db_manager.add_asset(
                                    symbol=base_symbol,
                                    amount=executed_qty,
                                    purchase_price=executed_price
                                )
                                logger.info(f"Creado activo en DB: {base_symbol}, cantidad: {executed_qty}, precio: {executed_price}")
                                
                        # Si es venta, actualizar o eliminar activo
                        elif trade['type'] == 'SELL':
                            # Extraer su00edmbolo base (sin USDC)
                            base_symbol = symbol.replace('USDC', '')
                            
                            # Buscar activo en DB
                            db_manager = DatabaseManager(self.db_session)
                            existing_asset = db_manager.get_asset_by_symbol(base_symbol)
                            
                            if existing_asset:
                                # Calcular cantidad restante después de la venta
                                remaining_amount = existing_asset.amount - executed_qty
                                
                                # Si vendimos todo o casi todo, eliminar el activo
                                if remaining_amount <= 0.00001:  # Considerar error de redondeo
                                    db_manager.delete_asset(existing_asset.id)
                                    logger.info(f"Eliminado activo de DB: {base_symbol} (venta completa)")
                                else:
                                    # Actualizar la cantidad
                                    db_manager.update_asset(
                                        asset_id=existing_asset.id,
                                        amount=remaining_amount
                                    )
                                    logger.info(f"Actualizado activo en DB: {base_symbol}, nueva cantidad: {remaining_amount}")
                    except Exception as e:
                        logger.error(f"Error actualizando base de datos para operaciu00f3n {trade['type']} de {symbol}: {e}")
                else:
                    executed_trade = {
                        **trade,
                        'success': False,
                        'error': 'La orden no se ejecutó completamente'
                    }
                
                executed_trades.append(executed_trade)
                
            except Exception as e:
                logger.error(f"Error ejecutando {trade['type']} de {trade['symbol']}: {e}")
                executed_trades.append({
                    **trade,
                    'success': False,
                    'error': str(e)
                })
        
        return executed_trades

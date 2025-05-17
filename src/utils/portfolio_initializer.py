from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from src.models.asset import Asset
from src.config.database import SessionLocal
from src.api.binance.data_manager import BinanceDataManager
from datetime import datetime
from loguru import logger
import sys
import os
import time

class PortfolioInitializer:
    def __init__(self):
        logger.debug("Inicializando PortfolioInitializer...")
        self.data_manager = BinanceDataManager()
        self.db = SessionLocal()
    
    def __del__(self):
        self.db.close()
    
    def get_binance_balance(self) -> List[Dict[str, Any]]:
        """
        Obtiene el balance de la cuenta de Binance con manejo de errores mejorado.
        
        Returns:
            List[Dict]: Lista de diccionarios con los balances de los activos.
                      Cada diccionario contiene:
                      - asset (str): Símbolo del activo (ej: 'BTC')
                      - free (float): Cantidad disponible para operar
                      - locked (float): Cantidad bloqueada en órdenes abiertas
                      - total (float): Suma de free + locked
        """
        try:
            logger.info("Obteniendo balance de Binance...")
            start_time = time.time()
            
            # Verificar si data_manager tiene el método necesario
            if not hasattr(self.data_manager, 'get_balance_summary'):
                error_msg = "El data_manager no tiene el método get_balance_summary"
                logger.error(error_msg)
                raise AttributeError(error_msg)
            
            # Obtener los balances
            logger.debug("Solicitando resumen de balance a la API de Binance...")
            balances = self.data_manager.get_balance_summary()
            
            if not isinstance(balances, list):
                error_msg = f"Se esperaba una lista de balances, se obtuvo: {type(balances)}"
                logger.error(error_msg)
                raise TypeError(error_msg)
            
            # Filtrar solo activos con saldo significativo (mayor a 0.000001)
            filtered_balances = []
            total_balance_usd = 0.0
            
            for balance in balances:
                try:
                    free = float(balance.get('free', 0))
                    locked = float(balance.get('locked', 0))
                    total = free + locked
                    
                    # Solo incluir activos con saldo significativo
                    if total >= 0.000001:
                        balance_data = {
                            'asset': balance['asset'],
                            'free': free,
                            'locked': locked,
                            'total': total
                        }
                        filtered_balances.append(balance_data)
                        
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error al procesar balance para {balance.get('asset', 'unknown')}: {e}")
            
            # Registrar métricas
            elapsed_time = time.time() - start_time
            logger.info(
                f"Balance obtenido exitosamente. "
                f"Activos con saldo: {len(filtered_balances)}. "
                f"Tiempo de respuesta: {elapsed_time:.2f}s"
            )
            
            if filtered_balances:
                assets_summary = ', '.join([f"{b['asset']}: {b['total']:.8f}" for b in filtered_balances])
                logger.debug(f"Resumen de activos: {assets_summary}")
            
            return filtered_balances
            
        except Exception as e:
            logger.exception(f"Error al obtener el balance de Binance: {str(e)}")
            # En un entorno de producción, podrías notificar al administrador aquí
            return []
    
    def get_asset_price(self, symbol: str) -> Optional[float]:
        """
        Obtiene el precio de compra más reciente de un activo basado en el historial de operaciones.
        Para activos que no son USDC, busca la operación de compra (BUY) más reciente en el par correspondiente.
        
        Args:
            symbol: Símbolo del activo (ej: 'BTC')
            
        Returns:
            float: Precio de compra por unidad del activo en USDC, o None si no se pudo determinar
        """
        try:
            if symbol == 'USDC':
                return 1.0  # 1 USDC = 1 USDC
                
            # Obtener el símbolo del par de trading (ej: BTCUSDC)
            trading_pair = f"{symbol}USDC"
            
            try:
                logger.info(f"Obteniendo órdenes para {trading_pair}")
                # Obtener todas las órdenes para este par
                orders = self.data_manager.get_all_orders(symbol=trading_pair)
                if not orders:
                    logger.warning(f"No se encontraron órdenes para {trading_pair}")
                    return None
                
                # Filtrar solo órdenes de compra completadas
                buy_orders = [
                    order for order in orders 
                    if order.get('side') == 'BUY' and order.get('status') == 'FILLED'
                ]
                
                if not buy_orders:
                    logger.warning(f"No se encontraron órdenes de compra completadas para {trading_pair}")
                    return None
                
                # Ordenar por tiempo (más reciente primero)
                buy_orders_sorted = sorted(buy_orders, key=lambda x: x.get('time', 0), reverse=True)
                
                # Tomar la orden de compra más reciente
                latest_buy = buy_orders_sorted[0]
                
                # Calcular el precio basado en la cantidad ejecutada y el monto total
                executed_qty = float(latest_buy.get('executedQty', 0))
                cumm_quote_qty = float(latest_buy.get('cummulativeQuoteQty', 0))
                
                if executed_qty > 0 and cumm_quote_qty > 0:
                    price = cumm_quote_qty / executed_qty
                    timestamp = latest_buy.get('time', 'desconocido')
                    logger.info(f"Precio de compra calculado para {symbol}: {price} USDC (comprado el {timestamp})")
                    return price
                
                logger.warning(f"No se pudo calcular el precio de compra para {symbol} - Cantidad: {executed_qty}, Monto: {cumm_quote_qty}")
                return None
                
            except Exception as e:
                logger.error(f"Error al obtener historial de operaciones para {trading_pair}: {e}")
                
            # No intentar con el precio actual como último recurso, ya que necesitamos el precio de compra real
            return None
            
        except Exception as e:
            logger.error(f"Error al obtener precio de compra para {symbol}: {e}")
            return None
    
    def asset_exists(self, symbol: str) -> bool:
        """Verifica si un activo ya existe en la base de datos"""
        return self.db.query(Asset).filter(Asset.symbol == symbol).first() is not None
    
    def initialize_portfolio(self) -> bool:
        """
        Inicializa el portafolio en la base de datos con los activos de Binance.
        Solo se añaden activos que no existan ya en la base de datos.
        
        Returns:
            bool: True si la inicialización fue exitosa, False en caso contrario
        """
        try:
            logger.info("Inicializando portafolio desde Binance...")
            balances = self.get_binance_balance()
            
            if not balances:
                logger.warning("No se encontraron saldos en Binance o hubo un error al obtenerlos")
                return False
            
            added_count = 0
            for balance in balances:
                symbol = balance['asset']
                free = float(balance.get('free', 0))
                locked = float(balance.get('locked', 0))
                total = free + locked
                
                if total < 1 or symbol == 'USDC':
                    continue
                
                # Verificar si el activo ya existe en la base de datos
                if self.asset_exists(symbol):
                    logger.debug(f"El activo {symbol} ya existe en la base de datos, omitiendo...")
                    continue
                
                # Obtener el precio de compra del activo
                purchase_price = self.get_asset_price(symbol)
                if purchase_price is None or purchase_price <= 0:
                    logger.warning(f"No se pudo obtener el precio de compra para {symbol}, omitiendo...")
                    continue
                
                # Crear el activo en la base de datos
                asset = Asset(
                    symbol=symbol,
                    amount=total,
                    purchase_price=purchase_price,
                    is_bubble=False,
                    force_sell=False
                )
                
                self.db.add(asset)
                added_count += 1
                logger.info(f"Añadido activo: {symbol} - Cantidad: {total} @ ${purchase_price}")
            
            if added_count > 0:
                self.db.commit()
                logger.info(f"Inicialización completada. Se añadieron {added_count} activos.")
            else:
                logger.info("No se añadieron nuevos activos. La base de datos ya está actualizada.")
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al inicializar el portafolio: {e}")
            return False
        finally:
            self.db.close()

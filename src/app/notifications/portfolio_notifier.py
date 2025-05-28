from loguru import logger
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from typing import Any, Optional
from src.models.asset import Asset
from src.config.database import SQLALCHEMY_DATABASE_URL
from config.settings import settings

def send_portfolio_update(data_manager: Any, notifier: Any) -> None:
    """
    Envía una actualización del portafolio.
    
    Args:
        data_manager: Instancia para obtener precios actuales
        notifier: Instancia para enviar notificaciones
    """
    # Configurar la conexión a la base de datos
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    try:
        # Obtener la hora actual
        now = datetime.now(timezone.utc)
        now_str = now.strftime("%Y-%m-%d %H:%M UTC")
        
        with Session(engine) as session:
            # Obtener todos los activos de la base de datos
            assets = session.query(Asset).all()
            
            if not assets:
                logger.warning("No se encontraron activos en la base de datos")
                return
            
            # Construir mensaje
            lines = [f"📊 *Portafolio - {now_str}*\n"]
            
            # Variables para el resumen total
            total_invested = 0.0
            total_current = 0.0
            assets_data = []
            
            # Procesar cada activo
            for asset in assets:
                try:
                    symbol = asset.symbol
                    current_price = data_manager.get_price(f"{symbol}USDC")
                    if not current_price:
                        logger.warning(f"No se pudo obtener el precio actual de {symbol}")
                        continue
                        
                    current_price = float(current_price)
                    purchase_price = asset.purchase_price
                    amount = asset.amount
                    
                    # Calcular valores
                    invested = asset.total_purchase_price
                    current_value = current_price * amount
                    profit_loss = current_value - invested
                    profit_loss_pct = (profit_loss / invested) * 100 if invested > 0 else 0
                    
                    # Actualizar totales
                    total_invested += invested
                    total_current += current_value
                    
                    # Almacenar datos del activo
                    assets_data.append({
                        'symbol': symbol,
                        'purchase_price': purchase_price,
                        'current_price': current_price,
                        'invested': invested,
                        'current_value': current_value,
                        'profit_loss': profit_loss,
                        'profit_loss_pct': profit_loss_pct
                    })
                    
                except Exception as e:
                    logger.error(f"Error procesando activo {getattr(asset, 'symbol', 'desconocido')}: {e}")
            
            # Ordenar activos por valor actual
            assets_data.sort(key=lambda x: x['current_value'], reverse=True)
            
            # Generar líneas para cada activo
            for asset_data in assets_data:
                try:
                    trend_emoji = "📈" if asset_data['profit_loss'] >= 0 else "📉"
                    lines.append(
                        f"{trend_emoji} *{asset_data['symbol']}*\n"
                        f"     • Compra: ${asset_data['purchase_price']:.8f}\n"
                        f"     • Actual: ${asset_data['current_price']:.8f}\n"
                        f"     • Total invertido: ${asset_data['invested']:.2f}\n"
                        f"     • Total actual: ${asset_data['current_value']:.2f}\n"
                        f"     • {'Ganancia' if asset_data['profit_loss'] >= 0 else 'Pérdida'}: "
                        f"{asset_data['profit_loss_pct']:+.2f}% (${abs(asset_data['profit_loss']):.2f})\n"
                    )
                except Exception as e:
                    logger.error(f"Error formateando datos del activo {asset_data.get('symbol', 'desconocido')}: {e}")
            
            # Añadir resumen total
            if total_invested > 0:
                total_profit_loss = total_current - total_invested
                total_profit_loss_pct = (total_profit_loss / total_invested) * 100
                
                lines.append("\n💼 *Resumen Total*")
                lines.append(f"• Total Invertido: ${total_invested:.2f}")
                lines.append(f"• Valor Actual: ${total_current:.2f}")
                lines.append(
                    f"• {'Ganancia' if total_profit_loss >= 0 else 'Pérdida'}: "
                    f"{total_profit_loss_pct:+.2f}% (${abs(total_profit_loss):.2f})"
                )

                lines.append(f"\n")
                lines.append(f"\nExecute buys: {settings.EXECUTE_BUYS}")
                lines.append(f"\nExecution mode: {settings.EXECUTION_MODE}")
            
            # Enviar mensaje
            message = "\n".join(lines)
            notifier.send_message(message)
            
    except Exception as e:
        logger.error(f"Error en notificación de portafolio: {e}")
    finally:
        engine.dispose()

def start_portfolio_notifier(data_manager: Any, notifier: Any, interval_minutes: int = 60) -> None:
    """
    Inicia el notificador de portafolio en un bucle infinito.
    
    Args:
        data_manager: Instancia para obtener precios actuales
        notifier: Instancia para enviar notificaciones
        interval_minutes: Intervalo en minutos entre notificaciones
    """
    import time
    
    logger.info(f"Iniciando notificador de portafolio (intervalo: {interval_minutes} minutos)")
    
    while True:
        try:
            send_portfolio_update(data_manager, notifier)
        except Exception as e:
            logger.error(f"Error en el bucle de notificaciones: {e}")
        
        # Esperar hasta la próxima notificación
        time.sleep(interval_minutes * 60)

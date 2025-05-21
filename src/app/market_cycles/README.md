# Sistema de Adaptación a Ciclos de Mercado

Este módulo implementa un sistema avanzado para detectar y adaptarse a los diferentes ciclos del mercado de criptomonedas, permitiendo que el bot optimice su estrategia según las condiciones actuales.

## Características Principales

- **Detección automática de 4 fases del mercado**:
  - **Acumulación**: Consolidación lateral después de una fase bajista
  - **Tendencia Alcista**: Momentum positivo con ruptura de resistencias
  - **Distribución**: Agotamiento alcista cerca de máximos
  - **Tendencia Bajista**: Mercado en caída con ruptura de soportes

- **Adaptaciones dinámicas de estrategia**:
  - Ajuste de asignación de capital y exposición al riesgo
  - Modificación de umbrales de compra y venta
  - Adaptación de stop loss y take profit
  - Integración con otros componentes como el detector de burbujas

- **Interfaz de análisis y monitoreo**:
  - CLI para visualizar el ciclo actual y adaptaciones
  - Gráficos y estadísticas para análisis avanzado

## Arquitectura

El sistema está compuesto por los siguientes módulos:

1. **MarketCycleDetector**: Analiza indicadores técnicos, datos de precio y volatilidad para identificar la fase actual del mercado.

2. **MarketCycleIntegrator**: Conecta el detector con el resto del sistema y define configuraciones optimizadas para cada fase.

3. **AdaptiveStrategyManager**: Orquesta la interacción entre los diferentes componentes del bot, modificando parámetros según el ciclo detectado.

4. **Integración con RiskManager**: Centraliza la gestión de riesgos y aplica las adaptaciones a los diferentes componentes del sistema.

## Configuración

Los parámetros del sistema se pueden configurar en `settings.py`:

```python
# Configuración del sistema de adaptación a ciclos de mercado
ENABLE_MARKET_CYCLE_ADAPTATION: bool = True   # Activar/desactivar el sistema
MARKET_CYCLE_UPDATE_INTERVAL: int = 8         # Horas entre actualizaciones
MARKET_CYCLE_LOOKBACK_DAYS: int = 90          # Días de datos históricos

# Configuraciones para diferentes ciclos (valores base)
ACCUMULATION_RISK_AVERSION: float = 0.5
UPTREND_RISK_AVERSION: float = 0.3
DISTRIBUTION_RISK_AVERSION: float = 0.7
DOWNTREND_RISK_AVERSION: float = 0.9
```

## Herramientas de Análisis

Se incluye una herramienta CLI para analizar los ciclos de mercado:

```bash
# Ver el ciclo actual y adaptaciones
python -m src.scripts.market_cycle_analysis --action status

# Monitorear continuamente el ciclo
python -m src.scripts.market_cycle_analysis --action monitor --interval 300

# Realizar análisis detallado con gráficos
python -m src.scripts.market_cycle_analysis --action analyze --days 180

# Simular diferentes ciclos (para pruebas)
python -m src.scripts.market_cycle_analysis --action simulate --simulate-cycle uptrend
```

## Integración con Otros Sistemas

El sistema de adaptación a ciclos de mercado se integra con varios componentes existentes:

1. **Detector de Burbujas**: Ajusta la sensibilidad del detector según el ciclo actual
2. **Sistema de Inversión Proporcional al Riesgo**: Modifica los umbrales de confianza y multiplicadores
3. **Rebalanceador de Portafolio**: Adapta frecuencia y parámetros de rebalanceo
4. **Gestión de Stop Loss/Take Profit**: Ajusta multiplicadores según condiciones del mercado

## Ejemplo de Adaptaciones

### En Fase de Acumulación
- Riesgo moderado (0.5)
- 15% máximo por activo
- 20% en stablecoins
- DCA activado

### En Fase Alcista
- Menor aversión al riesgo (0.3)
- 25% máximo por activo
- 10% en stablecoins
- Mayor take profit

### En Fase de Distribución
- Mayor aversión al riesgo (0.7)
- 10% máximo por activo
- 40% en stablecoins
- Stop loss ajustado

### En Fase Bajista
- Máxima aversión al riesgo (0.9)
- 5% máximo por activo
- 60% en stablecoins
- DCA activado para promediar a la baja

## Funcionamiento Interno

El sistema evalúa los siguientes indicadores para determinar el ciclo:

- Precio en relación a máximos y mínimos históricos
- Tendencias en medias móviles
- Patrones de volumen
- Volatilidad
- Indicadores técnicos (RSI, MACD)
- Datos de sentimiento de mercado (si están disponibles)

La detección se actualiza periódicamente (por defecto cada 8 horas) y las adaptaciones se aplican automáticamente a través del sistema centralizado de gestión de riesgos.

from abc import ABC, abstractmethod

class StrategyPlugin(ABC):
    """
    Base class for strategy plugins.
    """
    @abstractmethod
    def __init__(self, data_manager, settings):
        """Initialize plugin with data manager and settings."""
        pass

    @abstractmethod
    def name(self) -> str:
        """Return the strategy name."""
        pass

    @abstractmethod
    def analyze(self) -> dict:
        """
        Analyze market data and return signals.
        Expected return format: {'buy': bool, 'sell': bool, 'size': float}
        """
        pass

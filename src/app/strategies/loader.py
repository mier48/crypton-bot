import importlib
import pkgutil
from pathlib import Path
from typing import List

from config.settings import settings
from app.strategies.base import StrategyPlugin


def load_strategies(data_manager, settings_obj) -> List[StrategyPlugin]:
    """
    Dynamically discover and load strategy plugins from the strategies package.
    Each plugin must subclass StrategyPlugin and implement name() and analyze().
    """
    strategies = []
    package = importlib.import_module('app.strategies')
    pkg_path = Path(package.__file__).parent

    for finder, name, ispkg in pkgutil.iter_modules([str(pkg_path)]):
        if name in ('__init__', 'base', 'loader'):
            continue
        module_name = f'app.strategies.{name}'
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, StrategyPlugin) and obj is not StrategyPlugin:
                try:
                    instance = obj(data_manager, settings_obj)
                    strategies.append(instance)
                except Exception:
                    continue
    return strategies

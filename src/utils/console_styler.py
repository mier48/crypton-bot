from typing import Dict
from colorama import Fore, Style

class ConsoleStyler:
    COLORS = {
        "info": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED,
        "debug": Fore.CYAN,
        "default": Fore.WHITE
    }

    @staticmethod
    def print_log(level: str, message: Dict[str, str]) -> None:
        color = ConsoleStyler.COLORS.get(level, Fore.WHITE)
        print(f"{color}[{message.get('symbol', '')}] {message.get('message', '')}{Style.RESET_ALL}")

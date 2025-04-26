"""
Registry for symbols bought under bubble_momentum override to trigger quick sell.
"""
bubble_symbols = set()

def register(symbol: str) -> None:
    """Register a symbol for quick sell."""
    bubble_symbols.add(symbol)


def get_and_clear_all() -> set:
    """Retrieve and clear all registered symbols."""
    syms = set(bubble_symbols)
    bubble_symbols.clear()
    return syms

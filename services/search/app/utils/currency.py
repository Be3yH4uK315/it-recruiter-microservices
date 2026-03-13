def normalize_to_rub(amount: float | int | None, currency: str | None) -> float | None:
    """Нормализует зарплату в рубли для корректного сравнения."""
    if amount is None:
        return None
    
    rates = {
        "USD": 95.0, 
        "EUR": 105.0, 
        "RUB": 1.0, 
        "KZT": 0.2, 
        "RSD": 0.88
    }
    curr = (currency or "RUB").upper()
    return float(amount) * rates.get(curr, 1.0)

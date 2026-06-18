import re

VAT_RATE = 0.18


def format_money(value):
    if value is None:
        return "—"
    formatted = f"{int(round(float(value))):,}".replace(",", "\u202F")
    return f"₪{formatted}"


def parse_money_input(value, fallback=0):
    if value is None:
        return fallback
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        return fallback
    return int(digits)


def safe_float(value, fallback=0.0):
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = (
        str(value)
        .replace("₪", "")
        .replace(",", "")
        .replace("\u00A0", "")
        .replace("\u202F", "")
        .replace(" ", "")
        .strip()
    )
    try:
        return float(cleaned)
    except ValueError:
        return fallback


def vat_summary(subtotal, vat_rate=VAT_RATE):
    subtotal = round(float(subtotal))
    vat = round(subtotal * vat_rate)
    total = subtotal + vat
    return subtotal, vat, total

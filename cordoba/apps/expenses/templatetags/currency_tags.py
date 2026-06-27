from django import template

register = template.Library()


@register.filter
def ars(value):
    """
    Format a number in Argentine peso style: 40.200,00
    Thousands separator = period, decimal separator = comma, 2 decimal places.
    """
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return value
    formatted = f"{amount:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted

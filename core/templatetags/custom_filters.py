from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def calc_percentage(value, total):
    """Calculate percentage of value relative to total"""
    try:
        value = Decimal(str(value))
        total = Decimal(str(total))
        if total == 0:
            return 0
        return (value / total) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return 0

@register.filter
def format_currency(value):
    """Format value as currency"""
    try:
        return f"${Decimal(str(value)):.2f}"
    except (TypeError, ValueError):
        return "$0.00"

@register.filter
def sum_attr(objects, attribute):
    """Sum an attribute across multiple objects"""
    try:
        total = Decimal('0.00')
        for obj in objects:
            val = getattr(obj, attribute, 0)
            total += Decimal(str(val)) if val else Decimal('0.00')
        return total
    except (TypeError, ValueError, AttributeError):
        return Decimal('0.00')

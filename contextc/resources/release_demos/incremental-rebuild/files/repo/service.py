"""Tiny checkout service used by the M16 incremental release demo."""


def checkout_total(subtotal: int, discount: int) -> int:
    return subtotal - discount

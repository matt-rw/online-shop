"""
Stock management utilities — centralized stock modification with audit logging.
All stock changes should go through these functions to ensure audit trail.
"""

from shop.models.inventory import StockAdjustment


def adjust_stock(variant, new_quantity, adjustment_type="manual", reason="", user=None):
    """
    Change a variant's stock quantity and create an audit log entry.

    Args:
        variant: ProductVariant instance
        new_quantity: The new stock quantity (int)
        adjustment_type: One of StockAdjustment.ADJUSTMENT_TYPES
        reason: Text explanation
        user: User who made the change (optional)

    Returns:
        StockAdjustment instance
    """
    prev = variant.stock_quantity
    diff = new_quantity - prev

    if diff == 0:
        return None

    adjustment = StockAdjustment.objects.create(
        variant=variant,
        adjustment_type=adjustment_type,
        previous_quantity=prev,
        new_quantity=new_quantity,
        difference=diff,
        reason=reason,
        adjusted_by=user,
    )

    variant.stock_quantity = new_quantity
    variant.save(update_fields=["stock_quantity"])

    return adjustment


def add_stock(variant, quantity, adjustment_type="shipment_received", reason="", user=None):
    """Add stock to a variant."""
    return adjust_stock(
        variant,
        variant.stock_quantity + quantity,
        adjustment_type=adjustment_type,
        reason=reason,
        user=user,
    )


def deduct_stock(variant, quantity, adjustment_type="order_sold", reason="", user=None):
    """Deduct stock from a variant. Won't go below 0."""
    new_qty = max(0, variant.stock_quantity - quantity)
    return adjust_stock(
        variant,
        new_qty,
        adjustment_type=adjustment_type,
        reason=reason,
        user=user,
    )

"""A deliberately overgrown service to make architecture and complexity visible."""

from database import find_user


def process_order(user, order, coupon=None):
    if user is None:
        return {"ok": False, "reason": "missing user"}
    if not order:
        return {"ok": False, "reason": "empty order"}
    if order.get("status") == "cancelled":
        return {"ok": False, "reason": "cancelled"}
    if order.get("total", 0) < 0:
        return {"ok": False, "reason": "invalid total"}
    if coupon and coupon.get("expired"):
        return {"ok": False, "reason": "expired coupon"}
    if coupon and coupon.get("type") == "vip":
        order["total"] *= 0.8
    if order.get("total", 0) > 10000:
        order["needs_manual_review"] = True
    customer = find_user(user.get("name", ""))
    if customer and order.get("shipping") == "express":
        order["shipping_fee"] = 0
    else:
        order["shipping_fee"] = 20
    if order.get("payment") == "cash" and order.get("total", 0) > 5000:
        order["needs_manual_review"] = True
    if not order.get("items"):
        order["warning"] = "no items"
    if order.get("country") == "CN":
        order["tax"] = order.get("total", 0) * 0.13
    else:
        order["tax"] = 0
    if order.get("priority") == "high":
        order["queue"] = "fast"
    else:
        order["queue"] = "normal"
    if order.get("retry"):
        order["retry_count"] = order.get("retry_count", 0) + 1
    if order.get("retry_count", 0) > 3:
        order["needs_manual_review"] = True
    if user.get("role") == "guest":
        order["guest_limit"] = True
    if order.get("gift"):
        order["gift_message"] = "included"
    if order.get("address") is None:
        order["warning"] = "missing address"
    if order.get("currency") not in {"CNY", "USD"}:
        order["currency"] = "CNY"
    if order.get("total", 0) == 0:
        order["warning"] = "free order"
    if order.get("source") == "campaign":
        order["campaign"] = True
    if order.get("items") and len(order["items"]) > 50:
        order["bulk"] = True
    if order.get("status") == "pending":
        order["next_step"] = "payment"
    if order.get("status") == "paid":
        order["next_step"] = "fulfillment"
    if order.get("status") == "shipped":
        order["next_step"] = "delivery"
    if order.get("status") == "delivered":
        order["next_step"] = "after_sales"
    return {"ok": True, "customer": customer, "order": order}

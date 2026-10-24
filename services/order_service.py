import logging
import os
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from flask import Flask, jsonify, request

PORT = int(os.getenv("ORDER_PORT", "5050"))
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:5051")
TIMEOUT_SECONDS = float(os.getenv("INVENTORY_TIMEOUT_SECONDS", "2"))

ORDERS = {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [order] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.get("/orders/<order_id>")
def get_order(order_id):
    order = ORDERS.get(order_id)
    if order is None:
        return jsonify(error=f"order '{order_id}' not found"), 404
    return jsonify(order), 200


@app.post("/orders")
def create_order():
    body = request.get_json(silent=True) or {}
    item_id = body.get("item_id")
    quantity = body.get("quantity")

    valid_item = isinstance(item_id, str) and item_id != ""
    valid_quantity = isinstance(quantity, int) and not isinstance(quantity, bool) and quantity > 0
    if not valid_item or not valid_quantity:
        return jsonify(error="item_id must be a non-empty string and quantity a positive integer"), 400

    try:
        resp = requests.get(
            f"{INVENTORY_URL}/inventory/{quote(item_id, safe='')}",
            params={"quantity": quantity},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        log.warning("inventory did not answer within %.1fs, order for %s not created", TIMEOUT_SECONDS, item_id)
        return jsonify(error=f"inventory service timed out after {TIMEOUT_SECONDS}s"), 504
    except requests.exceptions.ConnectionError:
        log.warning("inventory unreachable at %s, order for %s not created", INVENTORY_URL, item_id)
        return jsonify(error="inventory service is unavailable, order was not created"), 503

    if resp.status_code == 404:
        log.info("order rejected: unknown item %s", item_id)
        return jsonify(resp.json()), 404

    if resp.status_code != 200:
        log.warning("unexpected inventory response %d", resp.status_code)
        return jsonify(error="unexpected response from inventory service"), 502

    available = resp.json().get("status") == "available"
    order = {
        "order_id": str(uuid.uuid4()),
        "item_id": item_id,
        "quantity": quantity,
        "status": "CONFIRMED" if available else "REJECTED",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ORDERS[order["order_id"]] = order
    log.info("order %s %s for %s x%d", order["order_id"], order["status"], item_id, quantity)

    if available:
        return jsonify(order), 201
    return jsonify({**order, "reason": f"'{item_id}' is unavailable"}), 409


if __name__ == "__main__":
    log.info("listening on :%d -> inventory %s (timeout %.1fs)", PORT, INVENTORY_URL, TIMEOUT_SECONDS)
    app.run(host="0.0.0.0", port=PORT)

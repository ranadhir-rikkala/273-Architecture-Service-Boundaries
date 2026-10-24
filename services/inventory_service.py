import logging
import os

from flask import Flask, jsonify, request

PORT = int(os.getenv("INVENTORY_PORT", "5051"))

STOCK = {
    "keyboard": 12,
    "monitor": 4,
    "mouse": 0,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [inventory] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


@app.get("/inventory/<item_id>")
def check_availability(item_id):
    try:
        quantity = int(request.args.get("quantity", "1"))
    except ValueError:
        quantity = 0

    if quantity <= 0:
        return jsonify(error="quantity must be a positive integer"), 400

    if item_id not in STOCK:
        log.info("check %s x%d -> unknown item", item_id, quantity)
        return jsonify(error=f"item '{item_id}' not found"), 404

    in_stock = STOCK[item_id]
    status = "available" if in_stock >= quantity else "unavailable"
    log.info("check %s x%d -> %s (in stock: %d)", item_id, quantity, status, in_stock)
    return jsonify(item_id=item_id, requested=quantity, in_stock=in_stock, status=status), 200


if __name__ == "__main__":
    log.info("listening on :%d", PORT)
    app.run(host="0.0.0.0", port=PORT)

#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
LOGS=evidence/logs
mkdir -p "$LOGS"
export NO_COLOR=1 PYTHONUNBUFFERED=1

wait_port() {
  for _ in $(seq 1 100); do nc -z localhost "$1" 2>/dev/null && return 0; sleep 0.1; done
  echo "port $1 did not open"; exit 1
}

start_inventory() {
  python services/inventory_service.py >> "$LOGS/inventory.log" 2>&1 &
  INV_PID=$!
  wait_port 5051
}

order() {
  echo
  echo "\$ curl -s -X POST localhost:5050/orders -H 'Content-Type: application/json' -d '$1'"
  curl -s -w 'HTTP %{http_code}\n' -X POST localhost:5050/orders -H 'Content-Type: application/json' -d "$1" | tee "$LOGS/last_response"
}

rm -f "$LOGS"/*.log
python services/order_service.py > "$LOGS/order.log" 2>&1 &
ORDER_PID=$!
wait_port 5050
trap 'kill $ORDER_PID $INV_PID 2>/dev/null' EXIT

echo "=== 1. Both services running ==="
start_inventory
echo
echo "\$ curl -s 'localhost:5051/inventory/keyboard?quantity=2'"
curl -s -w 'HTTP %{http_code}\n' 'localhost:5051/inventory/keyboard?quantity=2'
order '{"item_id": "keyboard", "quantity": 2}'
FIRST_ORDER=$(head -1 "$LOGS/last_response" | python -c 'import json,sys; print(json.load(sys.stdin)["order_id"])')
order '{"item_id": "mouse", "quantity": 1}'
order '{"item_id": "webcam", "quantity": 1}'
order '{"item_id": "monitor"}'

echo
echo "=== 2. Inventory Service stopped ==="
echo "\$ kill $INV_PID"
kill $INV_PID; wait $INV_PID 2>/dev/null
order '{"item_id": "monitor", "quantity": 1}'

echo
echo "=== 3. Order Service still running ==="
echo "\$ ps -p $ORDER_PID -o pid,command"
ps -p $ORDER_PID -o pid,command
echo
echo "\$ curl -s localhost:5050/health"
curl -s -w 'HTTP %{http_code}\n' localhost:5050/health
echo
echo "\$ curl -s localhost:5050/orders/$FIRST_ORDER"
curl -s -w 'HTTP %{http_code}\n' "localhost:5050/orders/$FIRST_ORDER"

echo
echo "=== 4. Inventory Service restarted ==="
start_inventory
order '{"item_id": "monitor", "quantity": 1}'

echo
echo "=== Order Service log ==="
sed -E "s/\x1b\[[0-9;]*m//g" "$LOGS/order.log"
echo
echo "=== Inventory Service log ==="
sed -E "s/\x1b\[[0-9;]*m//g" "$LOGS/inventory.log"
rm -f "$LOGS/last_response"

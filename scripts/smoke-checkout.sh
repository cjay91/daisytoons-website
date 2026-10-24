#!/usr/bin/env bash
# End-to-end check against the running Compose stack: a guest buys a product through the fake
# gateway while the same "paid" notification arrives twice more at the same moment. Exactly one
# paid order, one stock sale and one email must come out of it.
#
# Needs: docker compose up, and the sample products imported.
set -euo pipefail

API=${API:-http://localhost:8000}
MAILPIT=${MAILPIT:-http://localhost:8025}
json() { python3 -c "import json, sys; print(json.load(sys.stdin)$1)"; }
psql() { docker compose exec -T db psql -U daisytoons -tAc "$1"; }

token=$(curl -sf -X POST "$API/cart" | json '["token"]')
product=$(curl -sf "$API/products" | json '[0]["id"]')
on_hand_before=$(psql "select on_hand from inventory where product_id = $product")
curl -sf -X PUT "$API/cart/items/$product" -H "X-Cart-Token: $token" \
  -H 'Content-Type: application/json' -d '{"quantity": 2}' > /dev/null

checkout=$(curl -sf -X POST "$API/checkout" -H "X-Cart-Token: $token" \
  -H 'Content-Type: application/json' \
  -d '{"email": "smoke@example.com", "customer_name": "Smoke Test", "phone": "0771234567",
       "address": {"line1": "1 Main Street", "city": "Kandy", "district": "Kandy"}}')
order=$(echo "$checkout" | json '["order_number"]')
key=$(echo "$checkout" | json '["order_key"]')
total=$(echo "$checkout" | json '["total"]')
echo "Order $order, total Rs $total"

notification=$(docker compose exec -T api python -c "
from urllib.parse import urlencode
from app.services.payments import fake_notification
print(urlencode(fake_notification('$order', '$total', 'LKR', '2')))")
curl -sf -o /dev/null -X POST "$API/payments/fake/complete" \
  -d "order_id=$order&amount=$total&currency=LKR&status_code=2" &
curl -sf -o /dev/null -X POST "$API/payments/payhere/notify" -d "$notification" &
curl -sf -o /dev/null -X POST "$API/payments/payhere/notify" -d "$notification" &
wait
sleep 2

status=$(curl -sf "$API/orders/$order?key=$key" | json '["status"]')
paid=$(psql "select count(*) from payment_events where order_number = '$order' and outcome = 'paid'")
sales=$(psql "select count(*) from stock_adjustments where note = 'Order $order' and reason = 'sale'")
on_hand_after=$(psql "select on_hand from inventory where product_id = $product")
emails=$(curl -sf "$MAILPIT/api/v1/search?query=$order" | json '["messages_count"]')
echo "status=$status paid_events=$paid sales=$sales stock=$on_hand_before->$on_hand_after emails=$emails"

[ "$status" = paid ] && [ "$paid" = 1 ] && [ "$sales" = 1 ] && [ "$emails" = 1 ] \
  && [ "$on_hand_after" = $((on_hand_before - 2)) ]

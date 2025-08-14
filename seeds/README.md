# Foody seeds & test

## Smoke (bash)

```bash
API=https://<backend-domain>

# health
curl -sS $API/health

# register
RID=$(curl -sS -XPOST $API/api/v1/merchant/register_public -H 'Content-Type: application/json' -d '{"title":"Пекарня №1","phone":"+79991234567","city":"Москва","address":"Тверская, 1"}' | jq -r .restaurant_id)
KEY=$(curl -sS $API/api/v1/merchant/recover -H 'Content-Type: application/json' -d '{"phone":"+79991234567","secret":"$RECOVERY_SECRET"}' | jq -r .api_key)

# create offer
curl -sS -XPOST $API/api/v1/merchant/offers -H 'X-Foody-Key: '$KEY -H 'Content-Type: application/json' -d '{"restaurant_id":"'$RID'","title":"Набор эклеров","price_cents":19900,"original_price_cents":34900,"qty_total":5,"qty_left":5,"expires_at":"2025-08-31T20:00:00Z"}'

# public offers
curl -sS $API/api/v1/offers
```

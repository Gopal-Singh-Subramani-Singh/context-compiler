# Checkout rollback runbook v2
Approved procedure: stop the checkout rollout, roll back checkout-api to the prior image, preserve database state, verify checkout-cache hit ratio, then confirm checkout p95 and error rate recover before reopening traffic.

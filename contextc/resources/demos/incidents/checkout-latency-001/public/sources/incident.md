# INC-2026-0903 Checkout latency regression
Checkout p95 latency rose from 420 ms to 2.8 s within minutes of deployment checkout-api 2026.09.03.1. Errors increased on the checkout path while payment and search remained healthy. The current response is to use rollback runbook v2 and verify cache dependency health.

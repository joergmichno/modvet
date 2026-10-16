# 0002: The Dunning Run is nightly, not per failure

Status: accepted. Failed charges are retried by one nightly Dunning Run (3 attempts over 7 days), not on each webhook.

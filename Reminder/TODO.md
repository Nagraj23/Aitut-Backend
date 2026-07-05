# TODO - Redis Cloud migration

- [x] Gathered understanding of where Redis is used (Celery broker/backend, SSE pubsub, and publisher)
- [x] Update Celery broker/backend to use Redis Cloud connection (via REDIS_URL)
- [x] Update Redis publisher in services/task.py to use Redis Cloud connection (TLS + auth)
- [x] Update SSE Redis pubsub connection in api/routes.py to use Redis Cloud connection
- [x] Update test_trigger.py to match Redis Cloud connection

- [x] Verify dependencies support redis.asyncio and TLS (requirements.txt check)
- [ ] Run local/manual tests for: alarm creation -> task trigger -> SSE event received






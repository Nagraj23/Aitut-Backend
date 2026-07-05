from functools import lru_cache
from dotenv import load_dotenv
import os
import redis
from redis.asyncio import Redis as AsyncRedis

load_dotenv()

REDIS_URL = os.environ["REDIS_URL"]

@lru_cache
def get_redis():
    return redis.from_url(
        REDIS_URL,
        decode_responses=True
    )

@lru_cache
def get_async_redis():
    return AsyncRedis.from_url(
        REDIS_URL,
        decode_responses=True
    )

def get_redis_url():
    return REDIS_URL
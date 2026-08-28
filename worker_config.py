import redis
from rq import Queue

# Binary connection for RQ (must be decode_responses=False)
redis_conn = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=False  # RQ requires binary mode
)

# String connection for URL caching
r = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True
)

q = Queue("click_queue", connection=redis_conn)
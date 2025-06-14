import asyncio
from heare.developer.rate_limiter import RateLimiter


async def test_rate_limiter():
    limiter = RateLimiter()

    # Test normal case (no rate limit)
    print("Testing normal case...")
    await limiter.check_and_wait()
    print("✅ Normal case works")

    # Test rate limit case
    print("Testing rate limit case...")
    limiter.last_rate_limit_error = Exception("test error")
    limiter.backoff_time = 0.1  # Very short for testing

    import time

    start = time.time()
    await limiter.check_and_wait()
    end = time.time()

    elapsed = end - start
    print(f"Waited {elapsed:.2f} seconds")
    assert elapsed >= 0.05, f"Should have waited at least 0.05 seconds, got {elapsed}"
    assert limiter.last_rate_limit_error is None, "Error should be cleared"
    assert limiter.backoff_time == 0, "Backoff time should be reset"

    print("✅ Rate limit case works")
    print("🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_rate_limiter())

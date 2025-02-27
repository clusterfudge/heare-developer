import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from heare.developer.rate_limiter import RateLimiter


class TestRateLimiter(unittest.TestCase):
    def setUp(self):
        self.rate_limiter = RateLimiter()
        self.mock_user_interface = MagicMock()

        # Create a future reset time for testing
        self.future_time = datetime.now(timezone.utc) + timedelta(seconds=60)
        self.future_time_str = self.future_time.isoformat()

        # Create a near future reset time
        self.near_future_time = datetime.now(timezone.utc) + timedelta(seconds=10)
        self.near_future_time_str = self.near_future_time.isoformat()

        # Create headers with all Anthropic rate limit information
        self.full_headers = {
            "retry-after": "30",
            "anthropic-ratelimit-tokens-limit": "100000",
            "anthropic-ratelimit-tokens-remaining": "5000",
            "anthropic-ratelimit-tokens-reset": self.future_time_str,
            "anthropic-ratelimit-input-tokens-limit": "50000",
            "anthropic-ratelimit-input-tokens-remaining": "4000",
            "anthropic-ratelimit-input-tokens-reset": self.future_time_str,
            "anthropic-ratelimit-output-tokens-limit": "50000",
            "anthropic-ratelimit-output-tokens-remaining": "3000",
            "anthropic-ratelimit-output-tokens-reset": self.future_time_str,
            "anthropic-ratelimit-requests-limit": "500",
            "anthropic-ratelimit-requests-remaining": "100",
            "anthropic-ratelimit-requests-reset": self.future_time_str,
        }

        # Create a mock error with response headers
        self.mock_error = MagicMock()
        self.mock_error.response = MagicMock()
        self.mock_error.response.headers = self.full_headers

    def test_update_all_headers(self):
        """Test that update method properly parses all headers"""
        self.rate_limiter.update(self.full_headers)

        # Check token limits
        self.assertEqual(self.rate_limiter.limits["tokens"]["limit"], 100000)
        self.assertEqual(self.rate_limiter.limits["tokens"]["remaining"], 5000)
        self.assertEqual(
            self.rate_limiter.limits["tokens"]["reset_time"].isoformat(),
            self.future_time_str,
        )

        # Check input token limits
        self.assertEqual(self.rate_limiter.limits["input_tokens"]["limit"], 50000)
        self.assertEqual(self.rate_limiter.limits["input_tokens"]["remaining"], 4000)
        self.assertEqual(
            self.rate_limiter.limits["input_tokens"]["reset_time"].isoformat(),
            self.future_time_str,
        )

        # Check output token limits
        self.assertEqual(self.rate_limiter.limits["output_tokens"]["limit"], 50000)
        self.assertEqual(self.rate_limiter.limits["output_tokens"]["remaining"], 3000)
        self.assertEqual(
            self.rate_limiter.limits["output_tokens"]["reset_time"].isoformat(),
            self.future_time_str,
        )

        # Check request limits
        self.assertEqual(self.rate_limiter.limits["requests"]["limit"], 500)
        self.assertEqual(self.rate_limiter.limits["requests"]["remaining"], 100)
        self.assertEqual(
            self.rate_limiter.limits["requests"]["reset_time"].isoformat(),
            self.future_time_str,
        )

        # Check retry-after
        self.assertEqual(self.rate_limiter.retry_after, 30)

    def test_update_partial_headers(self):
        """Test that update method correctly handles partial headers"""
        partial_headers = {
            "anthropic-ratelimit-tokens-limit": "100000",
            "anthropic-ratelimit-tokens-remaining": "5000",
            # Intentionally missing reset time
            # Only include requests information
            "anthropic-ratelimit-requests-limit": "500",
            "anthropic-ratelimit-requests-remaining": "100",
            "anthropic-ratelimit-requests-reset": self.future_time_str,
        }

        self.rate_limiter.update(partial_headers)

        # Check token limits (with missing reset time)
        self.assertEqual(self.rate_limiter.limits["tokens"]["limit"], 100000)
        self.assertEqual(self.rate_limiter.limits["tokens"]["remaining"], 5000)
        self.assertIsNone(self.rate_limiter.limits["tokens"]["reset_time"])

        # Check request limits (complete)
        self.assertEqual(self.rate_limiter.limits["requests"]["limit"], 500)
        self.assertEqual(self.rate_limiter.limits["requests"]["remaining"], 100)
        self.assertEqual(
            self.rate_limiter.limits["requests"]["reset_time"].isoformat(),
            self.future_time_str,
        )

        # Others should be None
        self.assertIsNone(self.rate_limiter.limits["input_tokens"]["limit"])
        self.assertIsNone(self.rate_limiter.limits["output_tokens"]["limit"])

    def test_handle_rate_limit_error_with_retry_after(self):
        """Test that handle_rate_limit_error prioritizes retry-after header"""
        self.rate_limiter.handle_rate_limit_error(self.mock_error)

        # Should use the retry-after value directly
        self.assertEqual(self.rate_limiter.backoff_time, 30)
        self.assertEqual(self.rate_limiter.last_rate_limit_error, self.mock_error)

        # Should have updated all the rate limit info
        self.assertEqual(self.rate_limiter.limits["tokens"]["remaining"], 5000)
        self.assertEqual(
            self.rate_limiter.limits["tokens"]["reset_time"].isoformat(),
            self.future_time_str,
        )

    def test_handle_rate_limit_error_without_retry_after(self):
        """Test that handle_rate_limit_error calculates backoff time from reset times when retry-after is not present"""
        # Remove retry-after header
        headers_without_retry = dict(self.full_headers)
        del headers_without_retry["retry-after"]

        # Create earlier reset time for input tokens
        earlier_reset = datetime.now(timezone.utc) + timedelta(seconds=30)
        headers_without_retry["anthropic-ratelimit-input-tokens-reset"] = (
            earlier_reset.isoformat()
        )

        # Update mock error
        self.mock_error.response.headers = headers_without_retry

        backoff_time = self.rate_limiter.handle_rate_limit_error(self.mock_error)

        # Should calculate backoff based on the earliest reset time (input tokens)
        self.assertGreater(backoff_time, 20)  # Allow for test execution time
        self.assertLess(backoff_time, 35)  # Allow for test execution time

        # Should have updated all the rate limit info
        self.assertEqual(
            self.rate_limiter.limits["input_tokens"]["reset_time"].isoformat(),
            earlier_reset.isoformat(),
        )

    def test_handle_rate_limit_error_no_headers(self):
        """Test that handle_rate_limit_error uses default backoff when no headers are available"""
        # Create an error without headers
        mock_error_no_headers = MagicMock()
        mock_error_no_headers.response = None

        backoff_time = self.rate_limiter.handle_rate_limit_error(mock_error_no_headers)

        # Should use default backoff time (60 seconds)
        self.assertEqual(backoff_time, 60)
        self.assertEqual(self.rate_limiter.backoff_time, 60)

    @patch("time.sleep")
    def test_check_and_wait_after_error(self, mock_sleep):
        """Test check_and_wait behavior right after a rate limit error"""
        # Setup rate limiter as if it had encountered an error
        self.rate_limiter.last_rate_limit_error = self.mock_error
        self.rate_limiter.backoff_time = 30

        self.rate_limiter.check_and_wait(self.mock_user_interface)

        # Should have called sleep with backoff_time
        mock_sleep.assert_called_once_with(30)

        # Should have cleared error and backoff
        self.assertIsNone(self.rate_limiter.last_rate_limit_error)
        self.assertEqual(self.rate_limiter.backoff_time, 0)

        # Should have notified user
        self.mock_user_interface.handle_system_message.assert_called_once()

    @patch("time.sleep")
    def test_check_and_wait_approaching_token_limit(self, mock_sleep):
        """Test check_and_wait when approaching token limit"""
        # Setup rate limiter with low tokens remaining
        self.rate_limiter.limits["tokens"]["remaining"] = 500
        self.rate_limiter.limits["tokens"]["reset_time"] = self.near_future_time

        self.rate_limiter.check_and_wait(self.mock_user_interface)

        # Should have called sleep with wait_time close to 10 seconds
        self.assertEqual(mock_sleep.call_count, 1)
        wait_time = mock_sleep.call_args[0][0]
        self.assertGreater(wait_time, 5)  # Allow for test execution time
        self.assertLess(wait_time, 15)  # Allow for test execution time

        # Should have notified user
        self.mock_user_interface.handle_system_message.assert_called_once()

    @patch("time.sleep")
    def test_check_and_wait_approaching_request_limit(self, mock_sleep):
        """Test check_and_wait when approaching request limit"""
        # Setup rate limiter with low requests remaining but plenty of tokens
        self.rate_limiter.limits["tokens"]["remaining"] = 5000
        self.rate_limiter.limits["requests"]["remaining"] = (
            3  # Below the threshold for requests (5)
        )
        self.rate_limiter.limits["requests"]["reset_time"] = self.near_future_time

        self.rate_limiter.check_and_wait(self.mock_user_interface)

        # Should have called sleep with wait_time close to 10 seconds
        self.assertEqual(mock_sleep.call_count, 1)
        wait_time = mock_sleep.call_args[0][0]
        self.assertGreater(wait_time, 5)  # Allow for test execution time
        self.assertLess(wait_time, 15)  # Allow for test execution time

        # Should have notified user about requests limit
        self.mock_user_interface.handle_system_message.assert_called_once()
        message = self.mock_user_interface.handle_system_message.call_args[0][0]
        self.assertIn("requests", message.lower())

    @patch("time.sleep")
    def test_check_and_wait_no_reset_time(self, mock_sleep):
        """Test check_and_wait when no reset time is available"""
        # Setup rate limiter with low tokens remaining but no reset time
        self.rate_limiter.limits["tokens"]["remaining"] = 500
        self.rate_limiter.limits["tokens"]["reset_time"] = None

        self.rate_limiter.check_and_wait(self.mock_user_interface)

        # Should have used default wait time (60 seconds)
        mock_sleep.assert_called_once_with(60)

        # Should have notified user
        self.mock_user_interface.handle_system_message.assert_called_once()

    @patch("time.sleep")
    def test_check_and_wait_no_limits_approaching(self, mock_sleep):
        """Test check_and_wait when no limits are approaching"""
        # Setup rate limiter with plenty of everything
        self.rate_limiter.limits["tokens"]["remaining"] = 50000
        self.rate_limiter.limits["input_tokens"]["remaining"] = 25000
        self.rate_limiter.limits["output_tokens"]["remaining"] = 25000
        self.rate_limiter.limits["requests"]["remaining"] = 400

        self.rate_limiter.check_and_wait(self.mock_user_interface)

        # Should not have called sleep
        mock_sleep.assert_not_called()

        # Should not have notified user
        self.mock_user_interface.handle_system_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()

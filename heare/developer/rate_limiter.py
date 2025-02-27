import time
from datetime import datetime, timezone


class RateLimiter:
    def __init__(self):
        # Token-related limits
        self.tokens_limit = None
        self.tokens_remaining = None
        self.tokens_reset_time = None

        # Input token-related limits
        self.input_tokens_limit = None
        self.input_tokens_remaining = None
        self.input_tokens_reset_time = None

        # Output token-related limits
        self.output_tokens_limit = None
        self.output_tokens_remaining = None
        self.output_tokens_reset_time = None

        # Request-related limits
        self.requests_limit = None
        self.requests_remaining = None
        self.requests_reset_time = None

        # Error handling
        self.last_rate_limit_error = None
        self.backoff_time = 60  # Default backoff time in seconds
        self.retry_after = None

    def update(self, headers):
        # Update token limits
        if "anthropic-ratelimit-tokens-limit" in headers:
            self.tokens_limit = int(headers.get("anthropic-ratelimit-tokens-limit", 0))
        if "anthropic-ratelimit-tokens-remaining" in headers:
            self.tokens_remaining = int(
                headers.get("anthropic-ratelimit-tokens-remaining", 0)
            )
        if "anthropic-ratelimit-tokens-reset" in headers:
            reset_time_str = headers.get("anthropic-ratelimit-tokens-reset")
            if reset_time_str:
                self.tokens_reset_time = datetime.fromisoformat(reset_time_str).replace(
                    tzinfo=timezone.utc
                )

        # Update input token limits
        if "anthropic-ratelimit-input-tokens-limit" in headers:
            self.input_tokens_limit = int(
                headers.get("anthropic-ratelimit-input-tokens-limit", 0)
            )
        if "anthropic-ratelimit-input-tokens-remaining" in headers:
            self.input_tokens_remaining = int(
                headers.get("anthropic-ratelimit-input-tokens-remaining", 0)
            )
        if "anthropic-ratelimit-input-tokens-reset" in headers:
            reset_time_str = headers.get("anthropic-ratelimit-input-tokens-reset")
            if reset_time_str:
                self.input_tokens_reset_time = datetime.fromisoformat(
                    reset_time_str
                ).replace(tzinfo=timezone.utc)

        # Update output token limits
        if "anthropic-ratelimit-output-tokens-limit" in headers:
            self.output_tokens_limit = int(
                headers.get("anthropic-ratelimit-output-tokens-limit", 0)
            )
        if "anthropic-ratelimit-output-tokens-remaining" in headers:
            self.output_tokens_remaining = int(
                headers.get("anthropic-ratelimit-output-tokens-remaining", 0)
            )
        if "anthropic-ratelimit-output-tokens-reset" in headers:
            reset_time_str = headers.get("anthropic-ratelimit-output-tokens-reset")
            if reset_time_str:
                self.output_tokens_reset_time = datetime.fromisoformat(
                    reset_time_str
                ).replace(tzinfo=timezone.utc)

        # Update request limits
        if "anthropic-ratelimit-requests-limit" in headers:
            self.requests_limit = int(
                headers.get("anthropic-ratelimit-requests-limit", 0)
            )
        if "anthropic-ratelimit-requests-remaining" in headers:
            self.requests_remaining = int(
                headers.get("anthropic-ratelimit-requests-remaining", 0)
            )
        if "anthropic-ratelimit-requests-reset" in headers:
            reset_time_str = headers.get("anthropic-ratelimit-requests-reset")
            if reset_time_str:
                self.requests_reset_time = datetime.fromisoformat(
                    reset_time_str
                ).replace(tzinfo=timezone.utc)

        # Update retry-after if present
        if "retry-after" in headers:
            self.retry_after = int(headers.get("retry-after", 0))

    def handle_rate_limit_error(self, error):
        """Handle rate limit error by extracting information and setting backoff time"""
        self.last_rate_limit_error = error
        # If there are headers in the response, update our rate limit information
        if hasattr(error, "response") and hasattr(error.response, "headers"):
            self.update(error.response.headers)

        # First check if retry-after header is present - this is the most authoritative source
        if self.retry_after is not None and self.retry_after > 0:
            self.backoff_time = self.retry_after
            return self.backoff_time

        # Check for token reset times and use the earliest one
        current_time = datetime.now(timezone.utc)
        reset_times = []

        if self.tokens_reset_time:
            reset_times.append(self.tokens_reset_time)
        if self.input_tokens_reset_time:
            reset_times.append(self.input_tokens_reset_time)
        if self.output_tokens_reset_time:
            reset_times.append(self.output_tokens_reset_time)
        if self.requests_reset_time:
            reset_times.append(self.requests_reset_time)

        if reset_times:
            # Sort the reset times and use the earliest one
            earliest_reset = min(reset_times)
            self.backoff_time = max(3, (earliest_reset - current_time).total_seconds())
        else:
            # If no reset time information is available, use default backoff
            self.backoff_time = 60

        return self.backoff_time

    def check_and_wait(self, user_interface=None):
        # If we had a rate limit error recently, respect the backoff time
        if self.last_rate_limit_error and self.backoff_time > 0:
            message = f"Rate limit exceeded. Waiting for {self.backoff_time:.2f} seconds until reset."
            if user_interface:
                user_interface.handle_system_message(message)
            else:
                print(message)
            time.sleep(self.backoff_time)
            self.last_rate_limit_error = None
            self.backoff_time = 0
            return

        current_time = datetime.now(timezone.utc)
        low_threshold = 1000  # Threshold for considering a limit "approaching"

        # Check all types of limits and find the most restrictive one
        limit_checks = [
            # For total tokens
            (self.tokens_remaining, self.tokens_reset_time, "tokens"),
            # For input tokens
            (self.input_tokens_remaining, self.input_tokens_reset_time, "input tokens"),
            # For output tokens
            (
                self.output_tokens_remaining,
                self.output_tokens_reset_time,
                "output tokens",
            ),
            # For request limits - lower threshold for requests
            (self.requests_remaining, self.requests_reset_time, "requests", 5),
        ]

        for check in limit_checks:
            remaining, reset_time, limit_type = check[0], check[1], check[2]
            # Use a custom threshold if provided as 4th element, otherwise use default
            threshold = check[3] if len(check) > 3 else low_threshold

            if remaining is not None and remaining < threshold:
                if reset_time:
                    wait_time = max(0, (reset_time - current_time).total_seconds())
                    if wait_time > 0:
                        message = f"{limit_type.capitalize()} rate limit approaching ({remaining} remaining). Waiting for {wait_time:.2f} seconds until reset."
                        if user_interface:
                            user_interface.handle_system_message(message)
                        else:
                            print(message)
                        time.sleep(wait_time)
                        return
                else:
                    message = f"{limit_type.capitalize()} rate limit approaching ({remaining} remaining). Waiting for 60 seconds."
                    if user_interface:
                        user_interface.handle_system_message(message)
                    else:
                        print(message)
                    time.sleep(60)
                    return

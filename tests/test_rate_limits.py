import unittest

from src.limits import RateLimiter


class ControlledClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.clock = ControlledClock()
        self.limiter = RateLimiter(clock=self.clock)

    def test_allows_requests_up_to_the_limit(self):
        self.assertIsNone(self.limiter.check_request("client", 2))
        self.assertIsNone(self.limiter.check_request("client", 2))

    def test_returns_wait_until_the_oldest_request_expires(self):
        self.limiter.check_request("client", 2)
        self.limiter.check_request("client", 2)
        self.clock.advance(10)

        self.assertEqual(self.limiter.check_request("client", 2), 50)

    def test_allows_a_request_when_the_window_expires(self):
        self.limiter.check_request("client", 1)
        self.clock.advance(60)

        self.assertIsNone(self.limiter.check_request("client", 1))

    def test_keeps_limits_separate_by_key(self):
        self.limiter.check_request("first", 1)

        self.assertIsNone(self.limiter.check_request("second", 1))

"""
Unit tests for eformabot — no exchange connection needed.
Run: pytest tests/
"""

import pytest
from eformabot.strategy import FundingStrategy
from eformabot.risk import RiskManager


# ── Strategy tests ────────────────────────────────────────────────────────────

class TestFundingStrategy:
    def setup_method(self):
        self.s = FundingStrategy(entry_threshold=0.05, exit_threshold=0.01)

    def test_entry_above_threshold(self):
        assert self.s.should_enter(0.0006) is True   # 0.06% > 0.05%

    def test_no_entry_below_threshold(self):
        assert self.s.should_enter(0.0004) is False  # 0.04% < 0.05%

    def test_no_entry_at_zero(self):
        assert self.s.should_enter(0.0) is False

    def test_exit_when_funding_low(self):
        pos = {"side": "short", "entry_funding": 0.001}
        assert self.s.should_exit(0.00005, pos) is True  # 0.005% < 0.01% exit

    def test_exit_when_funding_negative(self):
        pos = {"side": "short", "entry_funding": 0.001}
        assert self.s.should_exit(-0.0001, pos) is True

    def test_no_exit_when_funding_still_high(self):
        pos = {"side": "short", "entry_funding": 0.001}
        assert self.s.should_exit(0.0003, pos) is False  # 0.03% still above 0.01%

    def test_annualized_yield(self):
        # 0.05% per 8h, 3x per day, 365 days
        yield_pct = self.s.annualized_yield(0.0005)
        assert abs(yield_pct - 54.75) < 0.01


# ── Risk manager tests ────────────────────────────────────────────────────────

class TestRiskManager:
    def setup_method(self):
        self.r = RiskManager(
            max_position_usd=100,
            max_open_positions=3,
            max_drawdown_pct=5.0,
            risk_per_trade_pct=1.0,
        )

    def test_can_open_when_clear(self):
        account = {"equity": 1000, "margin_used": 50}
        assert self.r.can_open_position({}, account) is True

    def test_blocked_when_max_positions(self):
        positions = {"BTC": {}, "ETH": {}, "SOL": {}}
        account = {"equity": 1000, "margin_used": 50}
        assert self.r.can_open_position(positions, account) is False

    def test_blocked_on_zero_equity(self):
        account = {"equity": 0, "margin_used": 0}
        assert self.r.can_open_position({}, account) is False

    def test_blocked_on_high_margin_utilization(self):
        account = {"equity": 1000, "margin_used": 850}
        assert self.r.can_open_position({}, account) is False

    def test_position_size_capped_at_max(self):
        # 1% of 50000 = 500, but max is 100
        size = self.r.position_size_usd(50000)
        assert size == 100.0

    def test_position_size_uses_risk_pct(self):
        # 1% of 500 = 5, below max of 100
        size = self.r.position_size_usd(500)
        assert size == 5.0

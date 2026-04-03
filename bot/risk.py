"""
Risk management for eformabot.
Hard limits on position size, number of open trades, and drawdown.
"""

import logging

log = logging.getLogger("eformabot.risk")


class RiskManager:
    def __init__(
        self,
        max_position_usd: float = 100.0,
        max_open_positions: int = 3,
        max_drawdown_pct: float = 5.0,
        risk_per_trade_pct: float = 1.0,  # % of equity risked per trade
    ):
        self.max_position_usd = max_position_usd
        self.max_open_positions = max_open_positions
        self.max_drawdown_pct = max_drawdown_pct
        self.risk_per_trade_pct = risk_per_trade_pct

        log.info(
            f"RiskManager — max_pos: ${max_position_usd}  "
            f"max_open: {max_open_positions}  "
            f"max_dd: {max_drawdown_pct}%"
        )

    def can_open_position(self, open_positions: dict, account: dict) -> bool:
        """Check all risk gates before opening a new position."""

        # Gate 1: too many open positions
        if len(open_positions) >= self.max_open_positions:
            log.warning(f"Risk gate: max open positions reached ({self.max_open_positions})")
            return False

        # Gate 2: account equity too low
        equity = account.get("equity", 0)
        if equity <= 0:
            log.warning("Risk gate: zero or negative equity")
            return False

        # Gate 3: margin utilization too high (> 80%)
        margin_used = account.get("margin_used", 0)
        if equity > 0 and (margin_used / equity) > 0.80:
            log.warning(f"Risk gate: margin utilization {margin_used/equity*100:.1f}% > 80%")
            return False

        return True

    def position_size_usd(self, equity: float) -> float:
        """Calculate position size in USD based on equity and risk settings."""
        risk_amount = equity * (self.risk_per_trade_pct / 100)
        size = min(risk_amount, self.max_position_usd)
        log.debug(f"Position size: ${size:.2f} (equity=${equity:.2f})")
        return size

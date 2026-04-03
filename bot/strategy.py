"""
Funding rate strategy for eformabot.

Logic:
  - ENTER short when funding > entry_threshold (you receive funding)
  - EXIT when funding < exit_threshold (edge gone) or position is in loss > stop_loss_pct
"""

import logging

log = logging.getLogger("eformabot.strategy")


class FundingStrategy:
    def __init__(
        self,
        entry_threshold: float = 0.05,   # % per 8h, e.g. 0.05 = 0.05%
        exit_threshold: float = 0.01,    # exit when funding drops below this
        stop_loss_pct: float = 2.0,       # exit if unrealized loss > 2%
        top_n: int = 5,
    ):
        # Convert pct to decimal if > 1 (convenience — accept both 0.05 and 5.0)
        self.entry_threshold = entry_threshold / 100 if entry_threshold > 1 else entry_threshold
        self.exit_threshold = exit_threshold / 100 if exit_threshold > 1 else exit_threshold
        self.stop_loss_pct = stop_loss_pct
        self.top_n = top_n

        log.info(
            f"Strategy configured — entry: {self.entry_threshold*100:.4f}%  "
            f"exit: {self.exit_threshold*100:.4f}%  "
            f"stop: {self.stop_loss_pct:.1f}%"
        )

    def should_enter(self, funding_rate: float) -> bool:
        """Return True if funding rate is high enough to warrant shorting."""
        if funding_rate >= self.entry_threshold:
            log.debug(f"Entry condition met: {funding_rate*100:.4f}% >= {self.entry_threshold*100:.4f}%")
            return True
        return False

    def should_exit(self, current_funding: float, position: dict) -> bool:
        """Return True if position should be closed."""
        # Funding normalized
        if current_funding < self.exit_threshold:
            log.debug(
                f"Exit — funding {current_funding*100:.4f}% < threshold {self.exit_threshold*100:.4f}%"
            )
            return True

        # Funding flipped negative (we'd be paying now)
        if current_funding < 0:
            log.debug(f"Exit — funding flipped negative: {current_funding*100:.4f}%")
            return True

        return False

    def annualized_yield(self, funding_rate: float, periods_per_day: int = 3) -> float:
        """Estimate annualized yield from a given funding rate (rough)."""
        return funding_rate * periods_per_day * 365 * 100

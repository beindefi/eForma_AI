"""
eformabot — Funding Rate Strategy
Scans top 5 HL perps by volume, shorts when funding is extreme, exits when it normalizes.
"""

import os
import json
import time
import logging
from datetime import datetime, timezone

from .exchange import HLExchange
from .strategy import FundingStrategy
from .risk import RiskManager
from .state import StateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("eformabot")


def run():
    log.info("═══ eformabot run starting ═══")

    exchange = HLExchange(
        wallet_address=os.environ["HL_WALLET_ADDRESS"],
        private_key=os.environ["HL_PRIVATE_KEY"],
        testnet=os.environ.get("HL_TESTNET", "true").lower() == "true",
    )

    risk = RiskManager(
        max_position_usd=float(os.environ.get("MAX_POSITION_USD", "100")),
        max_open_positions=int(os.environ.get("MAX_OPEN_POSITIONS", "3")),
        max_drawdown_pct=float(os.environ.get("MAX_DRAWDOWN_PCT", "5.0")),
    )

    strategy = FundingStrategy(
        entry_threshold=float(os.environ.get("FUNDING_ENTRY_THRESHOLD", "0.05")),
        exit_threshold=float(os.environ.get("FUNDING_EXIT_THRESHOLD", "0.01")),
        top_n=int(os.environ.get("TOP_N_COINS", "5")),
    )

    state = StateStore(path=os.environ.get("STATE_FILE", "state.json"))

    # ── 1. Fetch market data ──────────────────────────────────────────────────
    log.info("Fetching top coins and funding rates...")
    top_coins = exchange.get_top_coins_by_volume(n=strategy.top_n)
    log.info(f"Top {strategy.top_n} by volume: {[c['coin'] for c in top_coins]}")

    funding_rates = exchange.get_funding_rates([c["coin"] for c in top_coins])
    log.info("Funding rates: " + ", ".join(
        f"{k}={v*100:.4f}%" for k, v in funding_rates.items()
    ))

    # ── 2. Fetch account state ────────────────────────────────────────────────
    account = exchange.get_account_summary()
    log.info(f"Account equity: ${account['equity']:.2f}  Margin used: ${account['margin_used']:.2f}")

    open_positions = state.load()
    log.info(f"Tracked open positions: {list(open_positions.keys())}")

    # ── 3. Exit logic — close positions where funding has normalized ──────────
    for coin, pos in list(open_positions.items()):
        current_funding = funding_rates.get(coin, 0.0)
        if strategy.should_exit(current_funding, pos):
            log.info(f"EXIT signal for {coin} — funding now {current_funding*100:.4f}%")
            result = exchange.close_position(coin, pos)
            if result["success"]:
                pnl = result.get("realized_pnl", 0)
                log.info(f"  ✓ Closed {coin} | PnL: ${pnl:.4f}")
                state.remove(coin)
            else:
                log.warning(f"  ✗ Failed to close {coin}: {result['error']}")

    # ── 4. Entry logic — open shorts on high positive funding ─────────────────
    open_positions = state.load()  # reload after exits

    for coin_data in top_coins:
        coin = coin_data["coin"]

        if coin in open_positions:
            continue  # already in position

        funding = funding_rates.get(coin, 0.0)

        if not strategy.should_enter(funding):
            continue

        log.info(f"ENTRY signal for {coin} — funding {funding*100:.4f}% > threshold")

        # Risk checks
        if not risk.can_open_position(open_positions, account):
            log.warning("Risk limit reached — skipping new entries")
            break

        size_usd = risk.position_size_usd(account["equity"])
        price = exchange.get_mid_price(coin)
        size_contracts = round(size_usd / price, 4)

        log.info(f"  Placing short: {size_contracts} {coin} @ ~${price:.2f} (${size_usd:.2f})")
        result = exchange.place_order(
            coin=coin,
            side="sell",
            size=size_contracts,
            order_type="limit",
            price=round(price * 1.001, 2),  # small slippage buffer
            reduce_only=False,
        )

        if result["success"]:
            log.info(f"  ✓ Order placed | oid={result['order_id']}")
            state.add(coin, {
                "side": "short",
                "entry_funding": funding,
                "entry_price": price,
                "size": size_contracts,
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "order_id": result["order_id"],
            })
        else:
            log.warning(f"  ✗ Order failed: {result['error']}")

    # ── 5. Summary ────────────────────────────────────────────────────────────
    final_positions = state.load()
    log.info(f"Open positions after run: {list(final_positions.keys()) or 'none'}")
    log.info("═══ eformabot run complete ═══\n")


if __name__ == "__main__":
    run()

"""
Thin wrapper around the Hyperliquid Python SDK.
Handles all API calls: market data, account info, order placement.
"""

import logging
from typing import Optional

log = logging.getLogger("eformabot.exchange")

# SDK imports — install via: pip install hyperliquid-python-sdk
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
    import eth_account
except ImportError as e:
    raise ImportError(
        "hyperliquid-python-sdk not installed. Run: pip install hyperliquid-python-sdk"
    ) from e


class HLExchange:
    def __init__(self, wallet_address: str, private_key: str, testnet: bool = True):
        self.wallet_address = wallet_address
        self.testnet = testnet

        base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        log.info(f"Connecting to {'TESTNET' if testnet else 'MAINNET'} — {base_url}")

        self.account = eth_account.Account.from_key(private_key)
        self.info = Info(base_url, skip_ws=True)
        self.exchange = Exchange(self.account, base_url)

    # ── Market data ───────────────────────────────────────────────────────────

    def get_top_coins_by_volume(self, n: int = 5) -> list[dict]:
        """Return top N perp coins ranked by 24h volume."""
        meta = self.info.meta()
        universe = meta["universe"]

        # Fetch 24h stats for all perps
        stats = self.info.meta_and_asset_ctxs()
        asset_ctxs = stats[1]  # index 1 = asset contexts

        coins = []
        for i, asset in enumerate(universe):
            ctx = asset_ctxs[i] if i < len(asset_ctxs) else {}
            vol = float(ctx.get("dayNtlVlm", 0))
            coins.append({"coin": asset["name"], "volume_usd": vol})

        coins.sort(key=lambda x: x["volume_usd"], reverse=True)
        return coins[:n]

    def get_funding_rates(self, coins: list[str]) -> dict[str, float]:
        """Return current funding rate for each coin (as decimal, e.g. 0.0005 = 0.05%)."""
        meta_and_ctxs = self.info.meta_and_asset_ctxs()
        universe = meta_and_ctxs[0]["universe"]
        asset_ctxs = meta_and_ctxs[1]

        name_to_idx = {asset["name"]: i for i, asset in enumerate(universe)}
        rates = {}
        for coin in coins:
            idx = name_to_idx.get(coin)
            if idx is not None and idx < len(asset_ctxs):
                funding_str = asset_ctxs[idx].get("funding", "0")
                rates[coin] = float(funding_str)
        return rates

    def get_mid_price(self, coin: str) -> float:
        """Return current mid price for a coin."""
        l2 = self.info.l2_snapshot(coin)
        best_bid = float(l2["levels"][0][0]["px"])
        best_ask = float(l2["levels"][1][0]["px"])
        return (best_bid + best_ask) / 2

    def get_account_summary(self) -> dict:
        """Return account equity and margin info."""
        state = self.info.user_state(self.wallet_address)
        margin_summary = state.get("marginSummary", {})
        return {
            "equity": float(margin_summary.get("accountValue", 0)),
            "margin_used": float(margin_summary.get("totalMarginUsed", 0)),
            "raw": state,
        }

    # ── Order management ──────────────────────────────────────────────────────

    def place_order(
        self,
        coin: str,
        side: str,           # "buy" or "sell"
        size: float,
        order_type: str = "limit",
        price: Optional[float] = None,
        reduce_only: bool = False,
        slippage_pct: float = 0.1,
    ) -> dict:
        """Place a limit or market order. Returns {success, order_id, error}."""
        is_buy = side == "buy"

        try:
            if order_type == "market" or price is None:
                # Market order: use aggressive limit with slippage buffer
                mid = self.get_mid_price(coin)
                price = mid * (1 + slippage_pct / 100) if is_buy else mid * (1 - slippage_pct / 100)
                price = round(price, 2)

            order_result = self.exchange.order(
                coin,
                is_buy,
                size,
                price,
                {"limit": {"tif": "Gtc"}},
                reduce_only=reduce_only,
            )

            status = order_result.get("status")
            if status == "ok":
                oid = order_result["response"]["data"]["statuses"][0]
                order_id = oid.get("resting", {}).get("oid") or oid.get("filled", {}).get("oid")
                return {"success": True, "order_id": order_id, "raw": order_result}
            else:
                return {"success": False, "error": order_result, "order_id": None}

        except Exception as e:
            log.exception(f"Order placement failed for {coin}")
            return {"success": False, "error": str(e), "order_id": None}

    def close_position(self, coin: str, pos: dict) -> dict:
        """Close an existing position at market."""
        # Flip side to close
        close_side = "buy" if pos["side"] == "short" else "sell"
        return self.place_order(
            coin=coin,
            side=close_side,
            size=pos["size"],
            order_type="market",
            reduce_only=True,
        )

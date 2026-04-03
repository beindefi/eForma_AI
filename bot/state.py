"""
StateStore — persists open positions as a JSON file.

On GitHub Actions: commit state.json back to the repo after each run
so the next cron job can pick up where this one left off.
See the GitHub Actions workflow for the git commit step.
"""

import json
import os
import logging
from datetime import datetime, timezone

log = logging.getLogger("eformabot.state")


class StateStore:
    def __init__(self, path: str = "state.json"):
        self.path = path
        if not os.path.exists(self.path):
            self._write({})
            log.info(f"State file created: {self.path}")

    def load(self) -> dict:
        try:
            with open(self.path) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def add(self, coin: str, position: dict):
        state = self.load()
        state[coin] = position
        self._write(state)
        log.info(f"State: added {coin}")

    def remove(self, coin: str):
        state = self.load()
        if coin in state:
            del state[coin]
            self._write(state)
            log.info(f"State: removed {coin}")

    def _write(self, data: dict):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def summary(self) -> str:
        state = self.load()
        if not state:
            return "No open positions"
        lines = [f"{coin}: {pos['side']} @ ${pos['entry_price']:.2f}" for coin, pos in state.items()]
        return " | ".join(lines)

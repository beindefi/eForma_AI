# eForma_AI

Autonomous funding rate trading bot for Hyperliquid perpetuals powered by virtual-aGDP.

## Strategy

Every 5 minutes eFormabot:
1. Fetches the top 5 perps by 24h volume
2. Reads current funding rates for each
3. **Shorts** any coin with funding above the entry threshold (you *receive* funding payments)
4. **Closes** positions when funding normalizes below the exit threshold
5. Persists state between runs by committing `state.json` back to the repo

At 0.05% funding per 8h, that's ~54% annualized yield on the position — with near-zero directional risk since you're not holding a naked long.

## Repo structure

```
eformabot/
├── eformabot/
│   ├── bot.py        — main run loop
│   ├── exchange.py   — Hyperliquid SDK wrapper
│   ├── strategy.py   — funding rate entry/exit logic
│   ├── risk.py       — position sizing + risk gates
│   └── state.py      — JSON state persistence
├── tests/
│   └── test_bot.py
├── .github/workflows/
│   └── bot.yml       — cron schedule + commit state back
├── main.py           — entry point
├── state.json        — tracks open positions (committed to repo)
└── requirements.txt
```

## Setup

### 1. Fork / clone this repo

```bash
git clone https://github.com/you/eformabot
cd eformabot
```

### 2. Creating a Hyperliquid wallet

- Go to [app.hyperliquid.xyz](https://app.hyperliquid.xyz)
- Create and/or import a wallet
- **Start on testnet** — set `HL_TESTNET=true` 
- Fund with testnet USDC (faucet available in the HL app)

### 3. Add GitHub Secrets

See ==> Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|-------|
| `HL_WALLET_ADDRESS` | Ethereum wallet address (0x...) |
| `HL_PRIVATE_KEY` | Wallet private key |
| `GH_PAT` | GitHub Personal Access Token with `repo` scope (needed to commit state.json) |

Create the PAT at: github.com → Settings → Developer settings → Personal access tokens → Fine-grained tokens

### 4. Configure variables (optional)

In Settings → Variables → Actions (these have safe defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `HL_TESTNET` | `true` | Set to `false` for mainnet |
| `MAX_POSITION_USD` | `100` | Max size per trade in USD |
| `MAX_OPEN_POSITIONS` | `3` | Max concurrent open trades |
| `MAX_DRAWDOWN_PCT` | `5.0` | Emergency stop drawdown % |
| `FUNDING_ENTRY_THRESHOLD` | `0.05` | Min funding rate to enter (%) |
| `FUNDING_EXIT_THRESHOLD` | `0.01` | Funding rate to trigger exit (%) |
| `TOP_N_COINS` | `5` | How many top coins to scan |

### 5. Enable the workflow

- Push to GitHub — the workflow appears under the Actions tab
- Trigger a manual run first via "Run workflow" to verify it works
- It will then run automatically every 5 minutes

## Running locally

```bash
pip install -r requirements.txt

export HL_WALLET_ADDRESS=0x...
export HL_PRIVATE_KEY=0x...
export HL_TESTNET=true

python main.py
```

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

## How state persistence works

Since gitHub Actions runners are ephemeral (they're destroyed after each run). eFormabot persists open position data in `state.json`, which the workflow commits back to the repo after every run. The next cron job clones the repo and gets the latest state automatically.

This means an open positions survive across runs at zero cost. The only tradeoff: there's a ~5 second git commit at the end of each run.

## Safety notes

- Always test on **testnet** first (`HL_TESTNET=true`)
- Start with small `MAX_POSITION_USD` (e.g. $50)
- The bot only opens **short** positions to receive funding — it does not hold directional longs
- No leverage is explicitly set; HL defaults to cross margin. Consider setting isolated margin manually for extra safety
- Monitor your positions at [app.hyperliquid.xyz](https://app.hyperliquid.xyz)

## License

MIT

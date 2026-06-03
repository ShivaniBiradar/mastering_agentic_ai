## Week 1 — Card Optimizer

A responsive web app for maximizing credit card points across Chase Sapphire Preferred and Capital One Venture X as examples.

### Features

- **Card Picker** — tap a spend category, instantly see which card earns the most
- **Statement Analyzer** — upload a CSV statement; AI categorizes every merchant and shows missed points plus a new-card recommendation based on your actual spending
- **My Wallet** — track point balances, expiry status, transfer-partner optimizer (e.g. Hyatt 2.3¢, Turkish 1.8¢), and a redemption goal tracker
- **Insights** — annual fee ROI, sign-up bonus progress tracker, rotating category alerts

### Prerequisites

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager

Install `uv` if you don't have it:
```bash
brew install uv
```

### Setup

```bash
cd card-optimizer

# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Configure your API key
cp .env.example .env
# Open .env and paste your Anthropic API key
```

### Run

```bash
uv run python server.py
```

Then open [http://localhost:3000](http://localhost:3000) in your browser.

To use a different port:
```bash
PORT=8080 uv run python server.py
```

### Notes

- The `ANTHROPIC_API_KEY` in `.env` is used for AI transaction categorization in the Analyzer tab and for pulling the latest information on transfer partner programs for credit cards.
- Without an API key, the Analyzer falls back to keyword-based categorization — it still works for common merchants.
- The `.env` file is gitignored — your key will never be committed.

#TODO: (This feature needs to be modified)
- On mobile: open `http://<your-local-ip>:3000` on your phone while on the same Wi-Fi network.
 - Switch out the CSV sample data with secure Plaid integration that can pull live data from the banks

# Base Market Data — x402 Paid API

Real-time market data for Base (and other chains): token prices, trending tokens, and gas prices. Paid via x402 (USDC on Base).

## Endpoints

| Method | Path | Price | Description |
|--------|------|-------|-------------|
| GET | /health | Free | Health check |
| GET | /token?address=0x... | 0.0005 USDC | Token price, liquidity, volume, price change |
| GET | /trending | 0.0005 USDC | Top trending tokens on Base (by volume) |
| GET | /gas | 0.0005 USDC | Current Base gas price (gwei) |

## Data Sources
- DexScreener API (free, no key required)
- Base RPC (public)

## Payment
- Network: Base Mainnet (eip155:8453)
- Asset: USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
- PayTo: 0x65aa59025C4AcD8CD7ba2051ecb9152abaE4fcC6
- Price: 0.0005 USDC per call

## Usage

curl https://promptly-rep-mile-thin.trycloudflare.com/health

curl "https://promptly-rep-mile-thin.trycloudflare.com/token?address=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" \
  -H "X-PAYMENT: <base64-encoded-payment-proof>"

curl https://promptly-rep-mile-thin.trycloudflare.com/trending \
  -H "X-PAYMENT: <base64-encoded-payment-proof>"

curl https://promptly-rep-mile-thin.trycloudflare.com/gas \
  -H "X-PAYMENT: <base64-encoded-payment-proof>"

## Tech Stack
- Python 3 (stdlib only — no external dependencies)
- DexScreener API (free)
- Base RPC (public)
- x402 payment protocol

## License
MIT
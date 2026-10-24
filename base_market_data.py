#!/usr/bin/env python3
"""Base Market Data — x402-gated crypto market data for Base chain tokens."""
import json, os, time, urllib.request, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", "8820"))
PAY_TO = "0x65aa59025C4AcD8CD7ba2051ecb9152abaE4fcC6"
PRICE_USDC = 0.0005
PRICE_UNITS = int(PRICE_USDC * 1e6)
CHAIN_ID = 8453
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
USED_TXS_FILE = os.path.join(os.path.dirname(__file__), "used_txs.json")

def load_used_txs():
    try:
        with open(USED_TXS_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_used_txs(s):
    with open(USED_TXS_FILE, "w") as f:
        json.dump(sorted(s), f)

def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "base-market-data/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def get_token_data(address):
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    data = fetch_json(url)
    pairs = data.get("pairs", [])
    if not pairs:
        return {"error": "no_pairs_found", "address": address}
    best = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
    base = best.get("baseToken", {})
    return {
        "token": {"address": base.get("address"), "name": base.get("name"), "symbol": base.get("symbol")},
        "price_usd": best.get("priceUsd"),
        "price_change_24h": best.get("priceChange", {}).get("h24"),
        "volume_24h_usd": best.get("volume", {}).get("h24"),
        "liquidity_usd": best.get("liquidity", {}).get("usd"),
        "market_cap": best.get("marketCap"),
        "dex": best.get("dexId"),
        "updated_at": int(time.time()),
    }

def get_trending_base():
    url = "https://api.dexscreener.com/latest/dex/search?q=base"
    data = fetch_json(url)
    pairs = [p for p in data.get("pairs", []) if p.get("chainId") == "base"]
    pairs.sort(key=lambda p: float(p.get("volume", {}).get("h24", 0) or 0), reverse=True)
    results = []
    for p in pairs[:20]:
        base = p.get("baseToken", {})
        results.append({
            "address": base.get("address"), "name": base.get("name"), "symbol": base.get("symbol"),
            "price_usd": p.get("priceUsd"), "volume_24h_usd": p.get("volume", {}).get("h24"),
            "price_change_24h": p.get("priceChange", {}).get("h24"),
            "liquidity_usd": p.get("liquidity", {}).get("usd"), "dex": p.get("dexId"),
        })
    return {"chain": "base", "trending": results, "count": len(results), "updated_at": int(time.time())}

def get_gas_price():
    payload = json.dumps({"jsonrpc": "2.0", "method": "eth_gasPrice", "params": [], "id": 1}).encode()
    req = urllib.request.Request("https://mainnet.base.org", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    gas_wei = int(data["result"], 16)
    return {"gas_price_wei": gas_wei, "gas_price_gwei": round(gas_wei / 1e9, 4), "chain": "base", "updated_at": int(time.time())}

def verify_tx(tx_hash):
    payload = json.dumps({"jsonrpc": "2.0", "method": "eth_getTransactionReceipt", "params": [tx_hash], "id": 1}).encode()
    req = urllib.request.Request("https://mainnet.base.org", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
    receipt = data.get("result")
    if not receipt or receipt.get("status") != "0x1":
        return False, "tx_not_found_or_failed"
    for log in receipt.get("logs", []):
        if log.get("address", "").lower() == ASSET.lower():
            topics = log.get("topics", [])
            if len(topics) >= 3 and topics[0].lower() == "0x<redacted-64>":
                to_addr = "0x" + topics[2][-40:]
                if to_addr.lower() == PAY_TO.lower():
                    amount = int(log.get("data", "0x0"), 16)
                    if amount >= PRICE_UNITS:
                        return True, "verified"
    return False, "no_matching_transfer"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/health":
            self.send_json(200, {"status": "ok", "service": "base-market-data", "price_usdc": PRICE_USDC, "chain": "base"})
            return

        tx_hash = self.headers.get("X-Payment-Tx", "").strip()
        if not tx_hash:
            self.send_json(402, {"error": "payment_required", "message": f"Pay {PRICE_USDC} USDC on Base to {PAY_TO}",
                "pay_to": PAY_TO, "asset": ASSET, "chain": "base", "chain_id": CHAIN_ID,
                "amount_usdc": PRICE_USDC, "amount_units": PRICE_UNITS,
                "instructions": "Send USDC on Base to pay_to, then retry with X-Payment-Tx: <tx_hash>"})
            return

        used = load_used_txs()
        if tx_hash in used:
            self.send_json(402, {"error": "tx_already_used"})
            return
        ok, reason = verify_tx(tx_hash)
        if not ok:
            self.send_json(402, {"error": "payment_not_verified", "reason": reason})
            return
        used.add(tx_hash)
        save_used_txs(used)

        try:
            if path == "/token":
                addr = params.get("address", [""])[0]
                if not addr:
                    self.send_json(400, {"error": "missing_address", "usage": "/token?address=0x..."})
                    return
                self.send_json(200, get_token_data(addr))
            elif path == "/trending":
                self.send_json(200, get_trending_base())
            elif path == "/gas":
                self.send_json(200, get_gas_price())
            else:
                self.send_json(404, {"error": "not_found", "endpoints": ["/health", "/token?address=0x...", "/trending", "/gas"]})
        except Exception as e:
            self.send_json(500, {"error": "internal_error", "message": str(e)})

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass

if __name__ == "__main__":
    print(f"Base Market Data starting on port {PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

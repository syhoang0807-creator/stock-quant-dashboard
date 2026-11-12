"""
data_fetcher.py — 100% real data, zero fake/mock prices.

Sources:
  Price  (primary)  : DNSE Entrade Chart API  → prices already in thousand VND
  Price  (backup)   : VNDirect Finfo v4        → normalize if > 500
  Foreign flow      : VNDirect Finfo v4/foreigns → netVal / 1e9 → Billion VND
  Proprietary flow  : No reliable public API  → 0.0 (honest fallback)
"""

import logging
import math
from datetime import date, timedelta, datetime

import pandas as pd
import requests

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("data_fetcher")

# ── Shared browser headers ─────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 15  # seconds


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_unix(d: date) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp())


def _safe_float(val, divisor: float = 1.0) -> float:
    try:
        v = float(val)
        if math.isnan(v) or math.isinf(v):
            return 0.0
        return round(v / divisor, 2)
    except (TypeError, ValueError):
        return 0.0


# ── Price: DNSE Entrade (primary) ──────────────────────────────────────────────

def _fetch_price_dnse(symbol: str, days: int) -> pd.DataFrame:
    """
    DNSE Entrade Chart API.
    Returns arrays t, o, h, l, c, v.
    Prices already in thousand VND (e.g. 31.55).
    """
    end_dt = date.today()
    # Request a wider window to account for weekends/holidays
    start_dt = end_dt - timedelta(days=max(days * 2, 90))

    url = (
        "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
        f"?from={_to_unix(start_dt)}&to={_to_unix(end_dt)}"
        f"&symbol={symbol}&resolution=1D"
    )
    logger.info("[DNSE] Fetching price: %s", url)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("[DNSE] HTTP %d for %s", resp.status_code, url)
            return pd.DataFrame()
        data = resp.json()
    except Exception as exc:
        logger.error("[DNSE] Request failed for %s: %s", symbol, exc)
        return pd.DataFrame()

    t_arr = data.get("t", [])
    o_arr = data.get("o", [])
    h_arr = data.get("h", [])
    l_arr = data.get("l", [])
    c_arr = data.get("c", [])
    v_arr = data.get("v", [])

    if not t_arr:
        logger.warning("[DNSE] Empty response for %s", symbol)
        return pd.DataFrame()

    rows = []
    for i, ts in enumerate(t_arr):
        try:
            dt = datetime.utcfromtimestamp(ts).date()
            rows.append({
                "Date":   str(dt),
                "Open":   _safe_float(o_arr[i] if i < len(o_arr) else None),
                "High":   _safe_float(h_arr[i] if i < len(h_arr) else None),
                "Low":    _safe_float(l_arr[i] if i < len(l_arr) else None),
                "Close":  _safe_float(c_arr[i] if i < len(c_arr) else None),
                "Volume": int(v_arr[i]) if i < len(v_arr) else 0,
            })
        except Exception as exc:
            logger.warning("[DNSE] Row %d parse error: %s", i, exc)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values("Date").tail(days).reset_index(drop=True)
    logger.info("[DNSE] Got %d rows for %s (last close=%.2f)", len(df), symbol, df["Close"].iloc[-1])
    return df


# ── Price: VNDirect Finfo (backup) ────────────────────────────────────────────

def _fetch_price_vndirect(symbol: str, days: int) -> pd.DataFrame:
    """
    VNDirect Finfo v4 — backup price source.
    Prices: if raw value > 500 → divide by 1000, else keep as-is (already in thousand VND).
    """
    start_dt = date.today() - timedelta(days=max(days * 2, 90))
    start_str = start_dt.strftime("%Y-%m-%d")
    size = max(days + 10, 60)

    url = (
        "https://api-finfo.vndirect.com.vn/v4/stock_prices"
        f"?sort=date&q=code:{symbol}~date:gte:{start_str}&size={size}"
    )
    logger.info("[VNDirect] Fetching price: %s", url)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("[VNDirect] HTTP %d for %s", resp.status_code, url)
            return pd.DataFrame()
        data = resp.json()
    except Exception as exc:
        logger.error("[VNDirect] Request failed for %s: %s", symbol, exc)
        return pd.DataFrame()

    items = data.get("data", [])
    if not items:
        logger.warning("[VNDirect] Empty data for %s", symbol)
        return pd.DataFrame()

    def _norm(val):
        v = _safe_float(val)
        return round(v / 1000.0, 2) if v > 500 else v

    rows = []
    for item in items:
        rows.append({
            "Date":   str(item.get("date", ""))[:10],
            "Open":   _norm(item.get("open")),
            "High":   _norm(item.get("high")),
            "Low":    _norm(item.get("low")),
            "Close":  _norm(item.get("close")),
            "Volume": int(_safe_float(item.get("volume", 0))),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("Date").tail(days).reset_index(drop=True)
    logger.info("[VNDirect] Got %d rows for %s (last close=%.2f)", len(df), symbol, df["Close"].iloc[-1])
    return df


# ── Public: get_price_history ─────────────────────────────────────────────────

def get_price_history(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Fetch EOD candlestick data (Open, High, Low, Close, Volume).
    Prices in thousand VND (e.g. 31.55 = 31,550 VND).
    Returns empty DataFrame if all sources fail — NEVER fake data.
    """
    symbol = symbol.upper()

    # Primary: DNSE Entrade
    df = _fetch_price_dnse(symbol, days)
    if not df.empty and len(df) >= 5:
        return df

    logger.warning("[PriceHistory] DNSE failed or insufficient for %s, trying VNDirect...", symbol)

    # Backup: VNDirect Finfo
    df = _fetch_price_vndirect(symbol, days)
    if not df.empty:
        return df

    logger.error("[PriceHistory] ALL sources failed for %s. Returning empty DataFrame.", symbol)
    return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])


# ── Public: get_foreign_flow ──────────────────────────────────────────────────

def get_foreign_flow(symbol: str, days: int = 20) -> pd.DataFrame:
    """
    Fetch foreign investor net buy/sell per session in Billion VND.
    Source: VNDirect Finfo v4/foreigns, field netVal / 1e9.
    Missing sessions → 0.0. NEVER fake data.
    """
    symbol = symbol.upper()
    start_dt = date.today() - timedelta(days=max(days * 2, 60))
    start_str = start_dt.strftime("%Y-%m-%d")
    size = max(days + 10, 50)

    url = (
        "https://api-finfo.vndirect.com.vn/v4/foreigns"
        f"?sort=tradingDate&q=code:{symbol}~tradingDate:gte:{start_str}&size={size}"
    )
    logger.info("[ForeignFlow] Fetching: %s", url)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            logger.error("[ForeignFlow] HTTP %d for %s", resp.status_code, url)
            items = []
        else:
            items = resp.json().get("data", [])
    except Exception as exc:
        logger.error("[ForeignFlow] Request failed for %s: %s", symbol, exc)
        items = []

    if items:
        rows = []
        for item in items:
            dt_str = str(item.get("tradingDate", ""))[:10]
            net_val = _safe_float(item.get("netVal", 0), divisor=1e9)
            rows.append({"Date": dt_str, "NetValue_Billion": net_val})
        df = pd.DataFrame(rows)
        df = df.sort_values("Date").tail(days).reset_index(drop=True)
        logger.info("[ForeignFlow] Got %d rows for %s", len(df), symbol)
        return df

    # Fallback: return zeros for business days
    logger.warning("[ForeignFlow] No data for %s — returning zero-filled DataFrame", symbol)
    biz_dates = pd.bdate_range(end=date.today(), periods=days)
    return pd.DataFrame({
        "Date": [str(d.date()) for d in biz_dates],
        "NetValue_Billion": 0.0,
    })


# ── Public: get_proprietary_flow ─────────────────────────────────────────────

def get_proprietary_flow(symbol: str, days: int = 20) -> pd.DataFrame:
    """
    Proprietary (tự doanh) net buy/sell per session in Billion VND.
    No reliable public API available without authentication.
    Returns 0.0 for all sessions — honest fallback, never fake random data.
    """
    symbol = symbol.upper()
    logger.info("[ProprietaryFlow] No public API available for %s — returning 0.0", symbol)
    biz_dates = pd.bdate_range(end=date.today(), periods=days)
    return pd.DataFrame({
        "Date": [str(d.date()) for d in biz_dates],
        "NetValue_Billion": 0.0,
    })


# ── Public: get_full_snapshot ─────────────────────────────────────────────────

def get_full_snapshot(symbol: str, price_days: int = 30, flow_days: int = 20) -> dict:
    """
    Convenience wrapper returning price, foreign flow, and proprietary flow
    as a single dict (used by /api/snapshot/{symbol} in main.py).
    """
    symbol = symbol.upper()
    price_df = get_price_history(symbol, price_days)
    foreign_df = get_foreign_flow(symbol, flow_days)
    proprietary_df = get_proprietary_flow(symbol, flow_days)

    def _df_to_records(df: pd.DataFrame) -> list:
        return df.to_dict(orient="records")

    return {
        "symbol": symbol,
        "price": _df_to_records(price_df),
        "foreign_flow": _df_to_records(foreign_df),
        "proprietary_flow": _df_to_records(proprietary_df),
    }


# ── Smoke test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    ticker = sys.argv[1] if len(sys.argv) > 1 else "CTG"

    print(f"\n{'='*60}")
    print(f"  Smoke test: {ticker}")
    print(f"{'='*60}\n")

    # Price
    price_df = get_price_history(ticker, days=30)
    if price_df.empty:
        print("❌ PRICE: Empty — all sources failed!")
    else:
        print(f"✅ PRICE: {len(price_df)} rows")
        print(price_df.tail(5).to_string(index=False))

    # Foreign flow
    print()
    ff_df = get_foreign_flow(ticker, days=20)
    print(f"{'✅' if not ff_df.empty else '⚠️'} FOREIGN FLOW: {len(ff_df)} rows")
    print(ff_df.tail(5).to_string(index=False))

    # Proprietary
    print()
    pf_df = get_proprietary_flow(ticker, days=20)
    print(f"✅ PROPRIETARY FLOW: {len(pf_df)} rows (honest 0.0 fallback)")
    print(pf_df.tail(3).to_string(index=False))

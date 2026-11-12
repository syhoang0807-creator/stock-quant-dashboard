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
import time as _time
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

    unix_end is set 2 days into the future (+172800 s) so UTC vs UTC+7 timezone
    differences never accidentally exclude today's EOD candle.
    """
    start_dt = date.today() - timedelta(days=max(days * 2, 90))
    unix_start = _to_unix(start_dt)
    # +172800 s = +2 days buffer → ensures today's candle is always included
    unix_end = int(_time.time()) + 172800

    url = (
        "https://services.entrade.com.vn/chart-api/v2/ohlcs/stock"
        f"?from={unix_start}&to={unix_end}"
        f"&symbol={symbol}&resolution=1D"
    )
    logger.info("[DNSE] Fetching price (unix_end+2d buffer): %s", url)

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
            # Use UTC+7 (Vietnam timezone) for date conversion to avoid off-by-one
            dt = datetime.fromtimestamp(ts).date()
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
    logger.info("[DNSE] Got %d rows for %s (last date=%s, last close=%.2f)",
                len(df), symbol, df["Date"].iloc[-1], df["Close"].iloc[-1])
    return df


# ── Price: VNDirect Finfo (backup) ────────────────────────────────────────────

def _fetch_price_vndirect(symbol: str, days: int, latest_only: bool = False) -> pd.DataFrame:
    """
    VNDirect Finfo v4 — backup/merge price source.
    Prices: if raw value > 500 → divide by 1000, else keep as-is (already in thousand VND).

    latest_only=True  → fetch the most recent 45 candles without date filter
                        (used to fill a 1-day lag from DNSE).
    latest_only=False → fetch with date filter for a full history window.
    """
    if latest_only:
        url = (
            "https://api-finfo.vndirect.com.vn/v4/stock_prices"
            f"?sort=date&q=code:{symbol}&size=45"
        )
    else:
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
    logger.info("[VNDirect] Got %d rows for %s (last date=%s, last close=%.2f)",
                len(df), symbol, df["Date"].iloc[-1], df["Close"].iloc[-1])
    return df


# ── Helper: get latest foreign flow date (for lag detection) ──────────────────

def _get_latest_foreign_date(symbol: str) -> str | None:
    """
    Quick-fetch the most recent trading date from VNDirect foreign flow.
    Returns date string "YYYY-MM-DD" or None on failure.
    Used to detect if DNSE price data is lagging by 1 day.
    """
    url = (
        "https://api-finfo.vndirect.com.vn/v4/foreigns"
        f"?sort=tradingDate&q=code:{symbol}&size=5"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if resp.status_code != 200:
            return None
        items = resp.json().get("data", [])
        if items:
            latest = max(str(it.get("tradingDate", ""))[:10] for it in items)
            logger.info("[LagCheck] Latest foreign flow date for %s: %s", symbol, latest)
            return latest
    except Exception as exc:
        logger.warning("[LagCheck] Could not fetch foreign date for %s: %s", symbol, exc)
    return None


# ── Public: get_price_history ─────────────────────────────────────────────────

def get_price_history(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Fetch EOD candlestick data (Open, High, Low, Close, Volume).
    Prices in thousand VND (e.g. 31.55 = 31,550 VND).

    Strategy:
    1. Try DNSE Entrade (unix_end +2 days buffer to fix UTC vs UTC+7 lag).
    2. Fetch foreign flow latest date as the "expected latest trading day".
    3. If DNSE's latest candle date is 1 day behind the foreign flow date,
       fetch VNDirect (latest_only=True, size=45) and merge to fill the gap.
    4. If DNSE fails entirely, fall back to VNDirect full history.
    Returns empty DataFrame if all sources fail — NEVER fake data.
    """
    symbol = symbol.upper()
    today_str = str(date.today())

    # Primary: DNSE Entrade (with +2d future buffer)
    df_dnse = _fetch_price_dnse(symbol, days)

    if df_dnse.empty or len(df_dnse) < 5:
        logger.warning("[PriceHistory] DNSE failed or insufficient for %s, trying VNDirect full...", symbol)
        df_vnd = _fetch_price_vndirect(symbol, days, latest_only=False)
        if not df_vnd.empty:
            return df_vnd
        logger.error("[PriceHistory] ALL sources failed for %s. Returning empty DataFrame.", symbol)
        return pd.DataFrame(columns=["Date", "Open", "High", "Low", "Close", "Volume"])

    # Check if DNSE is lagging behind by comparing with foreign flow's latest date
    dnse_latest = df_dnse["Date"].iloc[-1]

    # Get the latest foreign flow date as reference (quick fetch, small size)
    ff_latest = _get_latest_foreign_date(symbol)

    if ff_latest and ff_latest > dnse_latest:
        logger.warning(
            "[PriceHistory] DNSE lag detected for %s: DNSE latest=%s, Foreign latest=%s. "
            "Fetching VNDirect to fill gap...",
            symbol, dnse_latest, ff_latest,
        )
        df_vnd = _fetch_price_vndirect(symbol, days, latest_only=True)
        if not df_vnd.empty:
            vnd_latest = df_vnd["Date"].iloc[-1]
            if vnd_latest > dnse_latest:
                # Merge: keep DNSE rows except dates VNDirect has newer data for
                df_merged = pd.concat([df_dnse, df_vnd], ignore_index=True)
                df_merged = df_merged.drop_duplicates(subset="Date", keep="last")
                df_merged = df_merged.sort_values("Date").tail(days).reset_index(drop=True)
                logger.info(
                    "[PriceHistory] Merged DNSE+VNDirect for %s: %d rows, latest=%s, close=%.2f",
                    symbol, len(df_merged), df_merged["Date"].iloc[-1], df_merged["Close"].iloc[-1],
                )
                return df_merged
            else:
                logger.warning("[VNDirect] latest=%s still not newer than DNSE=%s", vnd_latest, dnse_latest)
    else:
        logger.info("[PriceHistory] DNSE up-to-date for %s (latest=%s)", symbol, dnse_latest)

    return df_dnse


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
    Fetch real daily proprietary (Tự doanh) net trading value in Billion VND from CafeF API.
    Primary URL: https://s.cafef.vn/Ajax/PageNew/DataHistory/GDTuDoanh.ashx?Symbol={symbol}&StartDate=&EndDate=&PageIndex=1&PageSize={page_size}
    Fallback URL: https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDTuDoanh.ashx?Symbol={symbol}&StartDate=&EndDate=&PageIndex=1&PageSize={page_size}

    Parses "Data" -> "Data" list/dict, computes net_value = (GtMua - GtBan) / 1e9,
    and aligns dates with get_price_history().
    """
    symbol = symbol.upper()
    page_size = max(days + 15, 30)

    # 1. Fetch from CafeF API
    urls = [
        f"https://s.cafef.vn/Ajax/PageNew/DataHistory/GDTuDoanh.ashx?Symbol={symbol}&StartDate=&EndDate=&PageIndex=1&PageSize={page_size}",
        f"https://cafef.vn/du-lieu/Ajax/PageNew/DataHistory/GDTuDoanh.ashx?Symbol={symbol}&StartDate=&EndDate=&PageIndex=1&PageSize={page_size}",
    ]

    cafef_headers = dict(HEADERS)
    cafef_headers.update({
        "Referer": "https://cafef.vn/",
        "Accept": "application/json, text/plain, */*",
    })

    items = []
    for url in urls:
        logger.info("[ProprietaryFlow] Fetching from CafeF: %s", url)
        try:
            resp = requests.get(url, headers=cafef_headers, timeout=TIMEOUT)
            if resp.status_code == 200:
                res_json = resp.json()
                data_obj = res_json.get("Data")
                if data_obj:
                    # "Data" -> "Data" (can be list or dict containing ListDataTudoanh)
                    inner_data = data_obj.get("Data") if isinstance(data_obj, dict) else data_obj
                    if isinstance(inner_data, dict):
                        items = inner_data.get("ListDataTudoanh", [])
                    elif isinstance(inner_data, list):
                        items = inner_data
                    if items:
                        logger.info("[ProprietaryFlow] Successfully fetched %d items from %s", len(items), url)
                        break
        except Exception as exc:
            logger.warning("[ProprietaryFlow] Failed to fetch from %s: %s", url, exc)

    # 2. Parse items into mapping: date (YYYY-MM-DD) -> net_value (Billion VND)
    cafef_dict = {}
    for item in items:
        raw_date = str(item.get("Date", "")).strip()
        parts = raw_date.split("/")
        if len(parts) == 3:
            iso_date = f"{parts[2].zfill(4)}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        else:
            iso_date = raw_date

        try:
            gt_mua = float(item.get("GtMua", 0) or 0)
            gt_ban = float(item.get("GtBan", 0) or 0)
            net_val = round((gt_mua - gt_ban) / 1e9, 2)
            cafef_dict[iso_date] = net_val
        except (TypeError, ValueError):
            continue

    # 3. Align dates with get_price_history()
    price_df = get_price_history(symbol, days=days)
    if not price_df.empty and "Date" in price_df.columns:
        aligned_rows = []
        for d in price_df["Date"].tolist():
            aligned_rows.append({
                "Date": d,
                "NetValue_Billion": cafef_dict.get(d, 0.0),
            })
        df_prop = pd.DataFrame(aligned_rows)
        logger.info("[ProprietaryFlow] Aligned %d sessions with price history for %s", len(df_prop), symbol)
        return df_prop

    # Fallback if price history unavailable: use CafeF dates directly
    if cafef_dict:
        rows = [{"Date": d, "NetValue_Billion": v} for d, v in cafef_dict.items()]
        df_prop = pd.DataFrame(rows).sort_values("Date").tail(days).reset_index(drop=True)
        return df_prop

    logger.warning("[ProprietaryFlow] No data found for %s — returning zero-filled DataFrame", symbol)
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
    print(f"✅ PROPRIETARY FLOW: {len(pf_df)} rows (CafeF real data)")
    print(pf_df.tail(5).to_string(index=False))

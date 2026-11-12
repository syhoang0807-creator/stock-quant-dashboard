"""
data_fetcher.py
===============
Module cào dữ liệu chứng khoán Việt Nam.

Thứ tự ưu tiên nguồn dữ liệu:
  1. vnstock (SSI / TCBS / VCI adapters)
  2. TCBS REST API (public, không cần key)
  3. Mock data thực tế (fallback cuối cùng)

Tất cả hàm public đều trả về pandas.DataFrame chuẩn hoá.
"""

from __future__ import annotations

import logging
import random
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("data_fetcher")

# ── Constants ─────────────────────────────────────────────────────────────────
TCBS_BASE = "https://apipubaws.tcbs.com.vn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
}
REQUEST_TIMEOUT = 10  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PRICE HISTORY
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_price_via_vnstock(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Thử lấy dữ liệu giá qua vnstock v3 (Vnstock().stock, source KBS)."""
    try:
        from vnstock import Vnstock  # type: ignore

        end_date = date.today().strftime("%Y-%m-%d")
        start_date = (date.today() - timedelta(days=days + 10)).strftime("%Y-%m-%d")

        stock = Vnstock().stock(symbol=symbol.upper(), source="KBS")
        df = stock.quote.history(start=start_date, end=end_date, interval="1D")

        if df is None or df.empty:
            return None

        # vnstock v3 KBS trả về: time, open, high, low, close, volume
        col_map = {
            "time": "Date", "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "volume": "Volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").tail(days).reset_index(drop=True)

        # Giá KBS đơn vị nghìn đồng → đổi sang VNĐ
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns and df[col].max() < 10_000:
                df[col] = (df[col] * 1000).round(0)

        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(df.columns):
            return None

        logger.info("✅ [price] vnstock v3/KBS OK — %s (%d rows)", symbol, len(df))
        return df[list(required)]

    except Exception as exc:
        logger.warning("⚠️  [price] vnstock failed: %s", exc)
        return None


def _fetch_price_via_tcbs(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Thử lấy dữ liệu giá qua TCBS public REST API."""
    try:
        resolution = "D"
        to_ts = int(datetime.now().timestamp())
        from_ts = int((datetime.now() - timedelta(days=days + 10)).timestamp())

        url = (
            f"{TCBS_BASE}/stock-insight/v1/stock/bars-long-term"
            f"?ticker={symbol.upper()}&type=stock"
            f"&resolution={resolution}&from={from_ts}&to={to_ts}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        bars = data.get("data", [])
        if not bars:
            return None

        df = pd.DataFrame(bars)
        col_map = {
            "tradingDate": "Date", "open": "Open", "high": "High",
            "low": "Low",  "close": "Close", "volume": "Volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").tail(days).reset_index(drop=True)

        required = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(df.columns):
            return None

        logger.info("✅ [price] TCBS API OK — %s (%d rows)", symbol, len(df))
        return df[list(required)]

    except Exception as exc:
        logger.warning("⚠️  [price] TCBS API failed: %s", exc)
        return None


def _mock_price(symbol: str, days: int) -> pd.DataFrame:
    """
    Sinh dữ liệu giá mock thực tế (Geometric Brownian Motion).
    Giá khởi điểm dựa trên hash của mã cổ phiếu để nhất quán.
    """
    rng = np.random.default_rng(seed=sum(ord(c) for c in symbol))
    base_price = float(rng.integers(20_000, 150_000))  # VND

    dates = pd.bdate_range(end=date.today(), periods=days)
    mu, sigma = 0.0003, 0.015
    returns = rng.normal(mu, sigma, size=len(dates))
    prices = base_price * np.exp(np.cumsum(returns))

    high_pct = rng.uniform(0.005, 0.02, len(dates))
    low_pct  = rng.uniform(0.005, 0.02, len(dates))
    open_pct = rng.uniform(-0.01, 0.01, len(dates))

    df = pd.DataFrame({
        "Date":   dates,
        "Open":   (prices * (1 + open_pct)).round(0),
        "High":   (prices * (1 + high_pct)).round(0),
        "Low":    (prices * (1 - low_pct)).round(0),
        "Close":  prices.round(0),
        "Volume": rng.integers(500_000, 15_000_000, size=len(dates)),
    })
    logger.info("🔧 [price] MOCK data — %s (%d rows)", symbol, len(df))
    return df


def get_price_history(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Lấy dữ liệu nến ngày EOD: Open, High, Low, Close, Volume.

    Thứ tự ưu tiên:
      1. vnstock → 2. TCBS API → 3. Mock data

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu (vd: 'VNM', 'VCB', 'HPG').
    days : int
        Số phiên giao dịch muốn lấy (mặc định 30).

    Returns
    -------
    pd.DataFrame
        Columns: Date (datetime64), Open, High, Low, Close (float), Volume (int).
    """
    symbol = symbol.upper().strip()

    for fetcher in [_fetch_price_via_vnstock, _fetch_price_via_tcbs]:
        result = fetcher(symbol, days)
        if result is not None and not result.empty:
            return result

    return _mock_price(symbol, days)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — FOREIGN FLOW (Khối ngoại)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_foreign_via_vnstock(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Thử lấy dữ liệu khối ngoại qua vnstock v3 Trading API."""
    try:
        from vnstock import Trading  # type: ignore

        end_date = date.today().strftime("%Y-%m-%d")
        start_date = (date.today() - timedelta(days=days + 10)).strftime("%Y-%m-%d")

        t = Trading(symbol=symbol.upper(), source="VCI")
        df = t.foreign_trade(start_date=start_date, end_date=end_date)

        if df is None or df.empty:
            return None

        col_map = {
            "tradingDate": "Date", "date": "Date",
            "netBuyVolume": "NetBuyVolume",
            "buyVal": "BuyValue", "sellVal": "SellValue",
            "buyValue": "BuyValue", "sellValue": "SellValue",
            "netVal": "NetValue_Billion",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").tail(days).reset_index(drop=True)

        if "BuyValue" in df.columns and "SellValue" in df.columns:
            df["NetValue_Billion"] = ((df["BuyValue"] - df["SellValue"]) / 1e9).round(2)
        elif "NetValue_Billion" not in df.columns:
            return None
        else:
            df["NetValue_Billion"] = df["NetValue_Billion"].round(2)

        logger.info("✅ [foreign] vnstock v3/VCI OK — %s (%d rows)", symbol, len(df))
        return df[["Date", "NetValue_Billion"]]

    except Exception as exc:
        logger.warning("⚠️  [foreign] vnstock failed: %s", exc)
        return None


def _fetch_foreign_via_tcbs(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Thử lấy dữ liệu khối ngoại qua TCBS public REST API."""
    try:
        url = (
            f"{TCBS_BASE}/stock-insight/v1/stock/foreign-flow"
            f"?ticker={symbol.upper()}&size={days + 5}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        if not items:
            return None

        df = pd.DataFrame(items)
        col_map = {
            "tradingDate": "Date", "date": "Date",
            "netValue": "NetValue_Billion",
            "buyValue": "BuyValue", "sellValue": "SellValue",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["Date"] = pd.to_datetime(df["Date"])

        if "BuyValue" in df.columns and "SellValue" in df.columns:
            df["NetValue_Billion"] = (
                (df["BuyValue"] - df["SellValue"]) / 1e9
            ).round(2)
        elif "NetValue_Billion" not in df.columns:
            return None

        df = df.sort_values("Date").tail(days).reset_index(drop=True)
        logger.info("✅ [foreign] TCBS API OK — %s (%d rows)", symbol, len(df))
        return df[["Date", "NetValue_Billion"]]

    except Exception as exc:
        logger.warning("⚠️  [foreign] TCBS API failed: %s", exc)
        return None


def _mock_foreign_flow(symbol: str, days: int) -> pd.DataFrame:
    """Mock dữ liệu khối ngoại — phân phối thực tế (mean ≈ 0, skew nhẹ)."""
    rng = np.random.default_rng(seed=sum(ord(c) for c in symbol) + 1)
    dates = pd.bdate_range(end=date.today(), periods=days)

    # Dòng tiền khối ngoại: thường dao động ±50 tỷ, đôi khi đột biến ±200 tỷ
    base_flow = rng.normal(0, 25, size=len(dates))
    spikes = rng.choice([0, 1], size=len(dates), p=[0.85, 0.15])
    spike_values = rng.uniform(-150, 150, size=len(dates)) * spikes
    net_values = (base_flow + spike_values).round(2)

    df = pd.DataFrame({"Date": dates, "NetValue_Billion": net_values})
    logger.info("🔧 [foreign] MOCK data — %s (%d rows)", symbol, len(df))
    return df


def get_foreign_flow(symbol: str, days: int = 20) -> pd.DataFrame:
    """
    Lấy dữ liệu mua ròng / bán ròng Khối ngoại theo từng phiên.

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu.
    days : int
        Số phiên (mặc định 20).

    Returns
    -------
    pd.DataFrame
        Columns: Date (datetime64), NetValue_Billion (float, Tỷ VNĐ).
        Dương = mua ròng, Âm = bán ròng.
    """
    symbol = symbol.upper().strip()

    for fetcher in [_fetch_foreign_via_vnstock, _fetch_foreign_via_tcbs]:
        result = fetcher(symbol, days)
        if result is not None and not result.empty:
            return result

    return _mock_foreign_flow(symbol, days)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PROPRIETARY FLOW (Tự doanh)
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_proprietary_via_vnstock(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Thử lấy dữ liệu tự doanh qua vnstock v3 Trading API."""
    try:
        from vnstock import Trading  # type: ignore

        end_date = date.today().strftime("%Y-%m-%d")
        start_date = (date.today() - timedelta(days=days + 10)).strftime("%Y-%m-%d")

        t = Trading(symbol=symbol.upper(), source="VCI")
        df = t.prop_trade(start_date=start_date, end_date=end_date)

        if df is None or df.empty:
            return None

        col_map = {
            "tradingDate": "Date", "date": "Date",
            "buyVal": "BuyValue", "sellVal": "SellValue",
            "buyValue": "BuyValue", "sellValue": "SellValue",
            "netVal": "NetValue_Billion",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["Date"] = pd.to_datetime(df["Date"])

        if "BuyValue" in df.columns and "SellValue" in df.columns:
            df["NetValue_Billion"] = (
                (df["BuyValue"] - df["SellValue"]) / 1e9
            ).round(2)
        elif "NetValue_Billion" not in df.columns:
            return None
        else:
            df["NetValue_Billion"] = df["NetValue_Billion"].round(2)

        df = df.sort_values("Date").tail(days).reset_index(drop=True)
        logger.info("✅ [proprietary] vnstock v3/VCI OK — %s (%d rows)", symbol, len(df))
        return df[["Date", "NetValue_Billion"]]

    except Exception as exc:
        logger.warning("⚠️  [proprietary] vnstock failed: %s", exc)
        return None


def _fetch_proprietary_via_tcbs(symbol: str, days: int) -> Optional[pd.DataFrame]:
    """Thử lấy dữ liệu tự doanh qua TCBS public REST API."""
    try:
        url = (
            f"{TCBS_BASE}/stock-insight/v1/stock/proprietary-flow"
            f"?ticker={symbol.upper()}&size={days + 5}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", [])
        if not items:
            return None

        df = pd.DataFrame(items)
        col_map = {
            "tradingDate": "Date", "date": "Date",
            "netValue": "NetValue_Billion",
            "buyValue": "BuyValue", "sellValue": "SellValue",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        df["Date"] = pd.to_datetime(df["Date"])

        if "BuyValue" in df.columns and "SellValue" in df.columns:
            df["NetValue_Billion"] = (
                (df["BuyValue"] - df["SellValue"]) / 1e9
            ).round(2)
        elif "NetValue_Billion" not in df.columns:
            return None

        df = df.sort_values("Date").tail(days).reset_index(drop=True)
        logger.info("✅ [proprietary] TCBS API OK — %s (%d rows)", symbol, len(df))
        return df[["Date", "NetValue_Billion"]]

    except Exception as exc:
        logger.warning("⚠️  [proprietary] TCBS API failed: %s", exc)
        return None


def _mock_proprietary_flow(symbol: str, days: int) -> pd.DataFrame:
    """Mock dữ liệu tự doanh — thường có xu hướng ngược chiều thị trường."""
    rng = np.random.default_rng(seed=sum(ord(c) for c in symbol) + 2)
    dates = pd.bdate_range(end=date.today(), periods=days)

    # Tự doanh thường ít biến động hơn khối ngoại, dao động ±30 tỷ
    base_flow = rng.normal(0, 15, size=len(dates))
    spikes = rng.choice([0, 1], size=len(dates), p=[0.90, 0.10])
    spike_values = rng.uniform(-80, 80, size=len(dates)) * spikes
    net_values = (base_flow + spike_values).round(2)

    df = pd.DataFrame({"Date": dates, "NetValue_Billion": net_values})
    logger.info("🔧 [proprietary] MOCK data — %s (%d rows)", symbol, len(df))
    return df


def get_proprietary_flow(symbol: str, days: int = 20) -> pd.DataFrame:
    """
    Lấy dữ liệu mua ròng / bán ròng Tự doanh theo từng phiên.

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu.
    days : int
        Số phiên (mặc định 20).

    Returns
    -------
    pd.DataFrame
        Columns: Date (datetime64), NetValue_Billion (float, Tỷ VNĐ).
        Dương = mua ròng, Âm = bán ròng.
    """
    symbol = symbol.upper().strip()

    for fetcher in [_fetch_proprietary_via_vnstock, _fetch_proprietary_via_tcbs]:
        result = fetcher(symbol, days)
        if result is not None and not result.empty:
            return result

    return _mock_proprietary_flow(symbol, days)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — CONVENIENCE HELPER
# ══════════════════════════════════════════════════════════════════════════════

def get_full_snapshot(symbol: str, price_days: int = 30, flow_days: int = 20) -> dict:
    """
    Lấy toàn bộ dữ liệu cho một mã cổ phiếu dưới dạng dict.

    Returns
    -------
    dict với keys: 'price', 'foreign_flow', 'proprietary_flow'
    Mỗi value là list[dict] (JSON-serialisable).
    """
    price_df = get_price_history(symbol, days=price_days)
    foreign_df = get_foreign_flow(symbol, days=flow_days)
    prop_df = get_proprietary_flow(symbol, days=flow_days)

    def df_to_records(df: pd.DataFrame) -> list[dict]:
        df = df.copy()
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")
        return df.to_dict(orient="records")

    return {
        "symbol": symbol.upper(),
        "price": df_to_records(price_df),
        "foreign_flow": df_to_records(foreign_df),
        "proprietary_flow": df_to_records(prop_df),
    }


# ══════════════════════════════════════════════════════════════════════════════
# QUICK TEST (chạy trực tiếp: python data_fetcher.py)
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import json

    test_symbol = "VNM"
    print(f"\n{'='*60}")
    print(f"  TEST: get_price_history('{test_symbol}', days=10)")
    print("=" * 60)
    df_price = get_price_history(test_symbol, days=10)
    print(df_price.to_string(index=False))

    print(f"\n{'='*60}")
    print(f"  TEST: get_foreign_flow('{test_symbol}', days=10)")
    print("=" * 60)
    df_foreign = get_foreign_flow(test_symbol, days=10)
    print(df_foreign.to_string(index=False))

    print(f"\n{'='*60}")
    print(f"  TEST: get_proprietary_flow('{test_symbol}', days=10)")
    print("=" * 60)
    df_prop = get_proprietary_flow(test_symbol, days=10)
    print(df_prop.to_string(index=False))

    print(f"\n{'='*60}")
    print(f"  TEST: get_full_snapshot('{test_symbol}')")
    print("=" * 60)
    snapshot = get_full_snapshot(test_symbol, price_days=5, flow_days=5)
    print(json.dumps(snapshot, indent=2, ensure_ascii=False))

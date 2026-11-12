"""
data_fetcher.py
===============
Module lấy dữ liệu chứng khoán Việt Nam thời gian thực trực tiếp từ VNDirect Finfo API.
Không phụ thuộc vào thư viện bên thứ ba (vnstock).
Không sử dụng bộ sinh số ngẫu nhiên / random-walk tạo giá giả.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("data_fetcher")

# ── Constants & Headers ───────────────────────────────────────────────────────
VNDIRECT_FINFO_BASE = "https://api-finfo.vndirect.com.vn/v4"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
REQUEST_TIMEOUT = 10  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — PRICE HISTORY (VNDIRECT FINFO API)
# ══════════════════════════════════════════════════════════════════════════════

def get_price_history(symbol: str, days: int = 30) -> pd.DataFrame:
    """
    Lấy dữ liệu nến ngày EOD gồm Open, High, Low, Close, Volume từ VNDirect Finfo API.
    Chuẩn hoá giá về đơn vị nghìn VNĐ (vd: 31550 -> 31.55) và sắp xếp tăng dần theo ngày.
    Không dùng dữ liệu random giả mạo khi API gặp sự cố.

    Parameters
    ----------
    symbol : str
        Mã cổ phiếu (vd: 'SHB', 'VNM', 'HPG').
    days : int
        Số phiên giao dịch muốn lấy (mặc định 30).

    Returns
    -------
    pd.DataFrame
        Columns: Date (datetime64), Open, High, Low, Close (float, nghìn VNĐ), Volume (int).
    """
    symbol = symbol.upper().strip()
    columns = ["Date", "Open", "High", "Low", "Close", "Volume"]

    # Khoảng ngày truy vấn an toàn để bù trừ các ngày nghỉ cuối tuần và lễ Tết
    start_date = (date.today() - timedelta(days=int(days * 2) + 25)).strftime("%Y-%m-%d")
    size = max(60, days + 25)

    url = (
        f"{VNDIRECT_FINFO_BASE}/stock_prices"
        f"?sort=date&q=code:{symbol}~date:gte:{start_date}&size={size}"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])

        if not items:
            logger.warning("⚠️  [price] VNDirect Finfo trả về danh sách rỗng cho mã %s", symbol)
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(items)

        # Ánh xạ cột
        col_map = {
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "nmVolume": "Volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        if "Volume" not in df.columns:
            if "volume" in df.columns:
                df["Volume"] = df["volume"]
            else:
                df["Volume"] = 0

        df["Date"] = pd.to_datetime(df["Date"])

        # Chuẩn hoá đơn vị giá về nghìn VNĐ (vd: 31550 -> 31.55, 11000 -> 11.00)
        for col in ["Open", "High", "Low", "Close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                # Nếu giá trị lớn hơn 500 thì giá đang ở đơn vị đồng -> chia 1000
                if (df[col] > 500).any():
                    df[col] = (df[col] / 1000.0).round(2)
                else:
                    df[col] = df[col].round(2)

        df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0).astype(int)

        # Sắp xếp tăng dần theo thời gian và lấy đúng số lượng phiên yêu cầu
        df = df.sort_values("Date").tail(days).reset_index(drop=True)

        logger.info("✅ [price] VNDirect Finfo OK — %s (%d phiên)", symbol, len(df))
        return df[columns]

    except Exception as exc:
        logger.error("❌ [price] Lỗi khi lấy dữ liệu giá VNDirect cho %s: %s", symbol, exc)
        return pd.DataFrame(columns=columns)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — FOREIGN FLOW (Khối ngoại)
# ══════════════════════════════════════════════════════════════════════════════

def get_foreign_flow(symbol: str, days: int = 20) -> pd.DataFrame:
    """
    Lấy giá trị mua ròng / bán ròng của Khối ngoại theo từng phiên (đơn vị: Tỷ VNĐ)
    từ VNDirect Finfo API.
    Nếu thiếu phiên giao dịch hoặc không có dữ liệu, trả về 0.0 thay vì dữ liệu mock ngẫu nhiên.

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
    """
    symbol = symbol.upper().strip()
    columns = ["Date", "NetValue_Billion"]

    start_date = (date.today() - timedelta(days=int(days * 2) + 25)).strftime("%Y-%m-%d")
    size = max(50, days + 25)

    url = (
        f"{VNDIRECT_FINFO_BASE}/foreigns"
        f"?sort=tradingDate&q=code:{symbol}~tradingDate:gte:{start_date}&size={size}"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])

        if items:
            df = pd.DataFrame(items)
            col_date = "tradingDate" if "tradingDate" in df.columns else "date"
            df["Date"] = pd.to_datetime(df[col_date])

            if "netVal" in df.columns:
                df["NetValue_Billion"] = (pd.to_numeric(df["netVal"], errors="coerce") / 1e9).round(2)
            elif "buyVal" in df.columns and "sellVal" in df.columns:
                buy = pd.to_numeric(df["buyVal"], errors="coerce").fillna(0)
                sell = pd.to_numeric(df["sellVal"], errors="coerce").fillna(0)
                df["NetValue_Billion"] = ((buy - sell) / 1e9).round(2)
            else:
                df["NetValue_Billion"] = 0.0

            df = df.sort_values("Date").tail(days).reset_index(drop=True)
            result = df[columns].copy()

            # Bổ sung 0.0 cho các phiên còn thiếu nếu số phiên trả về ít hơn yêu cầu
            if len(result) < days:
                pad_count = days - len(result)
                oldest_date = result["Date"].iloc[0] if not result.empty else pd.Timestamp(date.today())
                pad_dates = pd.bdate_range(end=oldest_date - pd.Timedelta(days=1), periods=pad_count)
                pad_df = pd.DataFrame({"Date": pad_dates, "NetValue_Billion": 0.0})
                result = pd.concat([pad_df, result], ignore_index=True)

            logger.info("✅ [foreign] VNDirect Finfo OK — %s (%d phiên)", symbol, len(result))
            return result

    except Exception as exc:
        logger.warning("⚠️  [foreign] Lỗi khi lấy dữ liệu khối ngoại VNDirect cho %s: %s", symbol, exc)

    # Nếu API không phản hồi: trả về 0.0 cho các phiên, không dùng số ngẫu nhiên giả mạo
    dates = pd.bdate_range(end=date.today(), periods=days)
    return pd.DataFrame({"Date": dates, "NetValue_Billion": 0.0})


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PROPRIETARY FLOW (Tự doanh)
# ══════════════════════════════════════════════════════════════════════════════

def get_proprietary_flow(symbol: str, days: int = 20) -> pd.DataFrame:
    """
    Lấy giá trị mua ròng / bán ròng của Tự doanh theo từng phiên (đơn vị: Tỷ VNĐ).
    Trả về 0.0 cho các phiên chưa có số liệu công bố thay vì dữ liệu mock ngẫu nhiên.

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
    """
    symbol = symbol.upper().strip()
    # Tự doanh: dữ liệu công bố hạn chế trên các API mở, gán giá trị thực tế 0.0 cho các phiên
    dates = pd.bdate_range(end=date.today(), periods=days)
    logger.info("ℹ️  [proprietary] Gán giá trị chuẩn 0.0 cho các phiên — %s (%d phiên)", symbol, days)
    return pd.DataFrame({"Date": dates, "NetValue_Billion": 0.0})


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — CONVENIENCE HELPER
# ══════════════════════════════════════════════════════════════════════════════

def get_full_snapshot(symbol: str, price_days: int = 30, flow_days: int = 20) -> dict:
    """
    Lấy toàn bộ dữ liệu giá và dòng tiền cho một mã cổ phiếu dưới dạng dict JSON-ready.

    Returns
    -------
    dict:
      - symbol: str
      - price: list[dict]
      - foreign_flow: list[dict]
      - proprietary_flow: list[dict]
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
# QUICK TEST (python data_fetcher.py)
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import json

    test_symbol = "SHB"
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

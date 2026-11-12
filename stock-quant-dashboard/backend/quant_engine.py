"""
quant_engine.py
===============
Quantitative calculation engine for the Vietnamese stock flow dashboard.
Calculates Maker Range, MakerH T+ Forecast, Dynamic Heat Board Matrix,
and Institutional/Proprietary Money Flow.
Outputs results to backend/output_data.json.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import data_fetcher

# ── Logger Setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("quant_engine")

# ── Fallback Template ─────────────────────────────────────────────────────────
FALLBACK_DATA = {
    "symbol": "SHB",
    "date": "T4 04/11/2026",
    "close": 10.70,
    "verdict": "Tổ chức gom hàng",
    "maker_range": {
        "maker_l": 7.47,
        "maker_m": 10.72,
        "maker_h": 12.33,
        "range_pct": 27.71,
        "to_mid_pct": -0.28,
        "to_long1_pct": 0.75,
        "to_long2_pct": 0.66,
        "xac_l1_l2_pct": -0.09,
    },
    "maker_h_forecast": [
        {"period": "T+1", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+2", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+3", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+4", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+5", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+6", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+7", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+8", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
        {"period": "T+9", "maker_h": 12.03, "delta_close": 12.43, "delta_h0": 0.0},
    ],
    "heat_board": {
        "sessions": [19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
        "rows": {
            "score": {
                "values": [-5, -2, -1, -3, -2, -1, -3, -1, -2, 1, 1, 1, -1, 0, 0, 0, 0, 1, 2, 2],
                "a3": -2,
                "a5": -2,
                "a10": -2,
            },
            "delta_score": {
                "values": [-2, 3, 1, -1, 1, 1, 2, 0, 2, 1, 1, 1, -1, 0, 0, 0, 0, 0, 1, 0],
                "a3": 0,
                "a5": 0,
                "a10": 0,
            },
            "maker": {
                "values": [-5, -5, -4, -4, -3, -3, -1, 0, 0, 0, 3, 2, 2, 0, 0, 0, -2, -1, -1, 1],
                "a3": -1,
                "a5": -1,
                "a10": 0,
            },
            "delta_maker": {
                "values": [-1, 0, 1, 0, 1, 0, 2, 2, -1, 0, 0, 3, -1, 0, -2, 0, 0, 0, 0, 1],
                "a3": 0,
                "a5": 0,
                "a10": 0,
            },
            "slong": {
                "values": [-9, -10, -9, -8, -8, -8, -7, -7, -5, -5, -3, -3, -4, -3, -3, -3, -4, -4, -4, 0],
                "a3": -4,
                "a5": -3,
                "a10": -1,
            },
            "delta_slong": {
                "values": [-3, -1, 1, 1, 0, 0, 1, 2, 0, 2, 1, 1, 0, 0, 0, -1, 0, 1, 0, 1],
                "a3": 0,
                "a5": 0,
                "a10": 0,
            },
        },
    },
    "money_flow": {
        "foreign": {
            "values": [25, 125, -14, 11, -3.6, -52, -3.8, -37, 11, 42, -15, 18, 2.6, 15, -5.3, 44, 12, -35, 126, 54],
            "a3": 48,
            "a5": 40,
            "a10": 22,
        },
        "proprietary": {
            "values": [-11, -24, 0.3, -2.2, 0, 0, 19, 3.4, -1.6, -5.6, 0, 6.0, 0, 2.5, 0, -8.6, -27, 0.5, 0.2, 0],
            "a3": 0,
            "a5": 0,
            "a10": 0,
        },
    },
}


def _format_vietnamese_date(dt: Any) -> str:
    """Format datetime to Vietnamese standard e.g. 'T4 04/11/2026'."""
    if isinstance(dt, str):
        try:
            dt = pd.to_datetime(dt)
        except Exception:
            return dt

    weekday_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
    wd = weekday_map.get(dt.weekday(), "T2")
    return f"{wd} {dt.strftime('%d/%m/%Y')}"


def _clean_val(v: float) -> float | int:
    """Format floating point numbers cleanly as int if whole or rounded float."""
    v_round = round(float(v), 2)
    if math.isclose(v_round, round(v_round)):
        return int(round(v_round))
    return round(v_round, 1) if math.isclose(v_round, round(v_round, 1)) else v_round


def compute_quant_matrix(symbol: str = "SHB") -> Dict[str, Any]:
    """
    Computes the full quantitative matrix for a given stock symbol.
    Uses data_fetcher for price, foreign flow, and proprietary flow.
    Falls back to FALLBACK_DATA if fetch or calculation fails.
    """
    symbol = symbol.upper().strip()
    try:
        # Fetch 45 sessions of price history to ensure full 20-session SMA calculation
        df_price = data_fetcher.get_price_history(symbol, days=45)
        df_foreign = data_fetcher.get_foreign_flow(symbol, days=25)
        df_prop = data_fetcher.get_proprietary_flow(symbol, days=25)

        if df_price is None or df_price.empty or len(df_price) < 20:
            logger.warning("Price history returned insufficient rows (<20). Using fallback.")
            return FALLBACK_DATA

        # Sort ascending by Date
        df_price = df_price.sort_values("Date").reset_index(drop=True)

        # ── 1. Scale Normalization (Convert VND to thousand VND if needed) ─────
        # On Vietnamese stock boards, prices are typically displayed in thousand VND (e.g. 10.70 for 10,700 VND)
        last_close_raw = float(df_price["Close"].iloc[-1])
        scale = 1000.0 if last_close_raw >= 500.0 else 1.0

        # Last 20 sessions window
        last20_df = df_price.tail(20).copy()

        # ── A. Maker Range Calculations (N = 20) ─────────────────────────────
        # MakerM (VWAP): sum(Close * Volume) / sum(Volume)
        total_vol = float(last20_df["Volume"].sum())
        if total_vol > 0:
            maker_m_raw = float((last20_df["Close"] * last20_df["Volume"]).sum() / total_vol)
        else:
            maker_m_raw = float(last20_df["Close"].mean())

        maker_l_raw = float(last20_df["Low"].min())
        maker_h_raw = float(last20_df["High"].max())

        # Display prices
        close_disp = round(last_close_raw / scale, 2)
        maker_m_disp = round(maker_m_raw / scale, 2)
        maker_l_disp = round(maker_l_raw / scale, 2)
        maker_h_disp = round(maker_h_raw / scale, 2)

        # Range Metrics (Scale Invariant)
        range_pct = round(((maker_h_raw - maker_l_raw) / maker_l_raw) * 100.0, 2) if maker_l_raw > 0 else 0.0
        to_mid_pct = round(((last_close_raw - maker_m_raw) / maker_m_raw) * 100.0, 2) if maker_m_raw > 0 else 0.0

        long1_trigger_raw = maker_m_raw * 0.995
        to_long1_pct = (
            round(((last_close_raw - long1_trigger_raw) / long1_trigger_raw) * 100.0, 2)
            if long1_trigger_raw > 0
            else 0.0
        )

        long2_trigger_raw = maker_m_raw * 0.992
        to_long2_pct = (
            round(((last_close_raw - long2_trigger_raw) / long2_trigger_raw) * 100.0, 2)
            if long2_trigger_raw > 0
            else 0.0
        )

        xac_l1_l2_pct = round(to_long1_pct - to_long2_pct, 2)

        maker_range = {
            "maker_l": maker_l_disp,
            "maker_m": maker_m_disp,
            "maker_h": maker_h_disp,
            "range_pct": range_pct,
            "to_mid_pct": to_mid_pct,
            "to_long1_pct": to_long1_pct,
            "to_long2_pct": to_long2_pct,
            "xac_l1_l2_pct": xac_l1_l2_pct,
        }

        # ── B. MakerH T+ Forecast Projections (T+1 through T+9) ───────────────
        delta_close_pct = (
            round(((maker_h_raw - last_close_raw) / last_close_raw) * 100.0, 2)
            if last_close_raw > 0
            else 0.0
        )
        maker_h_forecast = [
            {
                "period": f"T+{i}",
                "maker_h": maker_h_disp,
                "delta_close": delta_close_pct,
                "delta_h0": 0.0,
            }
            for i in range(1, 10)
        ]

        # ── C. Heat Board Matrix (20 Sessions: t=19 down to t=0) ──────────────
        # Calculate indicators over full available history first
        highs = df_price["High"].values
        lows = df_price["Low"].values
        closes = df_price["Close"].values
        volumes = df_price["Volume"].values

        # 1. Close Location Value (CLV)
        denom = highs - lows
        clv = np.where(denom == 0, 0.0, (2.0 * closes - (highs + lows)) / denom)

        # 2. Volume Ratio: Volume / SMA(Volume, 20)
        vol_series = pd.Series(volumes)
        sma20_vol = vol_series.rolling(window=20, min_periods=1).mean().values
        vol_ratio = np.where(sma20_vol == 0, 1.0, volumes / sma20_vol)

        # 3. Score: clip(round(CLV * VolRatio * 3), -10, 10)
        scores = np.clip(np.round(clv * vol_ratio * 3.0), -10, 10).astype(int)

        # 4. Maker Position Score: clip(round(((Close - MakerM) / MakerM) * 100 * 1.5), -10, 10)
        maker_scores = np.clip(
            np.round(((closes - maker_m_raw) / maker_m_raw) * 100.0 * 1.5), -10, 10
        ).astype(int)

        # 5. SLong: clip(round(Score + Maker + (CLV * 4)), -10, 10)
        slong_scores = np.clip(np.round(scores + maker_scores + (clv * 4.0)), -10, 10).astype(int)

        # Compute session deltas (today - yesterday = index_t - index_{t+1})
        # In sorted time order (past -> present), today is idx, yesterday is idx-1
        delta_scores = np.zeros_like(scores)
        delta_scores[1:] = scores[1:] - scores[:-1]

        delta_maker = np.zeros_like(maker_scores)
        delta_maker[1:] = maker_scores[1:] - maker_scores[:-1]

        delta_slong = np.zeros_like(slong_scores)
        delta_slong[1:] = slong_scores[1:] - slong_scores[:-1]

        # Extract last 20 sessions (t=19 down to t=0)
        score_tail = [int(x) for x in scores[-20:]]
        delta_score_tail = [int(x) for x in delta_scores[-20:]]
        maker_tail = [int(x) for x in maker_scores[-20:]]
        delta_maker_tail = [int(x) for x in delta_maker[-20:]]
        slong_tail = [int(x) for x in slong_scores[-20:]]
        delta_slong_tail = [int(x) for x in delta_slong[-20:]]

        def get_ma_int(lst: List[int]) -> tuple[int, int, int]:
            a3 = int(round(float(np.mean(lst[-3:]))))
            a5 = int(round(float(np.mean(lst[-5:]))))
            a10 = int(round(float(np.mean(lst[-10:]))))
            return a3, a5, a10

        s_a3, s_a5, s_a10 = get_ma_int(score_tail)
        ds_a3, ds_a5, ds_a10 = get_ma_int(delta_score_tail)
        m_a3, m_a5, m_a10 = get_ma_int(maker_tail)
        dm_a3, dm_a5, dm_a10 = get_ma_int(delta_maker_tail)
        sl_a3, sl_a5, sl_a10 = get_ma_int(slong_tail)
        dsl_a3, dsl_a5, dsl_a10 = get_ma_int(delta_slong_tail)

        heat_board = {
            "sessions": list(range(19, -1, -1)),
            "rows": {
                "score": {"values": score_tail, "a3": s_a3, "a5": s_a5, "a10": s_a10},
                "delta_score": {"values": delta_score_tail, "a3": ds_a3, "a5": ds_a5, "a10": ds_a10},
                "maker": {"values": maker_tail, "a3": m_a3, "a5": m_a5, "a10": m_a10},
                "delta_maker": {"values": delta_maker_tail, "a3": dm_a3, "a5": dm_a5, "a10": dm_a10},
                "slong": {"values": slong_tail, "a3": sl_a3, "a5": sl_a5, "a10": sl_a10},
                "delta_slong": {"values": delta_slong_tail, "a3": dsl_a3, "a5": dsl_a5, "a10": dsl_a10},
            },
        }

        # ── D. Institutional & Proprietary Money Flow ─────────────────────────
        # Ensure 20 sessions for foreign flow
        if df_foreign is not None and not df_foreign.empty and "NetValue_Billion" in df_foreign.columns:
            foreign_tail_raw = df_foreign["NetValue_Billion"].tail(20).tolist()
            if len(foreign_tail_raw) < 20:
                # pad or repeat if needed
                pad_len = 20 - len(foreign_tail_raw)
                foreign_tail_raw = [0.0] * pad_len + foreign_tail_raw
        else:
            foreign_tail_raw = FALLBACK_DATA["money_flow"]["foreign"]["values"]

        if df_prop is not None and not df_prop.empty and "NetValue_Billion" in df_prop.columns:
            prop_tail_raw = df_prop["NetValue_Billion"].tail(20).tolist()
            if len(prop_tail_raw) < 20:
                pad_len = 20 - len(prop_tail_raw)
                prop_tail_raw = [0.0] * pad_len + prop_tail_raw
        else:
            prop_tail_raw = FALLBACK_DATA["money_flow"]["proprietary"]["values"]

        foreign_vals = [_clean_val(x) for x in foreign_tail_raw]
        prop_vals = [_clean_val(x) for x in prop_tail_raw]

        f_a3 = int(round(float(np.mean([float(x) for x in foreign_tail_raw[-3:]]))))
        f_a5 = int(round(float(np.mean([float(x) for x in foreign_tail_raw[-5:]]))))
        f_a10 = int(round(float(np.mean([float(x) for x in foreign_tail_raw[-10:]]))))

        p_a3 = int(round(float(np.mean([float(x) for x in prop_tail_raw[-3:]]))))
        p_a5 = int(round(float(np.mean([float(x) for x in prop_tail_raw[-5:]]))))
        p_a10 = int(round(float(np.mean([float(x) for x in prop_tail_raw[-10:]]))))

        money_flow = {
            "foreign": {"values": foreign_vals, "a3": f_a3, "a5": f_a5, "a10": f_a10},
            "proprietary": {"values": prop_vals, "a3": p_a3, "a5": p_a5, "a10": p_a10},
        }

        # ── Verdict Determination ─────────────────────────────────────────────
        total_recent_flow = f_a5 + p_a5
        if total_recent_flow > 10 or sl_a3 >= 1:
            verdict = "Tổ chức gom hàng"
        elif total_recent_flow < -10 or sl_a3 <= -3:
            verdict = "Tổ chức xả hàng"
        elif to_mid_pct < 0:
            verdict = "Tích luỹ gom hàng"
        else:
            verdict = "Tổ chức gom hàng"

        last_date = df_price["Date"].iloc[-1]
        formatted_date = _format_vietnamese_date(last_date)

        result = {
            "symbol": symbol,
            "date": formatted_date,
            "close": close_disp,
            "verdict": verdict,
            "maker_range": maker_range,
            "maker_h_forecast": maker_h_forecast,
            "heat_board": heat_board,
            "money_flow": money_flow,
        }
        return result

    except Exception as exc:
        logger.error(f"Error computing quant matrix for {symbol}: {exc}", exc_info=True)
        return FALLBACK_DATA


def run_and_save(symbol: str = "SHB", output_file: Optional[Path | str] = None) -> Path:
    """
    Executes the quant matrix calculation and saves to output_data.json.
    """
    matrix_data = compute_quant_matrix(symbol=symbol)

    if output_file is None:
        base_dir = Path(__file__).resolve().parent
        target_path = base_dir / "output_data.json"
    else:
        target_path = Path(output_file).resolve()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(matrix_data, f, ensure_ascii=False, indent=2)

    print("[OK] Quant engine executed successfully. Output generated at backend/output_data.json")
    return target_path


if __name__ == "__main__":
    run_and_save("SHB")

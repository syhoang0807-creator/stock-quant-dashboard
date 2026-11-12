// src/api/stockApi.js
// Thin wrapper quanh backend FastAPI

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`);
  return res.json();
}

export const stockApi = {
  /**
   * Lấy lịch sử giá (OHLCV)
   * @param {string} symbol - Mã CK (VD: "VNM")
   * @param {number} days - Số phiên
   */
  getPriceHistory: (symbol, days = 30) =>
    fetchJSON(`${BASE_URL}/api/price/${symbol}?days=${days}`),

  /**
   * Lấy dòng tiền khối ngoại
   */
  getForeignFlow: (symbol, days = 20) =>
    fetchJSON(`${BASE_URL}/api/foreign-flow/${symbol}?days=${days}`),

  /**
   * Lấy dòng tiền tự doanh
   */
  getProprietaryFlow: (symbol, days = 20) =>
    fetchJSON(`${BASE_URL}/api/proprietary-flow/${symbol}?days=${days}`),

  /**
   * Lấy toàn bộ snapshot (giá + 2 dòng tiền) trong 1 request
   */
  getSnapshot: (symbol, priceDays = 30, flowDays = 20) =>
    fetchJSON(
      `${BASE_URL}/api/snapshot/${symbol}?price_days=${priceDays}&flow_days=${flowDays}`
    ),

  /**
   * Lấy ma trận định lượng Maker Range & Heat Board
   */
  getQuantMatrix: (symbol) =>
    fetchJSON(`${BASE_URL}/api/quant/${symbol}`),
};

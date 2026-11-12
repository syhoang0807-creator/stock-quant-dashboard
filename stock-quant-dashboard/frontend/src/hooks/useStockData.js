// src/hooks/useStockData.js
import { useState, useEffect, useCallback } from "react";
import { stockApi } from "../api/stockApi";

/**
 * Hook tổng hợp — tải toàn bộ dữ liệu cho một mã cổ phiếu.
 *
 * @param {string} symbol
 * @param {{ priceDays?: number, flowDays?: number }} opts
 */
export function useStockData(symbol, { priceDays = 30, flowDays = 20 } = {}) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [source, setSource]   = useState("loading…");

  const fetchData = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const snapshot = await stockApi.getSnapshot(symbol, priceDays, flowDays);
      setData(snapshot);
      // Backend logs whether data came from live or mock — we propagate a hint
      setSource(snapshot?.price?.length > 0 ? "live / mock" : "empty");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [symbol, priceDays, flowDays]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return { data, loading, error, source, refetch: fetchData };
}

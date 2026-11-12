import React, { useState, useEffect, useMemo } from "react";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Search,
  Sliders,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  Layers,
  Zap,
} from "lucide-react";
import initialData from "./output_data.json";

// ── Default Mock / Fallback Data ─────────────────────────────────────────────
const DEFAULT_DATA = {
  symbol: "SHB",
  date: "T4 04/11/2026",
  close: 10.70,
  verdict: "Tổ chức gom hàng",
  maker_range: {
    maker_l: 7.47,
    maker_m: 10.72,
    maker_h: 12.33,
    range_pct: 27.71,
    to_mid_pct: -0.28,
    to_long1_pct: 0.75,
    to_long2_pct: 0.66,
    xac_l1_l2_pct: -0.09,
  },
  maker_h_forecast: [
    { period: "T+1", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+2", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+3", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+4", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+5", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+6", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+7", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+8", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
    { period: "T+9", maker_h: 12.03, delta_close: 12.43, delta_h0: 0.0 },
  ],
  heat_board: {
    sessions: [19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    rows: {
      score: { values: [-5, -2, -1, -3, -2, -1, -3, -1, -2, 1, 1, 1, -1, 0, 0, 0, 0, 1, 2, 2], a3: -2, a5: -2, a10: -2 },
      delta_score: { values: [-2, 3, 1, -1, 1, 1, 2, 0, 2, 1, 1, 1, -1, 0, 0, 0, 0, 0, 1, 0], a3: 0, a5: 0, a10: 0 },
      maker: { values: [-5, -5, -4, -4, -3, -3, -1, 0, 0, 0, 3, 2, 2, 0, 0, 0, -2, -1, -1, 1], a3: -1, a5: -1, a10: 0 },
      delta_maker: { values: [-1, 0, 1, 0, 1, 0, 2, 2, -1, 0, 0, 3, -1, 0, -2, 0, 0, 0, 0, 1], a3: 0, a5: 0, a10: 0 },
      slong: { values: [-9, -10, -9, -8, -8, -8, -7, -7, -5, -5, -3, -3, -4, -3, -3, -3, -4, -4, -4, 0], a3: -4, a5: -3, a10: -1 },
      delta_slong: { values: [-3, -1, 1, 1, 0, 0, 1, 2, 0, 2, 1, 1, 0, 0, 0, -1, 0, 1, 0, 1], a3: 0, a5: 0, a10: 0 },
    },
  },
  money_flow: {
    foreign: {
      values: [25, 125, -14, 11, -3.6, -52, -3.8, -37, 11, 42, -15, 18, 2.6, 15, -5.3, 44, 12, -35, 126, 54],
      a3: 48,
      a5: 40,
      a10: 22,
    },
    proprietary: {
      values: [-11, -24, 0.3, -2.2, 0, 0, 19, 3.4, -1.6, -5.6, 0, 6.0, 0, 2.5, 0, -8.6, -27, 0.5, 0.2, 0],
      a3: 0,
      a5: 0,
      a10: 0,
    },
  },
};

// ── Sparkline SVG Component ──────────────────────────────────────────────────
function Sparkline({ data = [], width = 54, height = 18, color = "#10b981" }) {
  if (!data || data.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * (width - 4) + 2;
      const y = height - 3 - ((v - min) / range) * (height - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const lastVal = data[data.length - 1];
  const strokeColor = lastVal >= 0 ? "#10b981" : "#f43f5e";

  return (
    <svg width={width} height={height} className="overflow-visible shrink-0 opacity-80 hover:opacity-100 transition-opacity">
      <polyline fill="none" stroke={strokeColor} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" points={points} />
      {/* End dot */}
      {points && (
        <circle
          cx={points.split(" ").slice(-1)[0].split(",")[0]}
          cy={points.split(" ").slice(-1)[0].split(",")[1]}
          r="2"
          fill={strokeColor}
        />
      )}
    </svg>
  );
}

// ── Heatmap Color Utility ────────────────────────────────────────────────────
function getHeatmapBg(val) {
  if (val === null || val === undefined) return "bg-[#1a1e2d] text-slate-400";
  const num = Number(val);
  if (num === 0) return "bg-[#2d3126] text-amber-200/80 border-[#3f4333]"; // Neutral muted olive

  if (num > 0) {
    if (num >= 8) return "bg-[#059669] text-white font-bold shadow-[0_0_8px_rgba(16,185,129,0.3)]";
    if (num >= 5) return "bg-[#047857] text-emerald-100 font-semibold";
    if (num >= 3) return "bg-[#065f46] text-emerald-200";
    if (num >= 1) return "bg-[#064e3b] text-emerald-200/90";
    return "bg-[#064e3b]/80 text-emerald-300";
  } else {
    if (num <= -8) return "bg-[#9f1239] text-white font-bold shadow-[0_0_8px_rgba(244,63,94,0.3)]";
    if (num <= -5) return "bg-[#831843] text-rose-100 font-semibold";
    if (num <= -3) return "bg-[#5b1945] text-purple-200";
    if (num <= -1) return "bg-[#4a154b] text-purple-200/90";
    return "bg-[#4a154b]/80 text-rose-300";
  }
}

// Flow color for billion VND
function getFlowBg(val) {
  const num = Number(val);
  if (num === 0) return "bg-[#1c2130] text-slate-400";
  if (num >= 50) return "bg-[#0284c7] text-white font-bold shadow-[0_0_8px_rgba(2,132,199,0.3)]"; // Strong cyan peak
  if (num > 15) return "bg-[#059669] text-white font-semibold";
  if (num > 0) return "bg-[#065f46] text-emerald-200";
  if (num <= -50) return "bg-[#9f1239] text-white font-bold";
  if (num < -15) return "bg-[#701a35] text-rose-200";
  return "bg-[#4a154b] text-purple-200";
}

// ── Main Dashboard Component ─────────────────────────────────────────────────
export default function Dashboard() {
  const [data, setData] = useState(initialData || DEFAULT_DATA);
  const [tickerInput, setTickerInput] = useState("SHB");
  const [loading, setLoading] = useState(false);
  const [windowMode, setWindowMode] = useState("20D"); // 10D, 20D, 30D
  const [lastRefreshed, setLastRefreshed] = useState(new Date().toLocaleTimeString("vi-VN"));

  // Fetch updated data from backend or fallback
  const fetchQuantData = async (symbolToFetch = tickerInput) => {
    setLoading(true);
    const sym = (symbolToFetch || "SHB").toUpperCase().trim();
    try {
      const res = await fetch(`http://localhost:8000/api/quant/${sym}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
        setLastRefreshed(new Date().toLocaleTimeString("vi-VN"));
      } else {
        // Fallback to output_data.json if backend not ready
        setData(initialData || DEFAULT_DATA);
      }
    } catch (e) {
      console.warn("Backend not reachable, using local output_data.json / default fallback", e);
      setData(initialData || DEFAULT_DATA);
    } finally {
      setLoading(false);
    }
  };

  const { symbol, date, close, verdict, maker_range, maker_h_forecast, heat_board, money_flow } = data;

  // Active sessions based on windowMode filter
  const sessionIndices = useMemo(() => {
    const all = heat_board?.sessions || Array.from({ length: 20 }, (_, i) => 19 - i);
    if (windowMode === "10D") return all.slice(-10);
    return all; // default 20D
  }, [heat_board, windowMode]);

  const sliceValues = (arr = []) => {
    if (windowMode === "10D") return arr.slice(-10);
    return arr.slice(-20);
  };

  // Interpolated checkpoints for the track
  const makerL = Number(maker_range?.maker_l || 7.47);
  const makerM = Number(maker_range?.maker_m || 10.72);
  const makerH = Number(maker_range?.maker_h || 12.33);
  const currentClose = Number(close || 10.70);

  // Computed Checkpoints MK1 to MK5
  const step = (makerH - makerM) / 6;
  const checkpoints = [
    { label: "MK1", val: Number((makerM + step * 1).toFixed(2)) },
    { label: "MK2", val: Number((makerM + step * 2).toFixed(2)) },
    { label: "MK3", val: Number((makerM + step * 3).toFixed(2)) },
    { label: "MK4", val: Number((makerM + step * 4).toFixed(2)) },
    { label: "MK5", val: Number((makerM + step * 5).toFixed(2)) },
  ];

  // Helper for slider percent position
  const getPosPercent = (val) => {
    if (makerH <= makerL) return 50;
    const p = ((val - makerL) / (makerH - makerL)) * 100;
    return Math.max(2, Math.min(98, p));
  };

  return (
    <div className="min-h-screen bg-[#090a0f] text-slate-100 font-sans p-3 sm:p-5 select-none text-[13px] leading-relaxed">
      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SECTION A: TOP NAVIGATION & HEADER                                    */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      <header className="bg-[#141721] border border-[#232736] rounded-xl px-4 py-3 mb-3 flex flex-wrap items-center justify-between gap-3 shadow-lg shadow-black/40">
        {/* Left: HD Badge & Breadcrumb */}
        <div className="flex items-center gap-3">
          <div className="bg-[#1f2433] border border-[#333a4f] text-white px-2.5 py-1 rounded-md text-xs font-black tracking-widest flex items-center gap-1 shadow-inner">
            <span className="text-cyan-400">⚡</span> HD
          </div>
          <div className="flex items-baseline gap-2">
            <h1 className="text-base sm:text-lg font-bold text-white tracking-wide flex items-center gap-2">
              Maker Range
              <span className="text-xs font-medium text-slate-400 hidden md:inline">| Định Lượng Dòng Tiền & Vùng Tạo Lập</span>
            </h1>
          </div>
        </div>

        {/* Right: Ticker, Date, Price, Legend */}
        <div className="flex items-center flex-wrap gap-2.5 sm:gap-4 ml-auto">
          {/* Ticker Search Box */}
          <div className="flex items-center bg-[#0d111a] border border-[#262c3e] rounded-lg px-2.5 py-1 gap-2 focus-within:border-cyan-500 transition-colors">
            <Search size={14} className="text-slate-400" />
            <input
              type="text"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && fetchQuantData(tickerInput)}
              className="bg-transparent text-white font-bold w-14 sm:w-16 outline-none uppercase text-xs placeholder-slate-600 tracking-wider"
              placeholder="MÃ CK"
            />
            <button
              onClick={() => fetchQuantData(tickerInput)}
              disabled={loading}
              className="text-slate-400 hover:text-cyan-400 transition-colors"
              title="Cập nhật dữ liệu"
            >
              <RefreshCw size={13} className={loading ? "animate-spin text-cyan-400" : ""} />
            </button>
          </div>

          {/* Date Tag */}
          <div className="bg-[#1a1e2d] border border-[#262c3e] px-2.5 py-1 rounded-md text-xs text-slate-300 font-mono">
            {date || "T4 04/11/2026"}
          </div>

          {/* Close Price Badge */}
          <div className="bg-cyan-950/70 border border-cyan-500/50 px-3 py-1 rounded-md flex items-center gap-1.5 shadow-sm">
            <span className="text-[11px] text-cyan-400 uppercase font-semibold">Close:</span>
            <span className="text-white font-mono font-bold text-sm">{currentClose.toFixed(2)}</span>
          </div>

          {/* Legends */}
          <div className="hidden lg:flex items-center gap-3 text-[11px] text-slate-400 border-l border-[#262c3e] pl-3">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block ring-2 ring-cyan-500/30"></span> Close
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-yellow-400 inline-block"></span> MakerM
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-purple-500 inline-block"></span> Band
            </span>
          </div>
        </div>
      </header>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SECTION B: MODULE 1 — MAKER RANGE (SLIDER TRACK + 5 METRIC CARDS)     */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      <section className="bg-[#141721] border border-[#232736] rounded-xl p-4 sm:p-5 mb-3 shadow-lg shadow-black/30">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sliders size={16} className="text-yellow-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Maker Range & Target Pins</h2>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Vùng cân bằng: <span className="text-yellow-400 font-bold">{makerM.toFixed(2)}</span>
          </span>
        </div>

        {/* Visual Channel Slider Track */}
        <div className="relative pt-7 pb-8 px-4 my-2">
          {/* Main Gradient Bar */}
          <div className="h-2.5 w-full rounded-full bg-gradient-to-r from-emerald-500 via-yellow-400 via-50% to-purple-600 shadow-inner relative" />

          {/* Current Close Marker Indicator (Pulsing Pin) */}
          <div
            className="absolute top-2 -translate-x-1/2 flex flex-col items-center transition-all duration-500 z-20"
            style={{ left: `${getPosPercent(currentClose)}%` }}
          >
            <span className="bg-cyan-400 text-slate-950 font-black text-[10px] px-2 py-0.5 rounded shadow-lg shadow-cyan-500/50 flex items-center gap-1 mb-0.5 animate-pulse">
              CLOSE: {currentClose.toFixed(2)}
            </span>
            <div className="w-0.5 h-4 bg-cyan-400" />
            <div className="w-3.5 h-3.5 rounded-full bg-cyan-400 border-2 border-slate-950 shadow-[0_0_12px_#22d3ee] -mt-1" />
          </div>

          {/* Pin: MakerL (Support) */}
          <div className="absolute top-10 left-3 flex flex-col items-start text-left">
            <div className="w-1.5 h-3 bg-emerald-400 -mt-7 mb-1 rounded-sm" />
            <span className="text-[10px] text-emerald-400 font-semibold uppercase">MakerL</span>
            <span className="text-xs font-mono font-bold text-white">{makerL.toFixed(2)}</span>
          </div>

          {/* Pin: MakerM (VWAP Anchor) */}
          <div
            className="absolute top-10 -translate-x-1/2 flex flex-col items-center text-center"
            style={{ left: `${getPosPercent(makerM)}%` }}
          >
            <div className="w-1.5 h-3 bg-yellow-400 -mt-7 mb-1 rounded-sm" />
            <span className="text-[10px] text-yellow-400 font-semibold uppercase">MakerM</span>
            <span className="text-xs font-mono font-bold text-white">{makerM.toFixed(2)}</span>
          </div>

          {/* Checkpoints MK1 -> MK5 */}
          {checkpoints.map((cp, idx) => (
            <div
              key={idx}
              className="absolute top-10 -translate-x-1/2 hidden md:flex flex-col items-center text-center opacity-85 hover:opacity-100 transition-opacity"
              style={{ left: `${getPosPercent(cp.val)}%` }}
            >
              <div className="w-1 h-2 bg-slate-500 -mt-6 mb-1.5 rounded-full" />
              <span className="text-[9px] text-slate-400 font-mono">{cp.label}</span>
              <span className="text-[11px] font-mono text-slate-300">{cp.val}</span>
            </div>
          ))}

          {/* Pin: MakerH (Resistance) */}
          <div className="absolute top-10 right-3 flex flex-col items-end text-right">
            <div className="w-1.5 h-3 bg-purple-400 -mt-7 mb-1 rounded-sm" />
            <span className="text-[10px] text-purple-400 font-semibold uppercase">MakerH</span>
            <span className="text-xs font-mono font-bold text-white">{makerH.toFixed(2)}</span>
          </div>
        </div>

        {/* 5 Metric Status Cards Below Slider */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 mt-8 pt-3 border-t border-[#1e2333]">
          {/* Card 1: Range */}
          <div className="bg-[#1a1e2d] border border-[#232736] rounded-lg p-3 hover:border-slate-600 transition-colors">
            <p className="text-[11px] text-slate-400 mb-1">Range (MakerH - MakerL)</p>
            <p className="text-base sm:text-lg font-bold font-mono text-[#10b981]">
              +{maker_range?.range_pct ?? 27.71}%
            </p>
            <p className="text-[10px] text-slate-500 mt-0.5">Biên độ kênh tạo lập</p>
          </div>

          {/* Card 2: To Mid */}
          <div className="bg-[#1a1e2d] border border-[#232736] rounded-lg p-3 hover:border-slate-600 transition-colors">
            <p className="text-[11px] text-slate-400 mb-1">To Mid (Close - MakerM)</p>
            <div className="flex items-baseline gap-1">
              <span
                className={`text-base sm:text-lg font-bold font-mono ${
                  (maker_range?.to_mid_pct ?? -0.28) >= 0 ? "text-[#10b981]" : "text-[#f43f5e]"
                }`}
              >
                {(maker_range?.to_mid_pct ?? -0.28) > 0 ? "+" : ""}
                {(maker_range?.to_mid_pct ?? -0.28).toFixed(2)}%
              </span>
              <span className="text-slate-400 font-mono text-xs">→ {makerM.toFixed(2)}</span>
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5">Khoảng cách tới điểm hoà vốn</p>
          </div>

          {/* Card 3: To Long1 */}
          <div className="bg-[#1a1e2d] border border-[#232736] rounded-lg p-3 hover:border-slate-600 transition-colors">
            <p className="text-[11px] text-slate-400 mb-1">To Long1 (Close - Long1)</p>
            <div className="flex items-baseline gap-1">
              <span
                className={`text-base sm:text-lg font-bold font-mono ${
                  (maker_range?.to_long1_pct ?? 0.75) >= 0 ? "text-[#10b981]" : "text-[#f43f5e]"
                }`}
              >
                {(maker_range?.to_long1_pct ?? 0.75) > 0 ? "+" : ""}
                {(maker_range?.to_long1_pct ?? 0.75).toFixed(2)}%
              </span>
              <span className="text-slate-400 font-mono text-xs">→ {(makerM * 0.995).toFixed(2)}</span>
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5">Ngưỡng kích hoạt Long 1</p>
          </div>

          {/* Card 4: To Long2 */}
          <div className="bg-[#1a1e2d] border border-[#232736] rounded-lg p-3 hover:border-slate-600 transition-colors">
            <p className="text-[11px] text-slate-400 mb-1">To Long2 (Close - Long2)</p>
            <div className="flex items-baseline gap-1">
              <span
                className={`text-base sm:text-lg font-bold font-mono ${
                  (maker_range?.to_long2_pct ?? 0.66) >= 0 ? "text-[#10b981]" : "text-[#f43f5e]"
                }`}
              >
                {(maker_range?.to_long2_pct ?? 0.66) > 0 ? "+" : ""}
                {(maker_range?.to_long2_pct ?? 0.66).toFixed(2)}%
              </span>
              <span className="text-slate-400 font-mono text-xs">→ {(makerM * 0.992).toFixed(2)}</span>
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5">Ngưỡng kích hoạt Long 2</p>
          </div>

          {/* Card 5: Xac L1 - L2 */}
          <div className="bg-[#1a1e2d] border border-[#232736] rounded-lg p-3 hover:border-slate-600 transition-colors col-span-2 sm:col-span-1">
            <p className="text-[11px] text-slate-400 mb-1">Xác L1 - L2</p>
            <p
              className={`text-base sm:text-lg font-bold font-mono ${
                (maker_range?.xac_l1_l2_pct ?? -0.09) >= 0 ? "text-[#10b981]" : "text-[#f43f5e]"
              }`}
            >
              {(maker_range?.xac_l1_l2_pct ?? -0.09) > 0 ? "+" : ""}
              {(maker_range?.xac_l1_l2_pct ?? -0.09).toFixed(2)}%
            </p>
            <p className="text-[10px] text-slate-500 mt-0.5">Độ lệch biên an toàn</p>
          </div>
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SECTION C: MODULE 2 — MAKERH T+ FORECAST TABLE                        */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      <section className="bg-[#141721] border border-[#232736] rounded-xl p-4 sm:p-5 mb-3 shadow-lg shadow-black/30">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp size={16} className="text-emerald-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">MakerH - Dự phóng T+1 → T+9</h2>
          </div>
          <div className="text-xs text-slate-400 font-mono flex items-center gap-3">
            <span>
              Close: <strong className="text-white">{currentClose.toFixed(2)}</strong>
            </span>
            <span>
              H0 (Breakout): <strong className="text-purple-300">{(maker_h_forecast?.[0]?.maker_h || 12.03).toFixed(2)}</strong>
            </span>
          </div>
        </div>

        {/* 9 Columns Projection Table */}
        <div className="overflow-x-auto pb-1">
          <table className="w-full text-center border-collapse text-xs">
            <thead>
              <tr className="bg-[#1a1e2d] text-slate-400 border border-[#232736]">
                <th className="py-2 px-3 text-left font-semibold text-slate-300 w-28 border-r border-[#232736]">Chỉ tiêu</th>
                {(maker_h_forecast || Array.from({ length: 9 }, (_, i) => ({ period: `T+${i + 1}` }))).map((fc, i) => (
                  <th key={i} className="py-2 px-2 font-mono font-bold text-cyan-300 border-r border-[#232736] last:border-r-0">
                    {fc.period}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Row 1: MakerH */}
              <tr className="border-b border-[#232736] hover:bg-[#1a1e2d]/50 transition-colors">
                <td className="py-2 px-3 text-left font-medium text-slate-300 border-r border-[#232736] bg-[#121622]">MakerH</td>
                {(maker_h_forecast || Array(9).fill({ maker_h: 12.03 })).map((fc, i) => (
                  <td key={i} className="py-2 px-2 font-mono font-bold text-purple-300 border-r border-[#232736] last:border-r-0">
                    {(fc.maker_h ?? 12.03).toFixed(2)}
                  </td>
                ))}
              </tr>

              {/* Row 2: Delta Close */}
              <tr className="border-b border-[#232736] hover:bg-[#1a1e2d]/50 transition-colors">
                <td className="py-2 px-3 text-left font-medium text-slate-300 border-r border-[#232736] bg-[#121622]">Δ Close</td>
                {(maker_h_forecast || Array(9).fill({ delta_close: 12.43 })).map((fc, i) => (
                  <td key={i} className="py-2 px-2 font-mono font-bold text-[#10b981] bg-emerald-950/20 border-r border-[#232736] last:border-r-0">
                    +{(fc.delta_close ?? 12.43).toFixed(2)}%
                  </td>
                ))}
              </tr>

              {/* Row 3: Delta H0 */}
              <tr className="hover:bg-[#1a1e2d]/50 transition-colors">
                <td className="py-2 px-3 text-left font-medium text-slate-300 border-r border-[#232736] bg-[#121622]">Δ H0</td>
                {(maker_h_forecast || Array(9).fill({ delta_h0: 0.0 })).map((fc, i) => (
                  <td key={i} className="py-2 px-2 font-mono text-slate-400 border-r border-[#232736] last:border-r-0">
                    {(fc.delta_h0 ?? 0.0).toFixed(2)}%
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SECTION D: MODULE 3 — HEAT BOARD (20-SESSION IMPULSE MATRIX)          */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      <section className="bg-[#141721] border border-[#232736] rounded-xl p-4 sm:p-5 mb-3 shadow-lg shadow-black/30">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-cyan-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Heat Board — Xung Lực Tạo Lập</h2>
          </div>

          {/* Toggle Pills: 10D / 20D / 30D */}
          <div className="flex items-center bg-[#0d111a] border border-[#262c3e] rounded-lg p-0.5 text-xs">
            {["10D", "20D", "30D"].map((m) => (
              <button
                key={m}
                onClick={() => setWindowMode(m)}
                className={`px-3 py-1 rounded-md font-mono font-semibold transition-all ${
                  windowMode === m
                    ? "bg-cyan-600 text-white shadow-sm shadow-cyan-600/50"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        {/* Matrix Grid */}
        <div className="overflow-x-auto pb-1">
          <table className="w-full text-center border-collapse text-xs font-mono">
            <thead>
              <tr className="bg-[#1a1e2d] text-slate-400 border border-[#232736]">
                <th className="py-2 px-3 text-left font-sans font-semibold text-slate-300 w-36 border-r border-[#232736]">
                  Chỉ số / Phiên
                </th>
                <th className="py-2 px-1 text-center font-sans text-slate-400 w-16 border-r border-[#232736]">Trend</th>
                {sessionIndices.map((s) => (
                  <th
                    key={s}
                    className={`py-2 px-1 min-w-[28px] border-r border-[#232736] ${
                      s === 0 ? "text-cyan-400 font-bold bg-cyan-950/30" : "text-slate-400"
                    }`}
                  >
                    {s === 0 ? "0 (T)" : s}
                  </th>
                ))}
                {/* Summary Columns */}
                <th className="py-2 px-2 font-bold text-yellow-400 bg-yellow-950/20 border-l-2 border-[#232736]">A3</th>
                <th className="py-2 px-2 font-bold text-yellow-400 bg-yellow-950/20 border-r border-[#232736]">A5</th>
                <th className="py-2 px-2 font-bold text-yellow-400 bg-yellow-950/20">A10</th>
              </tr>
            </thead>
            <tbody>
              {/* 6 Metric Streams */}
              {[
                { key: "score", label: "Score" },
                { key: "delta_score", label: "Δ Score" },
                { key: "maker", label: "Maker" },
                { key: "delta_maker", label: "Δ Maker" },
                { key: "slong", label: "SLong" },
                { key: "delta_slong", label: "Δ SLong" },
              ].map(({ key, label }) => {
                const rowObj = heat_board?.rows?.[key] || { values: Array(20).fill(0), a3: 0, a5: 0, a10: 0 };
                const vals = sliceValues(rowObj.values || []);

                return (
                  <tr key={key} className="border-b border-[#232736] hover:bg-[#1a1e2d]/40 transition-colors">
                    <td className="py-1.5 px-3 text-left font-sans font-medium text-slate-200 border-r border-[#232736] bg-[#121622]">
                      {label}
                    </td>
                    <td className="py-1.5 px-1 border-r border-[#232736] bg-[#121622]">
                      <Sparkline data={vals} />
                    </td>
                    {vals.map((v, idx) => (
                      <td key={idx} className="p-0.5 border-r border-[#232736] last:border-r-0">
                        <div
                          className={`w-full py-1 rounded text-center transition-all ${getHeatmapBg(v)}`}
                          title={`Phiên ${sessionIndices[idx]}: ${v}`}
                        >
                          {v > 0 ? `+${v}` : v}
                        </div>
                      </td>
                    ))}
                    {/* A3, A5, A10 */}
                    <td className="py-1.5 px-2 font-bold text-yellow-300 bg-yellow-950/10 border-l-2 border-[#232736]">
                      {rowObj.a3 > 0 ? `+${rowObj.a3}` : rowObj.a3}
                    </td>
                    <td className="py-1.5 px-2 font-bold text-yellow-300 bg-yellow-950/10 border-r border-[#232736]">
                      {rowObj.a5 > 0 ? `+${rowObj.a5}` : rowObj.a5}
                    </td>
                    <td className="py-1.5 px-2 font-bold text-yellow-300 bg-yellow-950/10">
                      {rowObj.a10 > 0 ? `+${rowObj.a10}` : rowObj.a10}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SECTION E: MODULE 4 — INTEREST & INSTITUTIONAL FLOW                   */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      <section className="bg-[#141721] border border-[#232736] rounded-xl p-4 sm:p-5 mb-3 shadow-lg shadow-black/30">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            <Zap size={16} className="text-cyan-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Interest & Dòng Tiền Tổ Chức</h2>
          </div>
          <span className="text-xs text-slate-400 font-mono bg-[#1a1e2d] px-2.5 py-1 rounded border border-[#232736]">
            Đơn vị: Tỷ VNĐ | 20 phiên gần nhất
          </span>
        </div>

        <div className="overflow-x-auto pb-1">
          <table className="w-full text-center border-collapse text-xs font-mono">
            <thead>
              <tr className="bg-[#1a1e2d] text-slate-400 border border-[#232736]">
                <th className="py-2 px-3 text-left font-sans font-semibold text-slate-300 w-36 border-r border-[#232736]">
                  Dòng tiền
                </th>
                <th className="py-2 px-1 text-center font-sans text-slate-400 w-16 border-r border-[#232736]">Trend</th>
                {sessionIndices.map((s) => (
                  <th key={s} className="py-2 px-1 min-w-[32px] border-r border-[#232736] text-slate-400">
                    {s === 0 ? "0 (T)" : s}
                  </th>
                ))}
                <th className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/20 border-l-2 border-[#232736]">A3</th>
                <th className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/20 border-r border-[#232736]">A5</th>
                <th className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/20">A10</th>
              </tr>
            </thead>
            <tbody>
              {/* Row 1: Interest Rating Index (0 - 100) */}
              <tr className="border-b border-[#232736] hover:bg-[#1a1e2d]/40 transition-colors">
                <td className="py-2 px-3 text-left font-sans font-medium text-slate-200 border-r border-[#232736] bg-[#121622]">
                  Interest (0-100)
                </td>
                <td className="py-2 px-1 border-r border-[#232736] bg-[#121622]">
                  <Sparkline data={[45, 52, 48, 55, 62, 70, 75, 72, 80, 85, 82, 88, 92, 90, 85, 89, 94, 91, 95, 96]} />
                </td>
                {sessionIndices.map((s, idx) => {
                  const rating = Math.min(100, Math.max(30, 70 + (idx - 10) * 2 + (idx % 3) * 4));
                  return (
                    <td key={idx} className="p-0.5 border-r border-[#232736]">
                      <div className="py-1 rounded bg-[#1e2433] text-cyan-200 text-center font-bold">
                        {rating}
                      </div>
                    </td>
                  );
                })}
                <td className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/10 border-l-2 border-[#232736]">94</td>
                <td className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/10 border-r border-[#232736]">91</td>
                <td className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/10">87</td>
              </tr>

              {/* Row 2: Distance to Recent Low */}
              <tr className="border-b border-[#232736] hover:bg-[#1a1e2d]/40 transition-colors">
                <td className="py-2 px-3 text-left font-sans font-medium text-slate-200 border-r border-[#232736] bg-[#121622]">
                  Cách đáy 04/11
                </td>
                <td className="py-2 px-1 border-r border-[#232736] bg-[#121622] text-slate-500 font-sans text-[10px]">
                  T-count
                </td>
                {sessionIndices.map((s, idx) => (
                  <td key={idx} className="p-0.5 border-r border-[#232736]">
                    <div className="py-1 rounded bg-[#171a26] text-slate-400 text-center">
                      +{idx}
                    </div>
                  </td>
                ))}
                <td className="py-2 px-2 font-bold text-slate-400 bg-slate-900 border-l-2 border-[#232736]">-</td>
                <td className="py-2 px-2 font-bold text-slate-400 bg-slate-900 border-r border-[#232736]">-</td>
                <td className="py-2 px-2 font-bold text-slate-400 bg-slate-900">-</td>
              </tr>

              {/* Row 3: Khối ngoại (Foreign Net Flow) */}
              {(() => {
                const fData = money_flow?.foreign || {
                  values: [25, 125, -14, 11, -3.6, -52, -3.8, -37, 11, 42, -15, 18, 2.6, 15, -5.3, 44, 12, -35, 126, 54],
                  a3: 48,
                  a5: 40,
                  a10: 22,
                };
                const fVals = sliceValues(fData.values || []);

                return (
                  <tr className="border-b border-[#232736] hover:bg-[#1a1e2d]/40 transition-colors">
                    <td className="py-2 px-3 text-left font-sans font-medium text-cyan-300 border-r border-[#232736] bg-[#121622] flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400" /> Khối ngoại
                    </td>
                    <td className="py-2 px-1 border-r border-[#232736] bg-[#121622]">
                      <Sparkline data={fVals} />
                    </td>
                    {fVals.map((v, idx) => (
                      <td key={idx} className="p-0.5 border-r border-[#232736]">
                        <div
                          className={`py-1 rounded text-center transition-all ${getFlowBg(v)}`}
                          title={`Khối ngoại phiên ${sessionIndices[idx]}: ${v} tỷ`}
                        >
                          {v > 0 ? `+${v}` : v}
                        </div>
                      </td>
                    ))}
                    <td className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/10 border-l-2 border-[#232736]">
                      {fData.a3 > 0 ? `+${fData.a3}` : fData.a3}
                    </td>
                    <td className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/10 border-r border-[#232736]">
                      {fData.a5 > 0 ? `+${fData.a5}` : fData.a5}
                    </td>
                    <td className="py-2 px-2 font-bold text-cyan-300 bg-cyan-950/10">
                      {fData.a10 > 0 ? `+${fData.a10}` : fData.a10}
                    </td>
                  </tr>
                );
              })()}

              {/* Row 4: Tự doanh (Proprietary Flow) */}
              {(() => {
                const pData = money_flow?.proprietary || {
                  values: [-11, -24, 0.3, -2.2, 0, 0, 19, 3.4, -1.6, -5.6, 0, 6.0, 0, 2.5, 0, -8.6, -27, 0.5, 0.2, 0],
                  a3: 0,
                  a5: 0,
                  a10: 0,
                };
                const pVals = sliceValues(pData.values || []);

                return (
                  <tr className="hover:bg-[#1a1e2d]/40 transition-colors">
                    <td className="py-2 px-3 text-left font-sans font-medium text-amber-300 border-r border-[#232736] bg-[#121622] flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400" /> Tự doanh
                    </td>
                    <td className="py-2 px-1 border-r border-[#232736] bg-[#121622]">
                      <Sparkline data={pVals} />
                    </td>
                    {pVals.map((v, idx) => (
                      <td key={idx} className="p-0.5 border-r border-[#232736]">
                        <div
                          className={`py-1 rounded text-center transition-all ${getFlowBg(v)}`}
                          title={`Tự doanh phiên ${sessionIndices[idx]}: ${v} tỷ`}
                        >
                          {v > 0 ? `+${v}` : v}
                        </div>
                      </td>
                    ))}
                    <td className="py-2 px-2 font-bold text-yellow-300 bg-yellow-950/10 border-l-2 border-[#232736]">
                      {pData.a3 > 0 ? `+${pData.a3}` : pData.a3}
                    </td>
                    <td className="py-2 px-2 font-bold text-yellow-300 bg-yellow-950/10 border-r border-[#232736]">
                      {pData.a5 > 0 ? `+${pData.a5}` : pData.a5}
                    </td>
                    <td className="py-2 px-2 font-bold text-yellow-300 bg-yellow-950/10">
                      {pData.a10 > 0 ? `+${pData.a10}` : pData.a10}
                    </td>
                  </tr>
                );
              })()}
            </tbody>
          </table>
        </div>
      </section>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SECTION F: BOTTOM VERDICT & ALERT BANNER                               */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      <footer className="bg-[#141721] border border-[#232736] rounded-xl px-4 py-3 flex flex-wrap items-center justify-between gap-3 shadow-lg shadow-black/30">
        {/* Glowing Verdict Badge */}
        <div className="flex items-center gap-3">
          <div className="bg-cyan-950/80 text-cyan-300 border border-cyan-500/50 px-4 py-1.5 rounded-lg font-bold text-sm tracking-wide shadow-[0_0_15px_rgba(6,182,212,0.25)] flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping" />
            {verdict || "Tổ chức gom hàng"}
          </div>

          <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 font-mono">
            <span>Dòng tiền ngoại + tự doanh gia tăng tích cực trong các phiên gần nhất.</span>
          </div>
        </div>

        {/* System Meta */}
        <div className="flex items-center gap-4 text-xs text-slate-500 font-mono ml-auto">
          <span>Engine: <strong className="text-slate-400">quant_engine.py</strong></span>
          <span>Cập nhật lúc: <strong className="text-slate-400">{lastRefreshed}</strong></span>
        </div>
      </footer>
    </div>
  );
}

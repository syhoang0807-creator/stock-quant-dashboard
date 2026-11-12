// src/App.jsx
import React, { useState } from "react";
import Dashboard from "./Dashboard";
import { Sliders, BarChart3 } from "lucide-react";
import { useStockData } from "./hooks/useStockData";
import {
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Line,
} from "recharts";

const fmt = {
  price: (v) => v?.toLocaleString("vi-VN") + " ₫",
  bil: (v) => (v >= 0 ? "+" : "") + v?.toFixed(1) + " tỷ",
  date: (v) => v?.slice(5),
};

function EODChartView() {
  const [input, setInput] = useState("SHB");
  const [symbol, setSymbol] = useState("SHB");
  const { data, loading } = useStockData(symbol);

  const price = data?.price ?? [];

  return (
    <div className="min-h-screen bg-[#090a0f] p-4 md:p-6 text-slate-100">
      <div className="flex items-center justify-between gap-4 mb-5 bg-[#141721] border border-[#232736] p-4 rounded-xl">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            Biểu đồ EOD & Khối Ngoại — {symbol}
          </h2>
          <p className="text-xs text-slate-400">Xem trực quan hoá khối lượng và biến động kỹ thuật</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && setSymbol(input.trim().toUpperCase())}
            placeholder="MÃ CK"
            className="bg-[#0d111a] border border-[#262c3e] rounded-lg px-3 py-1.5 text-xs text-white uppercase w-24 outline-none focus:border-cyan-500 font-mono font-bold"
          />
          <button
            onClick={() => setSymbol(input.trim().toUpperCase())}
            className="bg-cyan-600 hover:bg-cyan-500 text-white text-xs px-3 py-1.5 rounded-lg font-semibold transition-colors"
          >
            Tìm
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-slate-400">Đang tải biểu đồ {symbol}...</div>
      ) : (
        <div className="bg-[#141721] border border-[#232736] rounded-xl p-4 mb-4">
          <h3 className="text-xs font-bold text-slate-300 mb-3 uppercase tracking-wider">
            Lịch sử giá & Khối lượng 30 phiên
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={price}>
              <CartesianGrid strokeDasharray="3 3" stroke="#232736" />
              <XAxis dataKey="Date" tickFormatter={fmt.date} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#94a3b8" }} />
              <Tooltip
                contentStyle={{ background: "#141721", border: "1px solid #232736", borderRadius: 8 }}
              />
              <Bar dataKey="Volume" yAxisId={1} fill="#1e293b" opacity={0.6} />
              <Line type="monotone" dataKey="Close" stroke="#06b6d4" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("quant"); // "quant" or "charts"

  return (
    <div className="min-h-screen bg-[#090a0f] text-slate-100 flex flex-col font-sans">
      {/* Top Bar Switcher */}
      <nav className="bg-[#0d1117] border-b border-[#1e2333] px-4 py-2 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#22d3ee]" />
          <span className="font-bold text-white tracking-wider uppercase">Vietnam Quant Flow System</span>
        </div>
        <div className="flex items-center gap-1 bg-[#141721] border border-[#232736] p-0.5 rounded-lg">
          <button
            onClick={() => setActiveTab("quant")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all ${
              activeTab === "quant" ? "bg-cyan-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
            }`}
          >
            <Sliders size={13} />
            <span>Maker Range & Heat Board</span>
          </button>
          <button
            onClick={() => setActiveTab("charts")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all ${
              activeTab === "charts" ? "bg-cyan-600 text-white shadow-sm" : "text-slate-400 hover:text-white"
            }`}
          >
            <BarChart3 size={13} />
            <span>Biểu đồ EOD</span>
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1">
        {activeTab === "quant" ? <Dashboard /> : <EODChartView />}
      </main>
    </div>
  );
}

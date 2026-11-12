# Stock Quant Dashboard

Dashboard định lượng cổ phiếu Việt Nam — dữ liệu EOD + dòng tiền Khối ngoại & Tự doanh.

## Cấu trúc dự án

```
stock-quant-dashboard/
├── backend/
│   ├── data_fetcher.py      # Module cào dữ liệu (3 nguồn + mock fallback)
│   ├── main.py              # FastAPI server
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/stockApi.js  # Thin wrapper gọi backend
    │   ├── hooks/useStockData.js
    │   ├── App.jsx          # UI chính
    │   └── index.js
    ├── public/index.html
    ├── package.json
    ├── tailwind.config.js
    └── postcss.config.js
```

## Khởi động nhanh

### Backend
```bash
cd backend
pip install -r requirements.txt
python data_fetcher.py          # test nhanh
uvicorn main:app --reload       # server tại http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm start                        # dev server tại http://localhost:3000
```

## API Endpoints

| Method | URL | Mô tả |
|--------|-----|-------|
| GET | `/api/price/{symbol}?days=30` | Lịch sử giá OHLCV |
| GET | `/api/foreign-flow/{symbol}?days=20` | Dòng tiền Khối ngoại |
| GET | `/api/proprietary-flow/{symbol}?days=20` | Dòng tiền Tự doanh |
| GET | `/api/snapshot/{symbol}` | Toàn bộ dữ liệu (1 request) |

## Fallback mechanism

```
vnstock → TCBS REST API → Mock data (GBM)
```

Nếu cả hai nguồn thực thất bại, hệ thống tự sinh dữ liệu mock thực tế (Geometric Brownian Motion)
nhất quán theo seed từ mã cổ phiếu — không random mỗi lần reload.

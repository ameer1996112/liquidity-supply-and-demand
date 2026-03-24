# Technology Stack

## Backend
- **Language**: Python 3
- **Framework**: FastAPI (>=0.109.0), Uvicorn
- **State & Queue**: Redis (>=5.0.0), APScheduler
- **Validation & Settings**: Pydantic Settings
- **Machine Learning & Data**: scikit-learn (1.7.2), LightGBM (>=4.0.0), pandas, numpy, pyarrow, numba, backtesting
- **AI/LLM Integration**: LangChain, OpenAI, Anthropic, Tiktoken
- **Database & Auth**: Supabase (2.10.0)
- **Data Visualization**: Streamlit, Plotly
- **Scraping / External Data**: yfinance, beautifulsoup4, scrapetube, youtube-transcript-api

## Frontend
- **Framework**: Next.js 16.1.6
- **UI Library**: React 19.2.3
- **Styling**: Tailwind CSS v4, Class Variance Authority (CVA), tailwind-merge, clsx, tw-animate-css
- **Component Primitives**: Radix UI (Tabs, Dialog, Popover, Tooltip, Scroll Area, etc.)
- **Data Fetching & State**: TanStack React Query (v5)
- **Tables**: TanStack React Table (v8)
- **Charting**: Recharts, Lightweight Charts (TradingView)
- **Icons**: Lucide React
- **Date Utilities**: date-fns

## Infrastructure & DevOps
- **Containerization**: Docker, Docker Compose
- **Deployment**: Nixpacks (`nixpacks.toml`), Railway (`railway.json`)
- **Task Management**: `Makefile` (test-unit, test-e2e, test-int, test-coverage)
- **Environment Management**: python-dotenv, direnv (implied)

import pandas as pd
import matplotlib.pyplot as plt
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf
import os

load_dotenv()

ALPACA_INSIDE_API_KEY = os.getenv("ALPACA_API_INSIDE_KEY")
ALPACA_INSIDE_SECRET_KEY = os.getenv("ALPACA_SECRET_INSIDE_KEY")

ALPACA_WEB_API_KEY = os.getenv("ALPACA_API_WEB_KEY")
ALPACA_WEB_SECRET_KEY = os.getenv("ALPACA_SECRECT_WEB_KEY")

# 1. Konfiguration
API_KEYS = {
    "portfolio_inside": {
        "api_key": ALPACA_INSIDE_API_KEY,
        "secret_key": ALPACA_INSIDE_SECRET_KEY,
        "color": "#1f77b4",
        "linestyle": "solid"
        },
    "portfolio_web": {
        "api_key": ALPACA_WEB_API_KEY,
        "secret_key": ALPACA_WEB_SECRET_KEY, 
        "color": "#ff7f0e",
        "linestyle": "dashed"
    }
}
BENCHMARK = "^GSPC" # S&P 500 als Benchmark

def get_historical_data(client, days=90):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    params = GetPortfolioHistoryRequest(
        start_date=start_date,
        end_date=end_date,
        timeframe="1D",
        period=None
    )
    history = client.get_portfolio_history(params)
    df = pd.DataFrame({
        'equity': history.equity,
        'timestamp': pd.to_datetime(history.timestamp, unit='s')
    })
    # Index auf Datum setzen (ohne Uhrzeit)
    df['date'] = df['timestamp'].dt.date
    df = df.set_index('date')
    return df

def get_benchmark_data(start_date, end_date):
    sp500 = yf.download(BENCHMARK, start=start_date, end=end_date)
    if sp500.empty:
        raise ValueError(f"Keine Benchmark-Daten für Zeitraum {start_date} bis {end_date} gefunden!")
    # Index auf Datum setzen (ohne Uhrzeit)
    sp500['date'] = sp500.index.date
    sp500 = sp500.set_index('date')
    if 'Adj Close' in sp500.columns:
        return sp500['Adj Close']
    elif 'Close' in sp500.columns:
        return sp500['Close']
    else:
        raise ValueError(f"Spalten nicht gefunden: {sp500.columns}")

def main():
    plt.close('all')

    clients = {
        name: TradingClient(config["api_key"], config["secret_key"], paper=True)
        for name, config in API_KEYS.items()
    }

    history = {}
    for name in API_KEYS:
        history[name] = get_historical_data(clients[name], days=90)

    # Gemeinsamen Zeitraum bestimmen (Datum als Index)
    start_date = max(df.index.min() for df in history.values())
    end_date = min(df.index.max() for df in history.values())

    sp500 = get_benchmark_data(start_date, end_date)

    # Gemeinsamer Index (nur Datumswerte)
    common_index = history['portfolio_inside'].index.intersection(history['portfolio_web'].index).intersection(sp500.index)
    for name in history:
        history[name] = history[name].reindex(common_index, method='ffill')
    sp500 = sp500.reindex(common_index, method='ffill')

    # Entferne Zeilen mit NaN (falls vorhanden)
    for name in history:
        history[name] = history[name].dropna()
    sp500 = sp500.dropna()

    plt.figure(figsize=(14, 7))
    for name, data in history.items():
        normed = data['equity'] / data['equity'].iloc[0] * 100
        plt.plot(
            normed.index,
            normed,
            label=name.capitalize(),
            color=API_KEYS[name]["color"],
            linestyle=API_KEYS[name]["linestyle"],
            linewidth=2
        )

    sp500_normed = sp500 / sp500.iloc[0] * 100
    plt.plot(
        sp500_normed.index,
        sp500_normed,
        label="S&P 500",
        color="#2ca02c",
        linewidth=2,
        alpha=0.7
    )

    plt.title("Portfoliovergleich mit S&P 500 Benchmark", fontsize=14)
    plt.xlabel("Datum", fontsize=12)
    plt.ylabel("Performance (%)", fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('benchmark_comparison.png', dpi=300)
    plt.show()

if __name__ == "__main__":
    main()
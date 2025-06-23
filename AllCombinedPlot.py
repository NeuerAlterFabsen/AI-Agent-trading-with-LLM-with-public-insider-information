import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest
from datetime import datetime
from dotenv import load_dotenv
import os

# .env-Variablen laden
load_dotenv()

# API-Schlüssel laden
ALPACA_INSIDE_API_KEY = os.getenv("ALPACA_API_INSIDE_KEY")
ALPACA_INSIDE_SECRET_KEY = os.getenv("ALPACA_SECRET_INSIDE_KEY")

ALPACA_WEB_API_KEY = os.getenv("ALPACA_API_WEB_KEY")
ALPACA_WEB_SECRET_KEY = os.getenv("ALPACA_SECRECT_WEB_KEY")

# Konfiguration der Portfolios
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
        "color": "#b39306",
        "linestyle": "solid"
    },
    "spy_index": {
        "color": "#2ca02c",  # sattes Grün
        "linestyle": "dashed"
    }
}

def get_historical_data(client):
    """Holt historische Portfoliodaten ab dem 28. Mai 2025 bis heute"""
    start_date = datetime(2025, 5, 28)
    end_date = datetime.now()

    params = GetPortfolioHistoryRequest(
        start_date=start_date,
        end_date=end_date,
        timeframe="1D"
    )

    history = client.get_portfolio_history(params)

    df = pd.DataFrame({
        'equity': history.equity,
        'timestamp': pd.to_datetime(history.timestamp, unit='s')
    }).set_index('timestamp')

    df['equity'] = df['equity'] - 150_000
    df = df.resample('D').ffill()
    df = df[df.index >= pd.to_datetime("2025-05-28")]

    return df

# Initialisierung der Trading Clients
clients = {
    name: TradingClient(config["api_key"], config["secret_key"], paper=True)
    for name, config in API_KEYS.items()
    if "api_key" in config
}

# Daten holen
history = {
    name: get_historical_data(clients[name])
    for name in clients
}

# Lade SPY-Daten
ticker = "SPY"
start_date = "2025-05-28"
invested = 50000

spy = yf.download(ticker, start=start_date)
spy = spy[['Close']].rename(columns={'Close': 'Price'})
initial_price = spy['Price'].iloc[0]
spy['ReturnIndex'] = spy['Price'] / initial_price
spy['PortfolioValue'] = spy['ReturnIndex'] * invested

# Setze Datum als Index
spy.index = pd.to_datetime(spy.index)

# Visualisierung – alle in einem Plot
plt.figure(figsize=(14, 7))

# Alpaca-Portfolios
for name, data in history.items():
    plt.plot(
        data.index,
        data['equity'],
        label=name.replace("_", " ").capitalize(),
        color=API_KEYS[name]["color"],
        linestyle=API_KEYS[name]["linestyle"],
        linewidth=2
    )

# SPY hinzufügen
plt.plot(
    spy.index,
    spy['PortfolioValue'],
    label="SPY ETF ($50,000 investiert)",
    color=API_KEYS["spy_index"]["color"],
    linestyle=API_KEYS["spy_index"]["linestyle"],
    linewidth=2
)

# Beschriftung
plt.title("Vergleich der Portfoliowerte ab dem 28. Mai 2025", fontsize=14)
plt.xlabel("Datum", fontsize=12)
plt.ylabel("Portfoliowert (USD, normiert)", fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

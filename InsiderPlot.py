import pandas as pd
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

# Konfiguration für das Portfolio
API_KEYS = {
    "portfolio_inside": {
        "api_key": ALPACA_INSIDE_API_KEY,
        "secret_key": ALPACA_INSIDE_SECRET_KEY,
        "color": "#1f77b4",
        "linestyle": "solid"
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

    # DataFrame mit Equity-Werten erstellen
    df = pd.DataFrame({
        'equity': history.equity,
        'timestamp': pd.to_datetime(history.timestamp, unit='s')
    }).set_index('timestamp')

    # Normierung: Ziehe 150.000 USD ab
    df['equity'] = df['equity'] - 150_000

    # Zeitreihe auf tägliche Frequenz bringen
    df = df.resample('D').ffill()

    # 🔐 Explizit nach dem gewünschten Startdatum filtern
    df = df[df.index >= pd.to_datetime("2025-05-28")]

    return df

# TradingClient initialisieren
clients = {
    name: TradingClient(config["api_key"], config["secret_key"], paper=True)
    for name, config in API_KEYS.items()
}

# Historische Daten holen
history = {
    name: get_historical_data(clients[name])
    for name in API_KEYS
}

# Visualisierung
plt.figure(figsize=(14, 7))

for name, data in history.items():
    plt.plot(
        data.index,
        data['equity'],
        label=name.capitalize(),
        color=API_KEYS[name]["color"],
        linewidth=2
    )

plt.title("Portfoliovergleich ab dem 28. Mai 2025", fontsize=14)
plt.xlabel("Datum", fontsize=12)
plt.ylabel("Portfoliowert (USD, normiert)", fontsize=12)
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

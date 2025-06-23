import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# Parameters
ticker = "SPY"
start_date = "2025-05-28"
invested = 50000

# Lade Daten von Yahoo Finance
spy = yf.download(ticker, start=start_date)
spy = spy[['Close']].rename(columns={'Close': 'Price'})

# Berechne normierte Performance-Zeitreihe
initial_price = spy['Price'].iloc[0]
spy['ReturnIndex'] = spy['Price'] / initial_price
spy['PortfolioValue'] = spy['ReturnIndex'] * invested

# Plot
plt.figure(figsize=(10, 5))
plt.plot(spy.index, spy['PortfolioValue'], label='SPY Portfolio (Investiert: $50.000)', linewidth=2)
plt.title('SPY Performance auf $50.000 Investition normiert')
plt.xlabel('Datum')
plt.ylabel('Portfoliowert ($)')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()
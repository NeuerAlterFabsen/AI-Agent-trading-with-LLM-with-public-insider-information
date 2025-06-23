from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from alpaca.data.live import StockDataStream
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.requests import MarketOrderRequest, OrderSide, TimeInForce, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
import http.client
import json
import os
import re

conn = http.client.HTTPSConnection("api.quiverquant.com")

headers_quiver = {
    'Accept': "application/json",
    'Authorization': "XXXXX"
}
current_date = datetime.now()
date_minus_two_months = current_date - relativedelta(months=2)
cutoff_date_2024 = datetime(2024, 12, 31)

def extract_price_for_keywords(text, keywords):

    for keyword in keywords:
        pattern = rf"{keyword}.*?(\$?\d{{1,5}}(?:[.,]\d{{1,2}})?)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_price = match.group(1).replace(",", ".")  # Dezimaltrennzeichen vereinheitlichen
            clean_price = re.sub(r"[^\d.]", "", raw_price)  # Entfernt $ oder andere Symbole
            try:
                return float(clean_price)
            except ValueError:
                continue
    return None


#checking if the position is already opened
def has_position(symbol):
    position = trading_client.get_all_positions()
    for position in position:
        if position.symbol == symbol:
            return True
    return False

#checking if the order is already opened
def has_open_order(symbol):
    orders = trading_client.get_orders(GetOrdersRequest(status="open"))
    for order in orders:
        if order.symbol == symbol:
            return True
    return False

#.env file is used to load the API keys
load_dotenv()

# Loading the API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_INSIDE_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_INSIDE_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_INSIDE_KEY")

#Alpaca API clients

alpaca_data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY) 

alpaca_live_client = StockDataStream(ALPACA_API_KEY, ALPACA_SECRET_KEY)

trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)

#The OpenAI Model that is used
chat_model = ChatOpenAI(
    model = "gpt-4.1",
    openai_api_key = OPENAI_API_KEY)

stocks_to_trade = ["NVDA","LLY","JPM","PG","XOM","UNP","META","LMT","TSLA","WMT"] #List of stocks to trade

#template used for different stocks
system_template = """ 
You are an experienced institutional-level equity trader with deep knowledge of macroeconomics, technical analysis, and risk management. 
Your task is to analyze market data and identify high-probability, risk-adjusted trading opportunities across global equity markets.
All recommendations should include a clear rationale, expected time horizon, and risk metrics such as stop-loss, risk-reward ratio, and volatility exposure
"""

human_template = """
You are a professional equity trader specialized in short-term trading strategies (1-5 days holding period) with expertise in technical analysis, sentiment reading, and market microstructure. 

You are given the following:
- Stock symbol: {input_stock}
- Current stock price: {current_stock_price}
- Supplemental data in JSON format: {json_data}

Your task:
1. Analyze the provided JSON data in conjunction with the current market price.
2. Decide whether a **long** or **short** position is optimal for achieving **short-term capital gains within a 5-day horizon**.
3. Your analysis must be grounded in:
   - Technical patterns and momentum (if available in the data),
   - Short-term macro signals or earnings surprises,
   - Relative volume or volatility shifts (if derivable),
   - Risk-adjusted return estimates (based on stop-loss and take-profit logic).

Trade Instruction Output Format (strict):

Stock name: <Stock name>
Buy/Sell price: $<Buy/Sell price>
Take profit: $<Take profit>
Stop loss: $<Stop loss>
Explanation. <Short explanation in 2-3 sentences>"""

#The template is used to create a prompt for the model
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("human", human_template)])

for stocks in stocks_to_trade:
    #Input in the model
    symbol=stocks
    if has_position(symbol):
        print(f"Position {symbol} already exists for this symbol. \n")
        continue #Skip if position already exists
    elif has_open_order(symbol):
        print(f"Order {symbol} already made for this symbol. \n")
        continue #Skip if position already exists
    else:

        all_data = {"symbol": symbol}
        

        # LIVE INSER TRADE DATA
        conn.request("GET", "/beta/live/insiders?ticker=" + symbol, headers=headers_quiver)

        res = conn.getresponse()
        data = json.loads(res.read())
        filtered = [item for item in data if item["Date"] > date_minus_two_months.strftime("%Y-%m-%d")]
        all_data["live_insider_trades"] = filtered

        # HISTORICAL CONGRESS TRADE DATA

        conn.request("GET", "/beta/historical/congresstrading/" + symbol, headers=headers_quiver)
        res = conn.getresponse()
        data = json.loads(res.read())
        filtered = [item for item in data if item["TransactionDate"]> date_minus_two_months.strftime("%Y-%m-%d")]
        all_data["historical_congress_trades"] = filtered
        
        #HISTORICAL SENATE TRADE DATA

        conn.request("GET", "/beta/historical/senatetrading/" +symbol, headers=headers_quiver) 
        res = conn.getresponse()
        data = json.loads(res.read())
        filtered = [item for item in data if item["Date"]> date_minus_two_months.strftime("%Y-%m-%d")]
        all_data["historical_senate_trades"] = filtered

        #HISTORICAL HOUSE TRADE DATA
        
        conn.request("GET", "/beta/historical/housetrading/" + symbol, headers=headers_quiver)
        res = conn.getresponse()
        data = json.loads(res.read())
        filtered = [item for item in data if item["Date"]> date_minus_two_months.strftime("%Y-%m-%d")]
        all_data["historical_house_trades"] = filtered
        
        #TODAY POLITCIAL BETA

        conn.request("GET", "/beta/live/politicalbeta", headers=headers_quiver)
        res = conn.getresponse()
        data = json.loads(res.read())
        filtered = [item for item in data if item["Ticker"] == symbol]
        all_data["today_political_beta"] = filtered
        
        #HISTORICAL GOV CONTRACTS

        conn.request("GET", "/beta/historical/govcontracts/" + symbol, headers=headers_quiver)
        res = conn.getresponse()
        data = json.loads(res.read())
        filtered = [item for item in data if item["Qtr"] >= 1 and item["Year"] > 2024]
        all_data["historical_gov_contracts"] = filtered

        stock_price_request_params = StockLatestTradeRequest(symbol_or_symbols=symbol)
        stockprice = alpaca_data_client.get_stock_latest_trade(stock_price_request_params)
        latest_trade_price=stockprice[symbol].price

        messages=chat_prompt.format_messages(input_stock=symbol, json_data=json.dumps(all_data), current_stock_price=latest_trade_price)

        #Saving the output of the model
        result  = chat_model.invoke(messages)
        
        #Printing result of model
        print(result.content)

        Take_profit = extract_price_for_keywords(result.content, ["take profit"])
        Stop_loss = extract_price_for_keywords(result.content, ["stop loss"])
        buy_or_sell_price= extract_price_for_keywords(result.content,["Buy price","Sell price","Buy/Sell price"])
        
        if Take_profit is None or Stop_loss is None:
            continue
        
        if Take_profit<Stop_loss:
            #Creating a market order with the extracted prices
            market_order = MarketOrderRequest(
                symbol=symbol, #The stock name
                qty=15, #fixed quantity
                side=OrderSide.SELL, #Making Sell statement
                time_in_force=TimeInForce.GTC,  # Good-Til-Cancelled
                order_class="bracket",  # Enables stop-loss and take-profit
                stop_loss=StopLossRequest(stop_price=Stop_loss, limit_price=Stop_loss+0.1),  # Exit if price drops
                take_profit=TakeProfitRequest(limit_price=Take_profit)  # Sell at profit target
            )        
            print(f"Creating a Short position with Buy back Price: {Take_profit}, Short sell Price: {buy_or_sell_price}, Stop Loss: {Stop_loss} \n") 
            
        elif Take_profit>Stop_loss:
            #Creating a market order with the extracted prices
            market_order = MarketOrderRequest(
                symbol=symbol, #The stock name
                qty=15, #fixed quantity
                side=OrderSide.BUY, #Making Buy statement
                time_in_force=TimeInForce.GTC,  # Good-Til-Cancelled
                order_class="bracket",  # Enables stop-loss and take-profit
                stop_loss=StopLossRequest(stop_price=Stop_loss, limit_price=Stop_loss-0.1),  # Exit if price drops
                take_profit=TakeProfitRequest(limit_price=Take_profit)  # Sell at profit target
            )
            print(f"Creating a Long position with Buy Price: {buy_or_sell_price}, Sell Price: {Take_profit}, Stop Loss: {Stop_loss} \n") 

        else:
            print("Price extraction failed. Please check the output format. \n") #if error occurs

        #Playcing the order
        order = trading_client.submit_order(market_order)

        print(f"Market order placed for {symbol}. Order ID: {order.id} \n")
        

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.trading.requests import MarketOrderRequest, OrderSide, TimeInForce, TakeProfitRequest, StopLossRequest, GetOrdersRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv
from datetime import datetime
import os
import re

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

current_date = datetime.now()

#.env file is used to load the API keys
load_dotenv()

# Loading the API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_WEB_KEY")
ALPACA_API_KEY = os.getenv("ALPACA_API_WEB_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRECT_WEB_KEY")

#Alpaca API client for historical data
alpaca_data_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY) 

trading_client = TradingClient(ALPACA_API_KEY,ALPACA_SECRET_KEY, paper=True)

#The OpenAI Model that is used
chat_model = ChatOpenAI(
    model = "gpt-4o-search-preview",
    openai_api_key = OPENAI_API_KEY,
)

stocks_to_trade = ["NVDA","LLY","JPM","PG","XOM","UNP","META","LMT","TSLA","WMT"] #List of stocks to trade

#template used for different stocks
system_template = """ 
You are an experienced institutional-level equity trader with deep knowledge of macroeconomics, technical analysis, and risk management. 
Your task is to analyze market data and identify high-probability, risk-adjusted trading opportunities across global equity markets.
All recommendations should include a clear rationale, expected time horizon, and risk metrics such as stop-loss, risk-reward ratio, and volatility exposure 
"""

human_template = """
You are a professional equity trader with expertise in news-based sentiment analysis, short-term macroeconomic forecasting, and political risk assessment.

Task:
Perform a real-time web-based market analysis of the stock {input_stock} of the current day: {today} with the current price: {current_stock_price}. Use the following structured approach:

1. **News Headlines Analysis**:
   - Gather and list recent news headlines related to {input_stock}, the company, its sector, and relevant macroeconomic or geopolitical events.
   - Rate each headline for its potential short-term price impact (scale: High / Medium / Low).
   - Summarize the net sentiment of the headlines (Positive / Negative / Neutral).

2. **Sentiment Analysis**:
   - Based on the above headlines and any other up-to-date qualitative data, conduct a sentiment analysis for {input_stock}.
   - Justify whether the market is likely to move upward or downward in the next 1-5 trading days.

3. **Macro & Political Context**:
   - Briefly evaluate any important recent political, central bank, or regulatory developments that may influence market sentiment or the sector.

4. **Trading Decision**:
   - Integrate all findings (news sentiment, market structure, macro/political signals).
   - Decide whether to go **Long** or **Short** for optimal short-term capital gains.
   - Define a trade setup with entry, stop loss, and take profit levels.
   - Position duration must not exceed 5 calendar days.

Answer strictly in the following format (strict):


Stock name: <Stock name>
Buy price: $<Buy price>
Take profit: $<Take profit>
Stop loss: $<Stop loss>
Sentiment analysis: <Sentiment analysis>"""

#The template is used to create a prompt for the model
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", system_template),
    ("human", human_template)],
    )

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

        stock_price_request_params = StockLatestTradeRequest(symbol_or_symbols=symbol)
        stockprice = alpaca_data_client.get_stock_latest_trade(stock_price_request_params)
        latest_trade_price=stockprice[symbol].price


        messages=chat_prompt.format_messages(input_stock=symbol, today=current_date, current_stock_price=latest_trade_price) 

        #Saving the output of the model
        result  = chat_model.invoke(messages)
        
        #Printing result of model
        print(result.content)

        #TAKE PROFIT ANPASSEN, DASS ES PASST
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
import yfinance as yf

for ticker in ["AAPL", "TSLA", "2330.TW"]:
    print(f"\n--- 測試 {ticker} ---")
    stock = yf.Ticker(ticker)
    
    try:
        hist = stock.history(period="5d")
        print("股價資料行數:", len(hist))
        if not hist.empty:
            print("最近一筆收盤價:", hist.iloc[-1]['Close'])
        
        news = stock.news
        print("新聞數量:", len(news))
        if news:
            print("第一則新聞標題:", news[0].get('content', {}).get('title'))
    except Exception as e:
        print(f"發生錯誤: {e}")

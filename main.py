import os
import time
import schedule
from dotenv import load_dotenv
from agent import app

# 載入環境變數
load_dotenv()

TICKERS_TO_WATCH = ["AAPL", "TSLA", "2330.TW"]

def job():
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 開始執行異常變動檢查任務...")
    
    # 檢查 API Key 狀態
    if not os.environ.get("GOOGLE_API_KEY"):
        print("警告: 尚未設定 GOOGLE_API_KEY，請確認 .env 檔案。")
        return

    for ticker in TICKERS_TO_WATCH:
        print(f"[{ticker}] 正在分析中...")
        initial_state = {"ticker": ticker}
        
        # 呼叫 LangGraph agent
        try:
            # invoke 會執行整個 Graph，並回傳最後的 State
            result = app.invoke(initial_state)
            
            # 若為測試或除錯，可以印出部分結果
            is_anomalous = result.get("should_alert", False)
            reason = result.get("analysis_result", "")
            
            print(f"[{ticker}] 異常判定: {is_anomalous}")
            if not is_anomalous:
                print(f"[{ticker}] 正常原因: {reason}")
                
        except Exception as e:
            print(f"[{ticker}] 執行過程發生例外錯誤: {e}")
            
    print("檢查任務完成。\n")

if __name__ == "__main__":
    print("啟動【異常變動警報員】排程...")
    print(f"關注清單: {', '.join(TICKERS_TO_WATCH)}")
    print("排程頻率: 每 8 小時一次")
    
    # 啟動時先執行一次，方便確認邏輯無誤
    job()
    
    # 設定每 8 小時執行一次
    schedule.every(8).hours.do(job)
    
    # 進入無窮迴圈，維持程式運行並定時檢查
    while True:
        schedule.run_pending()
        time.sleep(60)

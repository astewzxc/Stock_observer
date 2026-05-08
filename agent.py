import os
import json
import yfinance as yf
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, PushMessageRequest

# 定義 State
class AgentState(TypedDict):
    ticker: str
    price_data: str
    news_data: str
    analysis_result: str
    should_alert: bool

# Node: 取得資料與新聞
def fetch_data_and_news(state: AgentState) -> AgentState:
    ticker = state["ticker"]
    try:
        stock = yf.Ticker(ticker)
        
        # 取得近 5 日股價
        hist = stock.history(period="5d")
        if hist.empty:
            price_str = "無法取得股價資料"
        else:
            # 取出日期與收盤價
            price_list = []
            for date, row in hist.iterrows():
                price_list.append(f"{date.strftime('%Y-%m-%d')}: {row['Close']:.2f}")
            price_str = "\n".join(price_list)
        
        # 取得最新新聞
        news_list = stock.news
        if not news_list:
            news_str = "無最新新聞"
        else:
            news_items = []
            # 取前 5 則新聞
            for n in news_list[:5]:
                content = n.get("content", {})
                title = content.get("title", "無標題")
                provider = content.get("provider", {})
                publisher = provider.get("displayName", "未知來源")
                news_items.append(f"- {title} ({publisher})")
            news_str = "\n".join(news_items)
            
    except Exception as e:
        price_str = f"取得資料發生錯誤: {e}"
        news_str = "無法取得新聞"
        
    return {"price_data": price_str, "news_data": news_str}

# Node: 分析資料
def analyze_data(state: AgentState) -> AgentState:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)
    
    prompt = f"""
請作為一位專業的股市分析師，根據以下股票的近期走勢與新聞，判斷是否有「異常波動」(例如大幅漲跌、趨勢反轉，或有重大影響股價的新聞)。

股票代號: {state['ticker']}
近期股價走勢(收盤價):
{state['price_data']}

近期相關新聞:
{state['news_data']}

請嚴格以 JSON 格式回覆，包含兩個欄位，不要輸出其他 Markdown 語法（如 ```json 等）：
{{
  "is_anomalous": true 或是 false,
  "reason": "說明為何判斷為異常或正常（若為異常，請用繁體中文以專業且精簡的語氣總結原因，此部分將作為警報訊息傳送給使用者；若為正常，也請簡短說明原因）"
}}
"""
    try:
        response = llm.invoke(prompt)
        # 簡單清理可能帶有的 markdown 格式
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
            
        result = json.loads(content)
        is_anomalous = result.get("is_anomalous", False)
        reason = result.get("reason", "無法解析原因")
    except Exception as e:
        is_anomalous = False
        reason = f"分析過程發生錯誤: {str(e)}\n原始回覆: {response.content if 'response' in locals() else '無'}"

    return {"analysis_result": reason, "should_alert": is_anomalous}

# Node: 發送警報
def send_alert(state: AgentState) -> AgentState:
    channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if not channel_access_token or not user_id:
        print(f"[{state['ticker']}] 缺少 LINE API 設定，跳過發送通知。")
        return state
        
    configuration = Configuration(access_token=channel_access_token)
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            message_text = f"⚠️ 【{state['ticker']} 異常波動警報】 ⚠️\n\n{state['analysis_result']}"
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=message_text)]
                )
            )
            print(f"[{state['ticker']}] 成功發送 LINE 警報！")
    except Exception as e:
        print(f"[{state['ticker']}] 發送 LINE 警報失敗: {e}")
        
    return state

# 建立圖的邊緣條件
def should_continue(state: AgentState):
    if state.get("should_alert"):
        return "send_alert"
    return END

# 建立 Graph
workflow = StateGraph(AgentState)
workflow.add_node("fetch_data_and_news", fetch_data_and_news)
workflow.add_node("analyze_data", analyze_data)
workflow.add_node("send_alert", send_alert)

workflow.set_entry_point("fetch_data_and_news")
workflow.add_edge("fetch_data_and_news", "analyze_data")
workflow.add_conditional_edges("analyze_data", should_continue, {
    "send_alert": "send_alert",
    END: END
})
workflow.add_edge("send_alert", END)

# 編譯
app = workflow.compile()

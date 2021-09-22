import time
import pyupbit
import datetime
import requests
import schedule
from fbprophet import Prophet
import numpy as np
import pandas as pd

# 업비트 로그인용 엑세스, 시크릿 키 가져오기 & 슬랙 전송용 토큰 가져오기
with open("upbit.txt") as f:
    lines = f.readlines()
    access = lines[0].strip()
    secret = lines[1].strip()
    myToken = "xoxb-2351359870022-2358308972563-rujG9eGFc3BLngWfHGF3ueOT"

# 슬랙 메시지 전송
def send_slack_message(token, channel, text):
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer "+token},
        data={"channel": channel,"text": text}
    )

# 현재시간 구하기 + 값 출력하기
def get_current_time():
    now = datetime.datetime.now()
    current_time = now.strftime("%Y{} %m{} %d{} %H{} %M{} %S{}").format(*"년월일시분초")
    print("current_time:")
    print(current_time)

# 시작 시간 조회
def get_start_time(ticker):
    df = pyupbit.get_ohlcv(ticker, interval="day", count=1)
    start_time = df.index[0]
    return start_time

# 현재가 조회
def get_current_price(ticker):
    return pyupbit.get_orderbook(tickers=ticker)[0]["orderbook_units"][0]["ask_price"]

# 15일 이동 평균선 조회 + 값 출력하기 + 슬랙으로 보내기
def get_ma15(ticker): # ma15 = moving_average_15days
    global ma15
    df = pyupbit.get_ohlcv(ticker, interval="day", count=15)
    ma15 = df['close'].rolling(15).mean().iloc[-1]
    print("ma15:")
    print(ma15)
    send_slack_message(myToken,"#bitcoinupbit", "ma15: " +str(ma15))

# 잔고 조회
def get_balance(ticker):
    balances = upbit.get_balances()
    for b in balances:
        if b['currency'] == ticker:
            if b['balance'] is not None:
                return float(b['balance'])
            else:
                return 0
    return 0

# 금일 시작 잔고 조회하기 + 값 출력하기 + 슬랙으로 보내기
def get_today_start_balance(ticker):
    global today_start_balance
    get_balance(ticker)
    today_start_balance = get_balance(ticker)
    print("today_start_balance:")
    print(today_start_balance)
    send_slack_message(myToken,"#bitcoinupbit", "today_start_balance: " +str(today_start_balance))

# k값 별 누적ror 구하기
def get_ror(k=0.5):
    df = pyupbit.get_ohlcv("KRW-ETH", count=7)
    df['range'] = (df['high'] - df['low']) * k
    df['target'] = df['open'] + df['range'].shift(1) # range 컬럼 한칸씩 밑으로
    fee = 0.0005 # 업비트 수수료
    df['ror'] = np.where(df['high'] > df['target'],
                         df['close'] / df['target'] - fee,
                         1) # np.where(조건문, 참일때 값, 거짓일때 값)
    cumprod_ror = df['ror'].cumprod()[-2]
    return cumprod_ror

# k값 별 ror 데이터 프레임 만들기
def get_best_k_df():
    global best_k_df
    cumprod_ror_list = []
    ks = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    for k in ks:
        cumprod_ror = get_ror(k)
        cumprod_ror_list.append(cumprod_ror)
    data = {'k': ks, 'cumprod_ror': cumprod_ror_list}
    best_k_df = pd.DataFrame(data=data)

# ror 최대값 구하기 + 값 출력하기
def get_best_k_ror(data_frame, data_column):
    global best_k_ror
    best_k_ror = data_frame[data_column].max()
    print("best_k_ror:")
    print(best_k_ror)

# ror 최대값일때 인덱스 구하기
def get_best_k_index(data_frame, data_column, data_value):
    global best_k_index
    best_k_index_list =  data_frame.index[data_frame[data_column] == data_value].tolist()
    best_k_index = best_k_index_list[0]

# ror이 최대일때 k값 구하기 + 값 출력하기 + 슬랙으로 보내기
def get_best_k(index):
    global best_k
    if index == 0:
        best_k = 0.1
    if index == 1:
        best_k =0.2
    if index == 2:
        best_k =0.3
    if index == 3:
        best_k =0.4
    if index == 4:
        best_k =0.5
    if index == 5:
        best_k =0.6
    if index == 6:
        best_k =0.7
    if index == 7:
        best_k =0.8
    if index == 8:
        best_k =0.9
    print("best_k:")
    print(best_k)
    send_slack_message(myToken,"#bitcoinupbit", "best_k: " +str(best_k))

# 변동성 돌파 전략으로 매수 목표가 조회 + 값 출력하기 + 슬랙으로 보내기
def get_target_price(ticker, k):
    global target_price
    df = pyupbit.get_ohlcv(ticker, interval="day", count=2) # df =data_frame
    target_price = df.iloc[0]['close'] + (df.iloc[0]['high'] - df.iloc[0]['low']) * k
    print("target_price:")
    print(target_price)
    send_slack_message(myToken,"#bitcoinupbit", "target_price: " +str(target_price))

# Prophet으로 당일 종가 가격 예측 + 값 출력하기 + 슬랙으로 보내기
def predict_price(ticker):
    """Prophet으로 당일 종가 가격 예측"""
    global predicted_close_price
    df = pyupbit.get_ohlcv(ticker, interval="minute60")
    df = df.reset_index()
    df['ds'] = df['index']
    df['y'] = df['close']
    data = df[['ds','y']]
    model = Prophet()
    model.fit(data)
    future = model.make_future_dataframe(periods=24, freq='H')
    forecast = model.predict(future)
    closeDf = forecast[forecast['ds'] == forecast.iloc[-1]['ds'].replace(hour=9)]
    if len(closeDf) == 0:
        closeDf = forecast[forecast['ds'] == data.iloc[-1]['ds'].replace(hour=9)]
    closeValue = closeDf['yhat'].values[0]
    predicted_close_price = closeValue
    print("predicted_close_price:")
    print(predicted_close_price)
    send_slack_message(myToken,"#bitcoinupbit", "predicted_close_price: " +str(predicted_close_price))

# 로그인
upbit = pyupbit.Upbit(access, secret)
print("자동매매 시작!!")

# 시작 메세지 슬랙 전송
send_slack_message(myToken,"#bitcoinupbit", "프로그램 시작!!")

# 티커 설정
ticker_a = "KRW-ETH"
ticker_b = "ETH"

# 프로그램 시작할때 필요한 값들 구하기
get_today_start_balance("KRW")
get_ma15(ticker_a)
get_best_k_df()
get_best_k_ror(best_k_df, 'cumprod_ror')
get_best_k_index(best_k_df, 'cumprod_ror', best_k_ror)
get_best_k(best_k_index)
get_target_price(ticker_a, best_k)
predict_price(ticker_a)
get_current_time()

# 필요한 시간별로 예약 설정하기
schedule.every().day.at("08:00").do(lambda: get_today_start_balance("KRW"))
schedule.every().day.at("09:00").do(lambda: get_ma15(ticker_a))
schedule.every().day.at("09:00").do(lambda: get_best_k_df())
schedule.every().day.at("09:00:10").do(lambda: get_best_k_ror(best_k_df, 'cumprod_ror'))
schedule.every().day.at("09:00:20").do(lambda: get_best_k_index(best_k_df, 'cumprod_ror', best_k_ror))
schedule.every().day.at("09:00:30").do(lambda: get_best_k(best_k_index))
schedule.every().day.at("09:00:40").do(lambda: get_target_price(ticker_a, best_k))
schedule.every().hour.do(lambda: predict_price(ticker_a))
schedule.every().hour.do(lambda: get_current_time())

# 자동매매 시작
while True:
    try:
        now = datetime.datetime.now()
        start_time = get_start_time(ticker_a) - datetime.timedelta(hours=1) #08시
        mid_time15 = start_time + datetime.timedelta(hours=7) # 15시
        mid_time16 = start_time + datetime.timedelta(hours=8) # 16시
        mid_time23 = start_time + datetime.timedelta(hours=15) # 23시
        mid_time00 = start_time + datetime.timedelta(hours=16) # 00시
        mid_time07 = start_time + datetime.timedelta(hours=23) # 07시
        end_time = start_time + datetime.timedelta(days=1) # 다음날 08시
        schedule.run_pending() # 실행 예약된 모든 작업을 실행합니다.

        if start_time <= now <= mid_time15: # 08시~15시(7시간동안 매수)
            current_price = get_current_price(ticker_a)
            if target_price < current_price and current_price < predicted_close_price and ma15 < current_price :
                krw = get_balance("KRW")
                if krw > 5000 and krw > today_start_balance*0.6668:
                    buy_result = upbit.buy_market_order(ticker_a, krw*0.3333)
                    send_slack_message(myToken,"#bitcoinupbit","1차매수, " +"BTC buy: " +str(buy_result))      
        elif now <= mid_time16: # 15시~16시 (1시간동안 매도)
            current_price = get_current_price(ticker_a)
            if current_price > predicted_close_price and current_price > target_price:
                btc = get_balance(ticker_b)
                if btc > 5000/current_price:
                    sell_result = upbit.sell_market_order(ticker_a, btc)
                    send_slack_message(myToken,"#bitcoinupbit","1차매도, " +"BTC sell: " +str(sell_result))
        elif now <= mid_time23: # 16시~23시 (7시간동안 매수)
            current_price = get_current_price(ticker_a)
            if target_price < current_price and current_price < predicted_close_price and ma15 < current_price :
                krw = get_balance("KRW")
                if krw > 5000 and krw > today_start_balance*0.3335:
                    buy_result = upbit.buy_market_order(ticker_a, krw*0.5)
                    send_slack_message(myToken,"#bitcoinupbit","2차매수, " +"BTC buy: " +str(buy_result))
        elif now <= mid_time00: # 23시~00시 (1시간동안 매도)
            current_price = get_current_price(ticker_a)
            if current_price > predicted_close_price and current_price > target_price:            
                btc = get_balance(ticker_b)
                if btc > 5000/current_price:
                    sell_result = upbit.sell_market_order(ticker_a, btc)
                    send_slack_message(myToken,"#bitcoinupbit","2차매도, " +"BTC sell: " +str(sell_result))
        elif now <= mid_time07: # 00시~다음날 07시 (7시간동안 매수)
            current_price = get_current_price(ticker_a)
            if target_price < current_price and current_price < predicted_close_price and ma15 < current_price :
                krw = get_balance("KRW")
                if krw > 5000:
                    buy_result = upbit.buy_market_order(ticker_a, krw*0.9995)
                    send_slack_message(myToken,"#bitcoinupbit","3차매수, " +"BTC buy: " +str(buy_result))
        elif now <= end_time - datetime.timedelta(seconds=10): # 다음날 07시 ~ 08시 (1시간동안 매도)
            current_price = get_current_price(ticker_a)
            if current_price > predicted_close_price and current_price > target_price:             
                btc = get_balance(ticker_b)
                if btc > 5000/current_price:
                    sell_result = upbit.sell_market_order(ticker_a, btc)
                    send_slack_message(myToken,"#bitcoinupbit","3차매도, " +"BTC sell: " +str(sell_result))
        else:  # 다음날 08시에 전량 매도
            current_price = get_current_price(ticker_a)
            btc = get_balance(ticker_b)
            if btc > 5000/current_price:
                sell_result = upbit.sell_market_order(ticker_a, btc)
                send_slack_message(myToken,"#bitcoinupbit","종가에 전량 매도!, " +"BTC sell: " +str(sell_result))
        time.sleep(1)
    except Exception as e:
        print(e)
        send_slack_message(myToken,"#bitcoinupbit", e)
        time.sleep(1)
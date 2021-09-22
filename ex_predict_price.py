import pyupbit
import datetime
import schedule
from fbprophet import Prophet


predicted_close_price = 0
# Prophet으로 당일 종가 가격 예측
def predict_price(ticker):
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
    # 현재시간 구하기
    now = datetime.datetime.now()
    current_time = now.strftime("%Y{} %m{} %d{} %H{} %M{} %S{}").format(*"년월일시분초")
    print(current_time)
    print(predicted_close_price)
# Prophet으로 당일 종가 가격 예측(1시간마다)
predicted_close_price = predict_price("KRW-ETH")
print(predicted_close_price)
# 導入
"""

!pip install yfinance

# Commented out IPython magic to ensure Python compatibility.
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt #繪圖庫
from math import sqrt
from sklearn.preprocessing import MinMaxScaler #平均&變異數標準化
from sklearn.metrics import r2_score #模型選擇和評估使用工具
from tensorflow.keras.models import Sequential #順序模型
from tensorflow.keras.layers import Dense,Flatten,Dropout,TimeDistributed #矩陣生成 #資料壓縮 #資料刪減 #時間分佈
from tensorflow.keras.callbacks import EarlyStopping #訓練停止
from tensorflow.keras.optimizers import Adam,schedules #學習率調整 #
from tensorflow.keras.layers import LSTM
from tensorflow.keras import regularizers #正規化
from pandas_datareader import data as web
import datetime
import time
import io
import requests
from keras.utils.vis_utils import plot_model
from sklearn.metrics import r2_score,mean_absolute_error,mean_squared_error
import yfinance as yf
# %matplotlib inline

"""# 資料抓取

"""

def data_download(target,start_date,end_date):
  for i in target:
    data_df=yf.download(target,start=start_date,end=end_date,progress=False)  
  return data_df

def yahoo_finance_futures():
    #Yahoo Finance 網址
    url = "https://finance.yahoo.com/commodities"
    #response = requests.get(url)
    #f = io.StringIO(response.text)
    page=io.StringIO(requests.get(url).text)
    df = pd.read_html(page)
    return df[0]

target_futures = yahoo_finance_futures() #下載yF商品，目的是取得商品代碼用於下載資料
target_futures['Symbol']

all_data = {}

for  i in target_futures['Symbol']: #i 就是上面所有37個商品代碼，BO=F 沒有此日期範圍的資料
    #print(i)
    all_data[i] = data_download(i,'2009-06-01','2022-01-01')
    time.sleep(5)

close = {}

for name, price in all_data.items():
    if len(price) != 0: #如果有資料就讀取下來，
        close[name] = price['Close']

close = pd.DataFrame(close)

close.head()

"""# 資料集整理

"""

close.info()

new_close=close.drop(["RTY=F", "OJ=F","MGC=F","SIL=F"], axis=1) #刪除資料不完整?

new_close.describe()

new_close.to_csv("futures.csv")

#查看相關性
new_close.corr(method='spearman')

##HeatMap Spearman Correlation
import seaborn as sns #matplotlib 為基礎建構的高階繪圖套件
plt.figure(figsize=(24,15))
matrix = np.triu(new_close.corr(method='spearman')) #三角矩陣、相關性 
heat_map = sns.heatmap(new_close.corr(method='spearman'),annot=True,annot_kws={"size":14},cmap= 'YlGnBu',mask=matrix)
heat_map.set_yticklabels(heat_map.get_yticklabels(), rotation=60)#設定Y軸標籤旋轉60度
heat_map.set_xticklabels(heat_map.get_xticklabels(), rotation=60)#設定X軸標籤旋轉60度
plt.tick_params(labelsize=12)
plt.title('Heatmap Spearman Correlation')
plt.style.use('fivethirtyeight')

new_close = new_close.resample('1d').last().dropna(how='all', axis=1).dropna(how='all', axis=0)#resample 重採樣 #dropna 去除空缺值
new_close = new_close.fillna(method='ffill')#填充缺失資料
new_close.isnull().sum()
new_close = new_close.dropna()

# SelectKBest 挑選出K個分數最高的特徵
from sklearn.feature_selection import SelectKBest
from sklearn.feature_selection import f_regression

#特徵的資料集
X=new_close.drop("GC=F", axis=1)

#設定選擇特徵的規則
feature = SelectKBest(k=5, score_func=f_regression)
fit = feature.fit(X,new_close['GC=F'])

#分數與特徵擷取結果可視化
df_score = pd.DataFrame(fit.scores_) 
df_name = pd.DataFrame(X.columns)   
df_feature = pd.concat([df_name,df_score],axis=1)
df_feature.columns = ['feature','Score']  
df_feature.nlargest(5,'Score')

new_close=new_close[['GC=F','ZN=F','ZF=F','SI=F','PA=F','ZC=F']]

new_close

"""# LSTM

"""

def test(data):
  df = new_close
  df=df[data]
  df=df.dropna()

  #直接針對整個資料集進行比例切割，常用之訓練集與預測集比例為8:2
  split_point = int(len(df)*0.8)
  train = df.iloc[:split_point].copy()
  test = df.iloc[split_point:].copy()

  #資料歸一化
  scaler = MinMaxScaler(feature_range=(-1, 1))

  #若資料非一維數據，需將資料做reshape的動作，調整成(資料長度,1) 

  train_set= train.values.reshape(-1,1)
  train_sc = scaler.fit_transform(train_set)

  test_set= test.values.reshape(-1,1)
  test_sc = scaler.fit_transform(test_set)

  predict_days = 1 
  X_train = train_sc[:-predict_days]
  y_train = train_sc[predict_days:]
  X_test = test_sc[:-predict_days]
  y_test = test_sc[predict_days:]

  #確認資料集的形狀，很重要 ！ 
  #可告知別人訓練集與資料集的大小
  X_train = X_train.reshape((X_train.shape[0],1, X_train.shape[1]))
  X_test = X_test.reshape((X_test.shape[0],1, X_test.shape[1]))
  print(X_train.shape, y_train.shape, X_test.shape, y_test.shape)

  #建立LSTM模型
  lstm_model = Sequential()

  #LSTM ：神經元（units） 
  lstm_model.add(LSTM(units=400, return_sequences=False, input_shape=(X_train.shape[1],1)))

  #遺忘層 ： 可調整 Dropout 遺忘率
  lstm_model.add(Dropout(0.2))

  #輸出層 ： 輸出資料的數量
  lstm_model.add(Dense(1))

  #loss : 損失函數
  #optimizer : 優化器
  #metrics : 評估指標
  #其餘的函數設定可參考 [ https://www.tensorflow.org/api_docs/python/tf/keras/Model ]
  lstm_model.compile(loss='mean_squared_error', optimizer='adam',metrics=['accuracy'])

  #使用EarlyStopping避免浪費時間
  early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)

  history_lstm_model = lstm_model.fit(X_train, y_train, epochs=20, batch_size=1, verbose=2, shuffle=False, callbacks=[early_stop])


  y_pred_test_lstm = lstm_model.predict(X_test) #進行預測
  plt.figure(figsize=(10, 6))
  plt.style.use('ggplot')
  plt.plot(y_test[:,0], label='Close')
  plt.plot(y_pred_test_lstm, label='LSTM')
  plt.title("LSTM's Prediction")
  plt.xlabel('Observation')
  plt.ylabel('Close')
  plt.legend()
  plt.show();

  #將歸一化的數據還原
  reduction_Lstm_pred = scaler.inverse_transform(y_pred_test_lstm)
  reduction_test = df.iloc[split_point:].copy()
  reduction_y_test = reduction_test[predict_days:]
  #模型評價
  #mae = mean_absolute_error(reduction_y_test, reduction_Lstm_pred)
  #mse = mean_squared_error(reduction_y_test, reduction_Lstm_pred)
  #rmse = sqrt(mean_squared_error(reduction_y_test, reduction_Lstm_pred))
  #r2 = r2_score(reduction_y_test, reduction_Lstm_pred)

  #模型評價
  mae = mean_absolute_error(y_test, y_pred_test_lstm)
  mse = mean_squared_error(y_test, y_pred_test_lstm)
  rmse = sqrt(mean_squared_error(y_test, y_pred_test_lstm))
  r2 = r2_score(y_test, y_pred_test_lstm)
  return mae,mse,rmse,r2

mae,mse,rmse,r2 = test("GC=F")

#模型評價
print("Mean Absolute Error:", mae)
print('Mean Squared Error:', mse)
print('Root Mean Squared Error:',rmse)
print("Coefficient of Determination:", r2)

mae,mse,rmse,r2  = test("ZN=F")

#模型評價
print("Mean Absolute Error:", mae)
print('Mean Squared Error:', mse)
print('Root Mean Squared Error:',rmse)
print("Coefficient of Determination:", r2)

mae,mse,rmse,r2  = test("ZF=F")

#模型評價
print("Mean Absolute Error:", mae)
print('Mean Squared Error:', mse)
print('Root Mean Squared Error:',rmse)
print("Coefficient of Determination:", r2)

mae,mse,rmse,r2  = test("SI=F")

#模型評價
print("Mean Absolute Error:", mae)
print('Mean Squared Error:', mse)
print('Root Mean Squared Error:',rmse)
print("Coefficient of Determination:", r2)

mae,mse,rmse,r2  = test("PA=F")

#模型評價
print("Mean Absolute Error:", mae)
print('Mean Squared Error:', mse)
print('Root Mean Squared Error:',rmse)
print("Coefficient of Determination:", r2)

mae,mse,rmse,r2  = test("ZC=F")

#模型評價
print("Mean Absolute Error:", mae)
print('Mean Squared Error:', mse)
print('Root Mean Squared Error:',rmse)
print("Coefficient of Determination:", r2)

"""## 探索式資料分析"""

##Line Plots Target & Features
data = new_close
col_names = data.columns

fig = plt.figure(figsize=(12, 24))

plt.style.use('ggplot')
for i in range(6):
  ax = fig.add_subplot(6,1,i+1)
  ax.plot(data.iloc[:,i],label=col_names[i])
  data.iloc[:,i].rolling(100).mean().plot(label='Rolling Mean')
  ax.set_title(col_names[i])
  ax.set_xlabel('Date')
  ax.set_ylabel('Price')
  plt.legend()
fig.tight_layout(pad=3.0)
plt.show()

"""# GC=F 與 ZC=F"""

split_point = int(len(new_close)*0.8)
train = new_close[["ZC=F","GC=F"]].iloc[:split_point].copy()
test = new_close[["ZC=F","GC=F"]].iloc[split_point:-1].copy() #因為預測一天後的結果，最後一天預測並無解答，所以-1

sc1 = MinMaxScaler(feature_range=(0,1))
sc2 = MinMaxScaler(feature_range=(0,1))

def prepare_train_data_lstm(scaler,train_data,n_dim,timesteps):
  input_data = scaler.fit_transform(train_data.values)
  global X_train,y1_train
  X_train= []
  y_train= []
  for i in range(len(input_data)-timesteps-1):
    t=[]
    for j in range(0,timesteps):        
      
        t.append(input_data[[(i+j)], :])
    X_train.append(t)
    y_train.append(input_data[i+ timesteps,0])
  
  X_train, y_train= np.array(X_train), np.array(y_train)
  
  X_train = X_train.reshape(X_train.shape[0],timesteps, n_dim)
  print('Shape of Train Dataset ',X_train.shape)
  return X_train,y_train

def prepare_test_data_lstm(scaler,test_data,n_dim,timesteps):
  inputs = scaler.transform(test_data.values)
  global X_test
  X_test = []
  for i in range(len(inputs)-timesteps-1):
      t=[]
      for j in range(0,timesteps):
        
          t.append(inputs[[(i+j)], :])
      X_test.append(t)
  X_test = np.array(X_test)
  X_test = np.reshape(X_test, (X_test.shape[0], X_test.shape[1], n_dim))
  print('Shape of Test Dataset ',X_test.shape)
  return X_test

def result_metrics_forecast(test_series,forecast_series,model_name):

  print('R2 Score : ',round(r2_score(test_series,forecast_series),4))
  print('Mean Squared Error : ',round(mean_squared_error(test_series,forecast_series),4))
  print('Mean Absolute Error : ',round(mean_absolute_error(test_series,forecast_series),4))
  fig = plt.figure(figsize=(12,6))
  plt.plot(test_series,label='Actual')
  plt.plot(forecast_series,label='Predicted')
  plt.title(model_name)
  plt.ylabel('Price')
  plt.legend()

#調整時間遞移
X_train,y_train = prepare_train_data_lstm(sc1,train,2,1) #(sc1 , train , timesteps)
X_test = prepare_test_data_lstm(sc1,test,2,1) #(sc1 , test , 變數數量 , timesteps)

lstm_model = Sequential()
lstm_model.add(LSTM(units=400, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])))
lstm_model.add(Dropout(0.2))
lstm_model.add(Dense(1))
lstm_model.compile(loss='mean_squared_error', optimizer='adam')
early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)
history_lstm_model = lstm_model.fit(X_train, y_train, epochs=30, batch_size=1, verbose=1, shuffle=True, callbacks=[early_stop])

lstm_all = lstm_model.predict(X_test)

result_metrics_forecast(X_test[:,0][:,0],lstm_all[:,0][:,0],'ZC=F')



"""# GC=F 與 ZN=F"""

split_point = int(len(new_close)*0.8)
train = new_close[["ZN=F","GC=F"]].iloc[:split_point].copy()
test = new_close[["ZN=F","GC=F"]].iloc[split_point:-1].copy() #因為預測一天後的結果，最後一天預測並無解答，所以-1

sc1 = MinMaxScaler(feature_range=(0,1))
sc2 = MinMaxScaler(feature_range=(0,1))

#調整時間遞移
X_train,y_train = prepare_train_data_lstm(sc1,train,2,1) #(sc1 , train , timesteps)
X_test = prepare_test_data_lstm(sc1,test,2,1) #(sc1 , test , 變數數量 , timesteps)

lstm_model = Sequential()
lstm_model.add(LSTM(units=400, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])))
lstm_model.add(Dropout(0.2))
lstm_model.add(Dense(1))
lstm_model.compile(loss='mean_squared_error', optimizer='adam')
early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)
history_lstm_model = lstm_model.fit(X_train, y_train, epochs=30, batch_size=1, verbose=1, shuffle=True, callbacks=[early_stop])

lstm_all = lstm_model.predict(X_test)

result_metrics_forecast(X_test[:,0][:,0],lstm_all[:,0][:,0],'LSTM')

"""# GC=F 與 ZF=F"""

split_point = int(len(new_close)*0.8)
train = new_close[["ZF=F","GC=F"]].iloc[:split_point].copy()
test = new_close[["ZF=F","GC=F"]].iloc[split_point:-1].copy() #因為預測一天後的結果，最後一天預測並無解答，所以-1

sc1 = MinMaxScaler(feature_range=(0,1))
sc2 = MinMaxScaler(feature_range=(0,1))

#調整時間遞移
X_train,y_train = prepare_train_data_lstm(sc1,train,2,1) #(sc1 , train , timesteps)
X_test = prepare_test_data_lstm(sc1,test,2,1) #(sc1 , test , 變數數量 , timesteps)

lstm_model = Sequential()
lstm_model.add(LSTM(units=400, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])))
lstm_model.add(Dropout(0.2))
lstm_model.add(Dense(1))
lstm_model.compile(loss='mean_squared_error', optimizer='adam')
early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)
history_lstm_model = lstm_model.fit(X_train, y_train, epochs=30, batch_size=1, verbose=1, shuffle=True, callbacks=[early_stop])

lstm_all = lstm_model.predict(X_test)

result_metrics_forecast(X_test[:,0][:,0],lstm_all[:,0][:,0],'LSTM')

"""# GC=F 與 PA=F"""

split_point = int(len(new_close)*0.8)
train = new_close[["PA=F","GC=F"]].iloc[:split_point].copy()
test = new_close[["PA=F","GC=F"]].iloc[split_point:-1].copy() #因為預測一天後的結果，最後一天預測並無解答，所以-1

sc1 = MinMaxScaler(feature_range=(0,1))
sc2 = MinMaxScaler(feature_range=(0,1))

#調整時間遞移
X_train,y_train = prepare_train_data_lstm(sc1,train,2,1) #(sc1 , train , timesteps)
X_test = prepare_test_data_lstm(sc1,test,2,1) #(sc1 , test , 變數數量 , timesteps)

lstm_model = Sequential()
lstm_model.add(LSTM(units=400, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])))
lstm_model.add(Dropout(0.2))
lstm_model.add(Dense(1))
lstm_model.compile(loss='mean_squared_error', optimizer='adam')
early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)
history_lstm_model = lstm_model.fit(X_train, y_train, epochs=30, batch_size=1, verbose=1, shuffle=True, callbacks=[early_stop])

lstm_all = lstm_model.predict(X_test)

result_metrics_forecast(X_test[:,0][:,0],lstm_all[:,0][:,0],'LSTM')

"""# GC=F 與 SI=F"""

split_point = int(len(new_close)*0.8)
train = new_close[["SI=F","GC=F"]].iloc[:split_point].copy()
test = new_close[["SI=F","GC=F"]].iloc[split_point:-1].copy() #因為預測一天後的結果，最後一天預測並無解答，所以-1

sc1 = MinMaxScaler(feature_range=(0,1))
sc2 = MinMaxScaler(feature_range=(0,1))

#調整時間遞移
X_train,y_train = prepare_train_data_lstm(sc1,train,2,1) #(sc1 , train , timesteps)
X_test = prepare_test_data_lstm(sc1,test,2,1) #(sc1 , test , 變數數量 , timesteps)

lstm_model = Sequential()
lstm_model.add(LSTM(units=400, return_sequences=True, input_shape=(X_train.shape[1], X_train.shape[2])))
lstm_model.add(Dropout(0.2))
lstm_model.add(Dense(1))
lstm_model.compile(loss='mean_squared_error', optimizer='adam')
early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)
history_lstm_model = lstm_model.fit(X_train, y_train, epochs=30, batch_size=1, verbose=1, shuffle=True, callbacks=[early_stop])

lstm_all = lstm_model.predict(X_test)

result_metrics_forecast(X_test[:,0][:,0],lstm_all[:,0][:,0],'LSTM')

"""# nn model"""

def nn_optimizer():
  lr_schedule = schedules.InverseTimeDecay(
      0.001,
      decay_steps=(X_train.shape[0]/32)*50,
      decay_rate=1,
      staircase=False)
  return Adam(lr_schedule)

nn_model = Sequential()
nn_model.add(Dense(64,kernel_regularizer=regularizers.l2(0.001), activation='relu' ,input_shape=(1, 6)))
nn_model.add(Dense(8))
nn_model.add(Dense(1, activation='sigmoid'))


early_stop = EarlyStopping(monitor='loss', patience=2, verbose=1)
nn_model.compile(loss = "mean_squared_error", 
                  optimizer = nn_optimizer(), 
                  metrics=['accuracy'])
    
history = nn_model.fit(X_train, y_train,  epochs=30, batch_size=1,callbacks= early_stop,verbose=1, shuffle=False)

nn_ans = nn_model.predict(X_test)

result_metrics_forecast(X_test[:,0][:,0],nn_ans[:,0][:,0],'ANN')

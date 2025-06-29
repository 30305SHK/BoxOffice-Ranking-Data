import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

API_KEY = 'e07016f15d66db5770ed678e930f7fc2'

# 연도별 데이터 수집 함수
def collect_yearly_data(year):
    all_data = []
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    delta = timedelta(days=1)

    while start_date <= end_date:
        target_date = start_date.strftime('%Y%m%d')
        url = f"http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
        params = {'key': API_KEY, 'targetDt': target_date}

        try:
            response = requests.get(url, params=params)
            data = response.json()
            daily_list = data['boxOfficeResult']['dailyBoxOfficeList']
            for movie in daily_list:
                all_data.append({
                    '날짜': start_date,
                    '영화명': movie['movieNm'],
                    '개봉일': movie['openDt'],
                    '당일 관객수': movie['audiCnt'],
                    '누적 관객수': movie['audiAcc'],
                    '순위': movie['rank']
                })
        except:
            pass
        start_date += delta

    return pd.DataFrame(all_data)

# 지속 주간 추가
def add_duration_week_column(df):
    df['개봉일'] = pd.to_datetime(df['개봉일'], errors='coerce')
    df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
    df['지속 주간'] = ((df['날짜'] - df['개봉일']).dt.days // 7) + 1
    df['지속 주간'] = df['지속 주간'].fillna(0).astype(int)
    df.loc[df['지속 주간'] < 1, '지속 주간'] = 1
    return df

# 주간/월간 관객수 추가
def add_weekly_monthly_columns(df):
    df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce')
    df['월'] = df['날짜'].dt.month
    df['주'] = df['날짜'].dt.isocalendar().week
    df['당일 관객수'] = pd.to_numeric(df['당일 관객수'], errors='coerce')

    weekly = df.groupby(['영화명', '주'])['당일 관객수'].sum().reset_index().rename(columns={'당일 관객수': '주간 관객수'})
    monthly = df.groupby(['영화명', '월'])['당일 관객수'].sum().reset_index().rename(columns={'당일 관객수': '월간 관객수'})

    df = pd.merge(df, weekly, on=['영화명', '주'], how='left')
    df = pd.merge(df, monthly, on=['영화명', '월'], how='left')
    return df

# 합병 정렬 (이중 기준: 누적 관객수 → 선택 기준)
def merge_sort_double(arr, key):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = merge_sort_double(arr[:mid], key)
    right = merge_sort_double(arr[mid:], key)
    return merge_double(left, right, key)

def merge_double(left, right, key):
    result = []
    while left and right:
        left_key = left[0].get(key, 0)
        right_key = right[0].get(key, 0)

        # 1. 우선 입력된 정렬 기준(key) 비교
        if left_key > right_key:
            result.append(left.pop(0))
        elif left_key < right_key:
            result.append(right.pop(0))
        else:
            # 2. 같으면 '누적 관객수'로 비교
            left_acc = int(left[0]['누적 관객수'])
            right_acc = int(right[0]['누적 관객수'])
            if left_acc >= right_acc:
                result.append(left.pop(0))
            else:
                result.append(right.pop(0))
    result.extend(left or right)
    return result

# Streamlit App
st.title("🎬 영화 박스오피스 데이터 웹앱")

year = st.number_input('연도를 입력하세요 (예: 2025)', min_value=2004, max_value=2025, value=2025, step=1)
year = int(year)  # float형으로 나오므로 int형 변환
sort_key = st.selectbox('정렬 기준 선택:', ['당일 관객수', '주간 관객수', '월간 관객수', '지속 주간', '누적 관객수'])

if st.button('데이터 불러오기 및 정렬'):
    df = collect_yearly_data(year)
    df = add_duration_week_column(df)
    df = add_weekly_monthly_columns(df)

    # 필요 컬럼 변환
    df['누적 관객수'] = pd.to_numeric(df['누적 관객수'], errors='coerce')
    df['당일 관객수'] = pd.to_numeric(df['당일 관객수'], errors='coerce')
    df['주간 관객수'] = pd.to_numeric(df['주간 관객수'], errors='coerce')
    df['월간 관객수'] = pd.to_numeric(df['월간 관객수'], errors='coerce')
    df['개봉일'] = pd.to_datetime(df['개봉일'], errors='coerce')
    df['날짜'] = pd.to_datetime(df['날짜'])
    df['주'] = df['날짜'].dt.isocalendar().week
    df['월'] = df['날짜'].dt.month
    max_daily_row = df.loc[df['당일 관객수'].idxmax()]
    max_weekly_row = df.loc[df['주간 관객수'].idxmax()]
    max_monthly_row = df.loc[df['월간 관객수'].idxmax()]

    # 해당 연도 개봉 영화만
    df_filtered = df[df['개봉일'].dt.year == year]

    # 기준별 idxmax 구하기
    if sort_key == '당일 관객수':
        idx = df_filtered.groupby('영화명')['당일 관객수'].idxmax()
        key_col = '날짜'
        key_name = '최대 당일 관객수 날짜'

    elif sort_key == '주간 관객수':
        idx = df_filtered.groupby('영화명')['주간 관객수'].idxmax()
        key_col = '주'
        key_name = '최대 주간 관객수 주'

    elif sort_key == '월간 관객수':
        idx = df_filtered.groupby('영화명')['월간 관객수'].idxmax()
        key_col = '월'
        key_name = '최대 월간 관객수 월'

    else:
        idx = None
        key_col = None
        key_name = None

# 기본 집계
    df_grouped = df_filtered.groupby('영화명').agg({
    '누적 관객수': 'max',
    '지속 주간': 'max',
    '주간 관객수': 'max',
    '월간 관객수': 'max',
    '당일 관객수': 'max',
    '개봉일': 'first'
    }).reset_index()

# 선택한 기준이 있으면 해당 값 추가
    if idx is not None:
        df_key = df_filtered.loc[idx, ['영화명', key_col]].rename(columns={key_col: key_name})
        df_grouped = df_grouped.merge(df_key, on='영화명', how='left')


    data = df_grouped.to_dict('records')
    sorted_data = merge_sort_double(data, sort_key)
    top30_df = pd.DataFrame(sorted_data[:30])

    st.subheader(f"Top 30 영화 (기준: {sort_key} → 누적 관객수)")
    st.dataframe(top30_df)

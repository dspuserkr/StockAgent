import os
import csv
import re

def sanitize_filename(name):
    """파일명에 사용할 수 없는 문자를 제거하거나 대체합니다."""
    # 파일명으로 사용할 수 없는 문자 제거 (Windows 기준)
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    # 혹시 모를 공백이나 마침표로 끝나는 경우 처리
    name = name.strip()
    if name.endswith('.'):
        name = name[:-1] + '_'
    return name

def save_chart_data_to_csv(start_date, end_date, chart_type, stock_code, stock_name, data_list, accumulated_data):
    """차트 데이터를 CSV 파일로 저장하기 위해 누적합니다.
    실제 파일 쓰기는 write_accumulated_data_to_csv에서 수행됩니다.
    """
    if not data_list:
        # print(f"D0: [{stock_code}] {stock_name} - 저장할 데이터가 없습니다.") # 로그가 너무 많을 수 있어 주석 처리
        return

    # 데이터 누적 시 종목명도 함께 저장 (파일 쓰기 시 재조회 방지)
    if stock_code not in accumulated_data:
        accumulated_data[stock_code] = {"name": stock_name, "data": []}
    
    # API에서 받은 키를 그대로 사용하며 데이터 누적
    accumulated_data[stock_code]["data"].extend(data_list)
    # print(f"D10: [{stock_code}] {stock_name} 데이터 누적: {len(data_list)}개 (총 {len(accumulated_data[stock_code]['data'])}개)")

def write_accumulated_data_to_csv(start_date, end_date, chart_type, stock_code, stock_name_acc, data_to_write_dicts, save_dir):
    if not data_to_write_dicts:
        print(f"경고: [{stock_code}] {stock_name_acc} - 저장할 데이터가 없습니다.")
        return

    print(f"D0: [{stock_code}] {stock_name_acc} - CSV 저장 시작 (데이터 {len(data_to_write_dicts)}건)")
    
    # 데이터 정렬 (일봉: 날짜 오름차순)
    data_to_write_dicts.sort(key=lambda x: x.get('date', ''))
    print(f"D0: [{stock_code}] {stock_name_acc} - 데이터 정렬 완료")

    # CSV 헤더와 API 키 매핑 수정 (43-48줄)
    headers = ["종목코드", "종목명", "일자", "시가", "고가", "저가", "현재가", "거래량", "거래대금",
              "sma5", "sma10", "sma20", "sma60", "sma120", "sma240",
              "ema5", "ema10", "ema20", "ema60", "ema120", "ema240",
              "rsi14", "macd", "macd_sig", "macd_hist",
              "bb_upper", "bb_mid", "bb_lower",
              "stoch_k", "stoch_d",
              "vp_high", "vp_mid", "vp_low"]
    
    output_key_map = {
        "종목코드": "code", "종목명": "종목명", "일자": "date", "시가": "open_price",
        "고가": "high_price", "저가": "low_price", "현재가": "current_price",
        "거래량": "volume", "거래대금": "trading_value_cheon",
        "sma5": "sma5", "sma10": "sma10", "sma20": "sma20", "sma60": "sma60",
        "sma120": "sma120", "sma240": "sma240",
        "ema5": "ema5", "ema10": "ema10", "ema20": "ema20", "ema60": "ema60",
        "ema120": "ema120", "ema240": "ema240",
        "rsi14": "rsi14", "macd": "macd", "macd_sig": "macd_sig", "macd_hist": "macd_hist",
        "bb_upper": "bb_upper", "bb_mid": "bb_mid", "bb_lower": "bb_lower",
        "stoch_k": "stoch_k", "stoch_d": "stoch_d",
        "vp_high": "vp_high", "vp_mid": "vp_mid", "vp_low": "vp_low"
    }

    # 데이터 처리 및 CSV 파일 저장
    processed_rows = []
    invalid_data_count = 0
    for row_dict_from_api in data_to_write_dicts:
        new_row = {}
        new_row["종목명"] = stock_name_acc
        is_valid = True
        
        for header_col in headers:
            if header_col == "종목명":
                continue
            api_key = output_key_map.get(header_col)
            if api_key:
                value = row_dict_from_api.get(api_key, "")
                if header_col == "종목코드":
                    new_row[header_col] = f'="{value}"'
                else:
                    new_row[header_col] = value
                    # 데이터 유효성 검사
                    if header_col in ["시가", "고가", "저가", "현재가", "거래량"] and (not value or value == 0):
                        is_valid = False
            else:
                new_row[header_col] = ""
        
        if is_valid:
            processed_rows.append(new_row)
        else:
            invalid_data_count += 1
            # print(f"D10: [{stock_code}] {stock_name_acc} - 비정상 데이터 발견 (일자: {row_dict_from_api.get('date', 'N/A')})")

    if invalid_data_count > 0:
        # print(f"D10: [{stock_code}] {stock_name_acc} - 총 {invalid_data_count}건의 비정상 데이터 제외됨")
        pass

    # CSV 파일 저장
    sanitized_stock_name = sanitize_filename(stock_name_acc)
    output_file = os.path.join(save_dir, f"{start_date}_{end_date}_{chart_type}_{stock_code}_{sanitized_stock_name}.csv")

    # print(f"D10: [{stock_code}] {stock_name_acc} - CSV 파일 저장 경로: {output_file}")

    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(processed_rows)

    # print(f"D10: [{stock_code}] {stock_name_acc} - CSV 저장 완료: {output_file} ({len(processed_rows)}건)")

def save_stock_data(stock_data, save_dir, file_name):
    """주식 데이터를 CSV 파일로 저장합니다."""
    if not stock_data:
        print(f"경고: 저장할 데이터가 없습니다.")
        return

    output_file = os.path.join(save_dir, file_name)
    
    # CSV 헤더와 API 키 매핑
    headers = ["종목코드", "종목명", "일자", "시가", "고가", "저가", "현재가", "거래량", "거래대금"]
    output_key_map = {
        "종목코드": "code", "종목명": "종목명", "일자": "date", "시가": "open_price",
        "고가": "high_price", "저가": "low_price", "현재가": "current_price",
        "거래량": "volume", "거래대금": "trading_value_cheon"
    }

    # 데이터 처리 및 CSV 파일 저장
    processed_rows = []
    for row_dict in stock_data:
        new_row = {}
        is_valid = True
        
        for header_col in headers:
            api_key = output_key_map.get(header_col)
            if api_key:
                value = row_dict.get(api_key, "")
                if header_col == "종목코드":
                    new_row[header_col] = f'="{value}"'
                else:
                    new_row[header_col] = value
                    # 데이터 유효성 검사
                    if header_col in ["시가", "고가", "저가", "현재가", "거래량"] and (not value or value == 0):
                        is_valid = False
            else:
                new_row[header_col] = ""
        
        if is_valid:
            processed_rows.append(new_row)

    # CSV 파일 저장
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(processed_rows)

    print(f"D1: CSV 저장 완료: {output_file} ({len(processed_rows)}건)")

def generate_missing_candle(prev_candle, missing_date, chart_type="일봉"):
    """누락된 봉을 생성합니다.
    
    Args:
        prev_candle (dict): 직전 봉 데이터
        missing_date (str): 누락된 날짜/시간
        chart_type (str): 차트 타입 ("일봉" 또는 "1분봉")
    
    Returns:
        dict: 생성된 봉 데이터
    """
    if not prev_candle:
        print(f"D0: [generate_missing_candle] 직전 봉 데이터가 없습니다.")
        return None
    
    # 직전 봉 데이터 로깅
    print(f"D0: [generate_missing_candle] 직전 봉 데이터:")
    print(f"D0:   - 종목코드: {prev_candle.get('code', 'N/A')}")
    print(f"D0:   - 시가: {prev_candle.get('open_price', 'N/A')}")
    print(f"D0:   - 고가: {prev_candle.get('high_price', 'N/A')}")
    print(f"D0:   - 저가: {prev_candle.get('low_price', 'N/A')}")
    print(f"D0:   - 종가: {prev_candle.get('current_price', 'N/A')}")
    print(f"D0:   - 거래량: {prev_candle.get('volume', 'N/A')}")
    if chart_type == "일봉":
        print(f"D0:   - 날짜: {prev_candle.get('date', 'N/A')}")
    else:
        print(f"D0:   - 시간: {prev_candle.get('datetime', 'N/A')}")
    
    # 누락된 날짜/시간 로깅
    print(f"D0: [generate_missing_candle] 누락된 날짜/시간: {missing_date}")
    print(f"D0: [generate_missing_candle] 차트 타입: {chart_type}")
        
    new_candle = {
        "code": prev_candle.get("code", ""),
        "open_price": prev_candle.get("current_price", 0),
        "high_price": prev_candle.get("current_price", 0),
        "low_price": prev_candle.get("current_price", 0),
        "current_price": prev_candle.get("current_price", 0),
        "volume": 0,
        "trading_value_cheon": 0
    }
    
    if chart_type == "일봉":
        new_candle["date"] = missing_date
    else:  # 1분봉
        new_candle["datetime"] = missing_date
    
    # 생성된 봉 데이터 로깅
    print(f"D0: [generate_missing_candle] 생성된 봉 데이터:")
    print(f"D0:   - 종목코드: {new_candle['code']}")
    print(f"D0:   - 시가: {new_candle['open_price']}")
    print(f"D0:   - 고가: {new_candle['high_price']}")
    print(f"D0:   - 저가: {new_candle['low_price']}")
    print(f"D0:   - 종가: {new_candle['current_price']}")
    print(f"D0:   - 거래량: {new_candle['volume']}")
    if chart_type == "일봉":
        print(f"D0:   - 날짜: {new_candle['date']}")
    else:
        print(f"D0:   - 시간: {new_candle['datetime']}")
        
    return new_candle

def fill_missing_candles(data_list, start_date, end_date, chart_type="일봉"):
    """누락된 봉을 찾아서 채웁니다.
    
    Args:
        data_list (list): 원본 데이터 리스트
        start_date (str): 시작 날짜 (YYYYMMDD)
        end_date (str): 종료 날짜 (YYYYMMDD)
        chart_type (str): 차트 타입 ("일봉" 또는 "1분봉")
    
    Returns:
        list: 누락된 봉이 채워진 데이터 리스트
    """
    if not data_list:
        print(f"D0: [fill_missing_candles] 원본 데이터가 없습니다.")
        return []
    
    print(f"D0: [fill_missing_candles] 시작 - 차트타입: {chart_type}, 시작일: {start_date}, 종료일: {end_date}")
    print(f"D0: [fill_missing_candles] 원본 데이터 수: {len(data_list)}개")
        
    # 데이터 정렬
    if chart_type == "일봉":
        data_list.sort(key=lambda x: x.get("date", ""))
        date_key = "date"
    else:  # 1분봉
        data_list.sort(key=lambda x: x.get("datetime", ""))
        date_key = "datetime"
    
    # 모든 날짜/시간 생성
    all_dates = []
    if chart_type == "일봉":
        current = start_date
        while current <= end_date:
            all_dates.append(current)
            # 다음 날짜 계산 (YYYYMMDD 형식)
            year = int(current[:4])
            month = int(current[4:6])
            day = int(current[6:8])
            next_day = day + 1
            if next_day > 28:  # 월말 체크
                if month in [4, 6, 9, 11] and next_day > 30:
                    next_day = 1
                    month += 1
                elif month == 2:
                    if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:  # 윤년
                        if next_day > 29:
                            next_day = 1
                            month += 1
                    else:
                        if next_day > 28:
                            next_day = 1
                            month += 1
                elif next_day > 31:
                    next_day = 1
                    month += 1
                    if month > 12:
                        month = 1
                        year += 1
            current = f"{year:04d}{month:02d}{next_day:02d}"
    else:  # 1분봉
        # 1분봉의 경우 9:00~15:30까지의 모든 분 생성
        for hour in range(9, 16):
            for minute in range(60):
                if hour == 15 and minute > 30:  # 15:30 이후는 제외
                    break
                all_dates.append(f"{start_date}{hour:02d}{minute:02d}")
    
    print(f"D0: [fill_missing_candles] 생성된 전체 날짜/시간 수: {len(all_dates)}개")
    
    # 누락된 봉 찾아서 채우기
    filled_data = []
    prev_candle = None
    missing_count = 0
    
    for date in all_dates:
        # 해당 날짜/시간의 데이터 찾기
        current_candle = next((c for c in data_list if c.get(date_key) == date), None)
        
        if current_candle:
            filled_data.append(current_candle)
            prev_candle = current_candle
        elif prev_candle:  # 누락된 봉 발견
            missing_count += 1
            print(f"\nD0: [fill_missing_candles] 누락된 봉 발견: {date}")
            missing_candle = generate_missing_candle(prev_candle, date, chart_type)
            if missing_candle:
                filled_data.append(missing_candle)
    
    print(f"\nD0: [fill_missing_candles] 완료 - 원본: {len(data_list)}개, 누락된 봉: {missing_count}개, 최종: {len(filled_data)}개")
    return filled_data

def process_and_fill_chart_data(data_list, start_date, end_date, chart_type, stock_code, stock_name):
    """차트 데이터를 처리하고 누락된 봉을 채웁니다.
    
    Args:
        data_list (list): 원본 데이터 리스트
        start_date (str): 시작 날짜 (YYYYMMDD)
        end_date (str): 종료 날짜 (YYYYMMDD)
        chart_type (str): 차트 타입 ("일봉" 또는 "1분봉")
        stock_code (str): 종목 코드
        stock_name (str): 종목명
    
    Returns:
        list: 처리된 데이터 리스트
    """
    if not data_list:
        print(f"D0: [{stock_code}] {stock_name} - 처리할 데이터가 없습니다.")
        return []
    
    # 누락된 봉 채우기
    filled_data = fill_missing_candles(data_list, start_date, end_date, chart_type)
    
    if not filled_data:
        print(f"D0: [{stock_code}] {stock_name} - 봉을 채운 후에도 데이터가 없습니다.")
        return []
    
    print(f"D0: [{stock_code}] {stock_name} - 봉 채우기 완료: {len(filled_data)}개")
    return filled_data

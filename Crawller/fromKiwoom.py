import sys
import os
sys.path.append(os.path.dirname(__file__))
import datetime
from PyQt5.QtWidgets import QApplication
from kiwoomAPI import KiwoomAPI
import time
from classGo import Stocks, DailyStockData, MinStockData
from functools import partial
import util
from PyQt5.QtCore import QEventLoop
import pandas as pd
import re
import argparse


# 전역 변수 설정
DAY_MIN = 1 # 1: 일봉, 2: 분봉
DEBUG_MODE_DAY = 1  # 1: 다중종목, 2: 단일종목 (일봉 시)
DEBUG_MODE_MIN = 1  # 1: 다중종목, 2: 단일종목 (분봉 시)
TEST_STOCK_CODE = "000300"  # 단일종목 모드 시 사용할 종목코드

# 날짜 기본값을 오늘 이전으로 수정
today_for_default = datetime.date.today()
yesterday_for_default = today_for_default - datetime.timedelta(days=1)
DEFAULT_START_DATE_DAY = (yesterday_for_default - datetime.timedelta(days=365*2)).strftime("%Y%m%d")
DEFAULT_START_DATE_MIN = (yesterday_for_default - datetime.timedelta(days=30)).strftime("%Y%m%d")
DEFAULT_END_DATE = yesterday_for_default.strftime("%Y%m%d")

START_DATE = "" # 실행 시 사용자 입력 또는 기본값으로 채워짐
END_DATE = ""   # 실행 시 사용자 입력 또는 기본값으로 채워짐

# DEBUG_STOCK_COUNT_MULTI, MAX_STOCKS_FOR_MODE_1_2 변수는 삭제 (종목 수 제한 없음)

# 파일 저장 경로 관련 전역변수
BASE_SAVE_DIR = "D:/StockAgent/CSV"  # CSV 저장 경로를 고정
SAVE_DIR = BASE_SAVE_DIR  # 실제 저장될 폴더 경로

stock_data = []  # 또는 dict 등 원하는 구조

def get_date_str(dt):
    return dt.strftime("%Y%m%d")

def _clean_numeric_str(value_str: str, is_minute_data: bool = False) -> str:
    """
    숫자 문자열에서 부호, 공백 등을 정리하고 순수 숫자 문자열(또는 빈 문자열)로 반환합니다.
    is_minute_data가 True이면 여러 부호(+-, -- 등)를 고려합니다.
    """
    if not isinstance(value_str, str):
        value_str = str(value_str)
    
    cleaned_value = value_str.strip()

    if is_minute_data:
        # 분봉 데이터의 경우 여러 부호 제거 (+, -, +-, -- 등)
        # 가장 뒤에 있는 숫자 부분만 취하도록 시도
        match = re.search(r'(\d+)$', cleaned_value)
        if match:
            cleaned_value = match.group(1)
        else:
            # 부호만 있고 숫자가 없거나, 이상한 문자열이면 빈 문자열로 처리하여 이후 로직에서 0으로 변환되도록 유도
            cleaned_value = "".join(filter(str.isdigit, cleaned_value)) # 모든 부호 제거 시도

    else: # 일봉 데이터 (또는 일반적인 경우) - 앞쪽 부호 한개만 제거
        if cleaned_value.startswith(('+', '-')):
            cleaned_value = cleaned_value[1:]
            
    cleaned_value = cleaned_value.lstrip('0')
    if not cleaned_value: # 모든 문자가 0이었거나, 부호만 있었던 경우
        return "0" # 기본값 0으로 처리
    return cleaned_value

def validate_and_prepare_data(run_mode, raw_stock_data_list, current_stock_code, current_stock_name, start_date_filter, end_date_filter):
    """
    수집된 원본 데이터를 유효성 검사하고, DailyStockData 또는 MinStockData 객체 리스트로 가공합니다.
    """
    processed_data_objects = []
    # print(f"DUMP: validate_and_prepare_data 호출됨. run_mode: {run_mode}, 데이터 수: {len(raw_stock_data_list)}, 시작일: {start_date_filter}, 종료일: {end_date_filter}")

    if not raw_stock_data_list:
        return processed_data_objects

    is_minute_chart = run_mode in [21, 22] # 분봉 모드 여부

    if is_minute_chart:  # 분봉 데이터 처리
        for raw_item in raw_stock_data_list:
            # 날짜/시간 필터링 및 기본 정보 추출
            raw_dt_str = raw_item.get('체결시간', '').strip()
            if not raw_dt_str or len(raw_dt_str) != 14: # YYYYMMDDHHMMSS
                print(f"DEBUG: 분봉 데이터 시간 형식 오류 - 체결시간:{raw_dt_str}, 항목:{raw_item}")
                continue
            item_date_str = raw_dt_str[:8]
            item_time_str = raw_dt_str[8:]
            
            # 날짜 범위 필터링
            if not (start_date_filter <= item_date_str <= end_date_filter):
                continue
                
            try:
                # API에서 받은 문자열 데이터 정리
                data_args = {
                    '종목코드': current_stock_code,
                    '종목명': current_stock_name,
                    '체결시간': raw_dt_str,
                    '시가': ''.join(c for c in str(raw_item.get('시가', '0')) if c.isdigit()),
                    '고가': ''.join(c for c in str(raw_item.get('고가', '0')) if c.isdigit()),
                    '저가': ''.join(c for c in str(raw_item.get('저가', '0')) if c.isdigit()),
                    '현재가': ''.join(c for c in str(raw_item.get('현재가', '0')) if c.isdigit()),
                    '거래량': ''.join(c for c in str(raw_item.get('거래량', '0')) if c.isdigit()),
                    '거래대금': ''.join(c for c in str(raw_item.get('거래대금', '0')) if c.isdigit()),
                    '이격도5': '0',
                    '이격도20': '0',
                    '전일종가': raw_item.get('전일종가', ''),
                    'sma5': '0', 'sma10': '0', 'sma20': '0', 'sma60': '0', 'sma120': '0', 'sma240': '0',
                    'ema5': '0', 'ema10': '0', 'ema20': '0', 'ema60': '0', 'ema120': '0', 'ema240': '0',
                    'rsi14': '0', 'macd': '0', 'macd_sig': '0', 'macd_hist': '0',
                    'bb_upper': '0', 'bb_mid': '0', 'bb_lower': '0',
                    'stoch_k': '0', 'stoch_d': '0',
                    'vp_high': '0', 'vp_mid': '0', 'vp_low': '0'
                }
                
                data_obj = MinStockData(**data_args)
                processed_data_objects.append(data_obj)

            except Exception as e:
                print(f"DEBUG: 분봉 데이터 가공 중 예외 발생 - 항목:{raw_item}, 오류:{e}")
        
        return processed_data_objects

    else:  # 일봉 데이터 처리
        for raw_item in raw_stock_data_list:
            # 날짜 필터링 및 기본 정보 추출
            item_date_str = raw_item.get('일자', '').strip()
            if not item_date_str or len(item_date_str) != 8: # YYYYMMDD
                print(f"DEBUG: 일봉 데이터 날짜 형식 오류 - 일자:{item_date_str}, 항목:{raw_item}")
                continue
            
            # 날짜 범위 필터링
            if not (start_date_filter <= item_date_str <= end_date_filter):
                continue
                
            try:
                # API에서 받은 문자열 데이터 정리 - 모든 부호 제거
                data_args = {
                    '종목코드': current_stock_code,
                    '종목명': current_stock_name,
                    '일자': item_date_str,
                    '시가': ''.join(c for c in raw_item.get('시가', '0') if c.isdigit()).lstrip('0') or '0',
                    '고가': ''.join(c for c in raw_item.get('고가', '0') if c.isdigit()).lstrip('0') or '0',
                    '저가': ''.join(c for c in raw_item.get('저가', '0') if c.isdigit()).lstrip('0') or '0',
                    '현재가': ''.join(c for c in raw_item.get('현재가', '0') if c.isdigit()).lstrip('0') or '0',
                    '거래량': ''.join(c for c in raw_item.get('거래량', '0') if c.isdigit()).lstrip('0') or '0',
                    'sma5': '0', 'sma10': '0', 'sma20': '0', 'sma60': '0', 'sma120': '0', 'sma240': '0',
                    'ema5': '0', 'ema10': '0', 'ema20': '0', 'ema60': '0', 'ema120': '0', 'ema240': '0',
                    'rsi14': '0', 'macd': '0', 'macd_sig': '0', 'macd_hist': '0',
                    'bb_upper': '0', 'bb_mid': '0', 'bb_lower': '0',
                    'stoch_k': '0', 'stoch_d': '0'
                }
                
                data_obj = DailyStockData(**data_args)
                processed_data_objects.append(data_obj)

            except Exception as e:
                print(f"DEBUG: 일봉 데이터 가공 중 예외 발생 - 항목:{raw_item}, 오류:{e}")
        
        return processed_data_objects

# stop.flag 체크 함수 추가
def check_stop_flag():
    stop_flag_path = os.path.join(os.path.dirname(__file__), "stop.flag")
    if os.path.exists(stop_flag_path):
        print("중지 플래그 감지, 안전하게 종료합니다.")
        os.remove(stop_flag_path)
        return True
    return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daymin", required=True, help="일봉/분봉 구분 (예: 일봉, 분봉)")
    parser.add_argument("--start", required=True, help="시작일 (yyyymmdd)")
    parser.add_argument("--end", required=True, help="종료일 (yyyymmdd)")
    args = parser.parse_args()

    # 인자값을 기존 전역변수에 반영
    if args.daymin == "일봉":
        DAY_MIN = 1
        DEBUG_MODE_DAY = 1
        run_mode = 11
        default_start_date_for_mode = DEFAULT_START_DATE_DAY
    else:
        DAY_MIN = 2
        DEBUG_MODE_MIN = 1
        run_mode = 21
        default_start_date_for_mode = DEFAULT_START_DATE_MIN
    START_DATE = args.start
    END_DATE = args.end

    chart_type_str = "일봉" if DAY_MIN == 1 else "1분봉"
    SAVE_DIR = os.path.join(BASE_SAVE_DIR, f"{START_DATE}_{END_DATE}_{chart_type_str}")
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
        print(f"D1: 저장 폴더 생성: {SAVE_DIR}")

    print("\n===== 선택 결과 =====")
    print(f"유형: {chart_type_str}")
    print(f"모드: 전체 종목")
    print(f"START_DATE: {START_DATE}, END_DATE: {END_DATE}")
    print(f"SAVE_DIR: {SAVE_DIR}")
    print(f"run_mode 코드: {run_mode}")

    app = QApplication(sys.argv)
    kiwoom = KiwoomAPI()
    if not kiwoom.login():
        print("D1: 키움증권 OpenAPI 로그인 실패! 프로그램을 종료합니다.")
        sys.exit(1)
    print("D1: 키움증권 OpenAPI 로그인 성공")

    # 프로그램 시작 시 stop.flag 파일 삭제
    stop_flag_path = os.path.join(os.path.dirname(__file__), "stop.flag")
    if os.path.exists(stop_flag_path):
        os.remove(stop_flag_path)

    # 2. 전체 종목 코드 가져오기 및 필터링 (최초 1회 수행)
    print("\nD1: 전체 종목 코드 수집 및 필터링 시작...")
    kospi_codes = kiwoom.get_code_list_by_market("0")
    kosdaq_codes = kiwoom.get_code_list_by_market("10")
    all_codes_str = kospi_codes + ";" + kosdaq_codes
    all_codes_list_from_api = [code.strip() for code in all_codes_str.split(';') if code.strip()]
    print(f"D1: API로부터 받은 총 종목 코드 수: {len(all_codes_list_from_api)}")

    exclusion_keywords = []
    try:
        with open("관리종목, 담보대출불가능종목, ETF, 초저유동성종목, 증거금.txt", 'r', encoding='utf-8') as f:
            exclusion_keywords = [kw.strip() for kw in f.read().split(',') if kw.strip()]
        print(f"D1: 제외 키워드 로드 완료: {len(exclusion_keywords)}개")
    except Exception as e:
        print(f"D1: 제외 키워드 파일 로드 실패: {e}")

    filtered_stocks_obj_list = []
    for code in all_codes_list_from_api:
        stock_name = kiwoom.get_master_code_name(code)
        if not stock_name or any(keyword in stock_name for keyword in exclusion_keywords):
            continue
        filtered_stocks_obj_list.append(Stocks(code, stock_name))
    print(f"D1: 필터링 후 최종 대상 종목 수 (전체): {len(filtered_stocks_obj_list)}")

    # 3. run_mode에 따라 처리 대상 종목 리스트 결정
    target_stocks_for_processing = []
    if DEBUG_MODE_DAY == 1: # 다중(전체) 종목 모드
        target_stocks_for_processing = filtered_stocks_obj_list
        print(f"D1: 다중 종목 모드 선택됨. 처리할 종목 수: {len(target_stocks_for_processing)}")
    elif DEBUG_MODE_DAY == 2: # 단일 종목 모드
        found_test_stock = False
        for stock_obj in filtered_stocks_obj_list:
            if stock_obj.code == TEST_STOCK_CODE:
                target_stocks_for_processing.append(stock_obj)
                found_test_stock = True
                break
        if not found_test_stock: # 필터링된 목록에 없더라도, API가 조회 가능한지 시도
            test_stock_name = kiwoom.get_master_code_name(TEST_STOCK_CODE)
            if test_stock_name: # 유효한 종목명이 반환되면 객체 생성 후 추가
                target_stocks_for_processing.append(Stocks(TEST_STOCK_CODE, test_stock_name))
                print(f"D1: 단일 종목 '{TEST_STOCK_CODE}'({test_stock_name})을 필터링 목록 외에서 추가합니다.")
            else:
                print(f"경고: 단일 종목 코드 '{TEST_STOCK_CODE}'에 대한 정보를 찾을 수 없습니다. 처리 대상 없음.")
        print(f"D1: 단일 종목 모드 선택됨. 처리할 종목: {TEST_STOCK_CODE if target_stocks_for_processing else '없음'}")
    else:
        print(f"경고: 유효하지 않은 디버그 모드({DEBUG_MODE_DAY}). 프로그램을 종료합니다.")
        sys.exit(1)

    if not target_stocks_for_processing:
        print("D1: 최종 처리 대상 종목이 없습니다. 프로그램을 종료합니다.")
        sys.exit(0)
    
    try:
        # 4. 선택된 모드와 종목에 대해 데이터 요청, 처리 및 저장 (공통 로직)
        for idx, stock_obj in enumerate(target_stocks_for_processing):
            if check_stop_flag():
                print("중지 플래그 감지, 프로그램을 즉시 종료합니다.")
                app = QApplication.instance()
                if app is not None:
                    app.quit()
                sys.exit(0)
            current_stock_code = stock_obj.code
            current_stock_name = stock_obj.name
            print(f"\nD1: [{idx+1}/{len(target_stocks_for_processing)}] [{current_stock_name}({current_stock_code})] API 데이터 요청 중...")

            # kiwoom.stock_data는 API 호출 시마다 갱신되므로, 각 종목의 데이터를 별도로 저장해야 함
            raw_data_from_api_single_stock = [] 

            if DAY_MIN == 1: # 일봉
                print(f"D1:  -> 일봉 데이터 요청 (기준일: {END_DATE}, 시작필터: {START_DATE})...")
                kiwoom.request_daily_chart_data(
                    code=current_stock_code,
                    base_date=END_DATE,
                    modify_price_gubun="1", 
                    start_date_for_filter=START_DATE 
                )
                raw_data_from_api_single_stock = list(kiwoom.stock_data) # 복사본 저장
                # 여기에 raw_data_from_api_single_stock 을 콘솔에 출력
                # print(f"D0: [{current_stock_name}] 원본 데이터 {len(raw_data_from_api_single_stock)}건 수집 완료")
                # for idx, item in enumerate(raw_data_from_api_single_stock[:5]):  # 처음 5개만 출력
                #     print(f"D0:   {idx+1}. {item}")
                # if len(raw_data_from_api_single_stock) > 5:
                #     print(f"D0:   ... 외 {len(raw_data_from_api_single_stock)-5}건")
                
                # 여기에 input문으로 pause
                # input(f"UID0: [{current_stock_name}] 원본 데이터 확인 후 Enter를 누르세요...")
                
                # 여기에 유효성 검사 호출, raw_data_from_api_single_stock 과 run_mode를 인자로 주고, 같은 클래스의 결과를 return 받을것
                processed_data_objects = validate_and_prepare_data(
                    run_mode,
                    raw_data_from_api_single_stock,
                    current_stock_code,
                    current_stock_name,
                    START_DATE,
                    END_DATE
                )
                
                # # 여기에 유효성 검사 결과를 콘솔에 출력
                # print(f"D0: [{current_stock_name}] 유효성 검사 결과: {len(processed_data_objects)}건")
                # for idx, item in enumerate(processed_data_objects):  # 모든 항목 출력
                #     print(f"D0:   {idx+1}. {item}")
                
                # # 여기에 input문으로 pause
                # input(f"UID0: [{current_stock_name}] 유효성 검사 결과 확인 후 Enter를 누르세요...")
                
                # 여기에 csv 파일 저장
                if processed_data_objects:
                    data_to_save_dicts = [obj.to_dict() for obj in processed_data_objects]
                    safe_stock_code = util.sanitize_filename(current_stock_code)
                    safe_stock_name = util.sanitize_filename(current_stock_name)
                    chart_type = "일봉" if DAY_MIN == 1 else "분봉"
                    if DAY_MIN == 2:
                        min_date = min(obj.체결시간[:8] for obj in processed_data_objects)
                        max_date = max(obj.체결시간[:8] for obj in processed_data_objects)
                        file_name = f"{min_date}_{max_date}_{chart_type}_{safe_stock_code}_{safe_stock_name}.csv"
                    else:
                        file_name = f"{START_DATE}_{END_DATE}_{chart_type}_{safe_stock_code}_{safe_stock_name}.csv"
                    output_file_path = os.path.join(SAVE_DIR, file_name)
                    
                    try:
                        if DAY_MIN == 1:
                            df_to_save = pd.DataFrame(data_to_save_dicts, columns=DailyStockData.get_csv_headers())
                        else:
                            df_to_save = pd.DataFrame(data_to_save_dicts, columns=MinStockData.get_csv_headers())
                        # 반드시 이격도5, 이격도20 컬럼이 포함되어 csv에 저장됨
                        df_to_save.to_csv(output_file_path, index=False, encoding='utf-8-sig')
                        print(f"D0: [{current_stock_name}] CSV 저장 완료: {output_file_path} ({len(processed_data_objects)}건)")
                    except Exception as e:
                        print(f"에러: [{current_stock_name}] CSV 저장 실패: {e}")
                
                # # 여기에 input문으로 pause
                # input(f"UID0: [{current_stock_name}] CSV 저장 완료 후 Enter를 누르세요...")
            elif DAY_MIN == 2: # 분봉
                print(f"D1:  -> 분봉 데이터 요청 (1분봉, 기준일: {END_DATE}, 시작필터: {START_DATE})...")
                kiwoom.request_minute_chart_data(
                    code=current_stock_code,
                    tick_interval="1",
                    modify_price_gubun="1",
                    start_date_for_filter=START_DATE,
                    end_date_for_filter=END_DATE
                )
                raw_data_from_api_single_stock = list(kiwoom.stock_data) # 복사본 저장
                # # 원본 데이터 콘솔 출력
                # print(f"D0: [{current_stock_name}] 원본 데이터 {len(raw_data_from_api_single_stock)}건 수집 완료")
                # for idx, item in enumerate(raw_data_from_api_single_stock[:5]):  # 처음 5개만 출력
                #     print(f"D0:   {idx+1}. {item}")
                # if len(raw_data_from_api_single_stock) > 5:
                #     print(f"D0:   ... 외 {len(raw_data_from_api_single_stock)-5}건")
                # input(f"UID0: [{current_stock_name}] 원본 데이터 확인 후 Enter를 누르세요...")

                # 유효성 검사 및 객체 변환
                processed_data_objects = validate_and_prepare_data(
                    run_mode,
                    raw_data_from_api_single_stock,
                    current_stock_code,
                    current_stock_name,
                    START_DATE,
                    END_DATE
                )
                # print(f"D0: [{current_stock_name}] 유효성 검사 결과: {len(processed_data_objects)}건")
                # for idx, item in enumerate(processed_data_objects):  # 모든 항목 출력
                #     print(f"D0:   {idx+1}. {item}")
                # input(f"UID0: [{current_stock_name}] 유효성 검사 결과 확인 후 Enter를 누르세요...")

                # CSV 저장
                if processed_data_objects:
                    data_to_save_dicts = [obj.to_dict() for obj in processed_data_objects]
                    safe_stock_code = util.sanitize_filename(current_stock_code)
                    safe_stock_name = util.sanitize_filename(current_stock_name)
                    chart_type = "일봉" if DAY_MIN == 1 else "분봉"
                    if DAY_MIN == 2:
                        min_date = min(obj.체결시간[:8] for obj in processed_data_objects)
                        max_date = max(obj.체결시간[:8] for obj in processed_data_objects)
                        file_name = f"{min_date}_{max_date}_{chart_type}_{safe_stock_code}_{safe_stock_name}.csv"
                    else:
                        file_name = f"{START_DATE}_{END_DATE}_{chart_type}_{safe_stock_code}_{safe_stock_name}.csv"
                    output_file_path = os.path.join(SAVE_DIR, file_name)
                    try:
                        if DAY_MIN == 1:
                            df_to_save = pd.DataFrame(data_to_save_dicts, columns=DailyStockData.get_csv_headers())
                        else:
                            df_to_save = pd.DataFrame(data_to_save_dicts, columns=MinStockData.get_csv_headers())
                        # 반드시 이격도5, 이격도20 컬럼이 포함되어 csv에 저장됨
                        df_to_save.to_csv(output_file_path, index=False, encoding='utf-8-sig')
                        print(f"D0: [{current_stock_name}] CSV 저장 완료: {output_file_path} ({len(processed_data_objects)}건)")
                    except Exception as e:
                        print(f"에러: [{current_stock_name}] CSV 저장 실패: {e}")
                # input(f"UID0: [{current_stock_name}] CSV 저장 완료 후 Enter를 누르세요...")
            else:
                print(f"경고: 알 수 없는 DAY_MIN 값 ({DAY_MIN})으로 [{current_stock_name}] 스킵")
                continue
            
            if idx < len(target_stocks_for_processing) - 1:
                time.sleep(0.3) # 각 종목 API 요청 사이의 최소 대기 시간
    except KeyboardInterrupt:
        print("사용자에 의해 수집이 중단되었습니다. (Ctrl+C)")

    print(f"\n===== 전체 원본 데이터 수집 완료 =====")
    input("Enter를 눌러 데이터 처리 및 저장을 시작합니다...") # 확인 메시지 추가

    # 5. 데이터 유효성 검사, DailyStockData 객체 변환 및 CSV 저장
    print("\n===== 데이터 처리 및 CSV 파일 저장 시작 =====")
    
    # CSV 헤더 결정
    final_csv_headers = []
    if DAY_MIN == 1:
        final_csv_headers = DailyStockData.get_csv_headers()
    else: # 분봉
        final_csv_headers = MinStockData.get_csv_headers()
    print(f"최종 CSV 저장 시 사용할 헤더: {final_csv_headers}")

    for idx, stock_data_block in enumerate(collected_raw_data_for_all_stocks):
        s_code = stock_data_block["code"]
        s_name = stock_data_block["name"]
        s_raw_list = stock_data_block["raw_data_list"]
        # s_run_mode를 collected_raw_data_for_all_stocks에 저장하지 않았으므로, 전역 run_mode를 사용
        # 또는 데이터 수집 시 DAY_MIN을 저장했다면 그것으로 s_run_mode를 재구성할 수 있음.
        # 여기서는 전역 run_mode를 validate_and_prepare_data에 전달합니다.

        print(f"\nD1: [{idx+1}/{len(collected_raw_data_for_all_stocks)}] [{s_name}({s_code})] 데이터 처리 및 저장 시작 (원본 {len(s_raw_list)}건)...")

        processed_stock_data_objects = validate_and_prepare_data(
            run_mode, # 전역 run_mode 사용
            s_raw_list, 
            s_code, 
            s_name,
            START_DATE, # 전역 START_DATE 사용 (필터링 기준일관성)
            END_DATE    # 전역 END_DATE 사용
        )

        if processed_stock_data_objects:
            data_to_save_dicts = [obj.to_dict() for obj in processed_stock_data_objects]
            safe_stock_code_for_file = util.sanitize_filename(s_code)
            file_name = f"{safe_stock_code_for_file}.csv"
            output_file_path = os.path.join(SAVE_DIR, file_name)
            
            try:
                df_to_save = pd.DataFrame(data_to_save_dicts, columns=final_csv_headers)
                df_to_save.to_csv(output_file_path, index=False, encoding='utf-8-sig')
                print(f"D1: [{s_name}] 데이터 저장 완료: {output_file_path} ({len(processed_stock_data_objects)}건)")
            except Exception as e:
                print(f"에러: [{s_name}] CSV 파일 저장 중 오류 발생: {output_file_path}, 오류: {e}")
        else:
            print(f"D1: [{s_name}] 처리 후 저장할 데이터가 없습니다 (필터링 또는 변환 실패).")

        print(f"D1: [{s_name}({s_code})] 데이터 처리 및 저장 완료.")

    print("\n===== 모든 대상 종목 처리 완료 =====")
    app.quit()
    sys.exit(0)

# kiwoomAPI.py
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QObject, pyqtSignal

# 여기에 키움증권 Open API 관련 클래스 및 함수를 정의합니다.
# 예: 로그인, 데이터 요청, 이벤트 처리 등

class KiwoomAPI(QObject): # QObject 상속 추가 (시그널 사용을 위해)
    # 로그인 결과 시그널 정의 (err_code 전달)
    login_result_signal = pyqtSignal(int)
    # 조건검색식 목록 결과 시그널 정의 (dict 형태: {id: name})
    condition_list_signal = pyqtSignal(dict)
    # 계좌 정보 결과 시그널 정의 (dict 형태: {'accounts': [...], 'user_id': '...', 'user_name': '...'})
    account_info_signal = pyqtSignal(dict)
    # 계좌 잔고(opw00018) 결과 시그널 정의 (dict 형태)
    balance_data_signal = pyqtSignal(dict)
    # 보유 종목(opw00018 멀티) 결과 시그널 정의 (list of dict 형태)
    holdings_data_signal = pyqtSignal(list)
    # 조건검색 결과(OnReceiveTrCondition) 시그널 정의 (screen_no, condition_name, code_list)
    condition_tr_result_signal = pyqtSignal(str, str, list)
    # 주식 기본 정보(opt10001) 결과 시그널 정의 (dict 형태)
    stock_basic_info_signal = pyqtSignal(dict)
    # 실시간 조건검색 결과(OnReceiveRealCondition) 시그널 정의 (code, type, cond_name, cond_idx)
    real_condition_update_signal = pyqtSignal(str, str, str, str)
    # 실시간 시세 데이터 업데이트 시그널 정의 (code, fid_data)
    # fid_data는 {fid: value} 형태의 딕셔너리
    real_time_data_update_signal = pyqtSignal(str, dict)
    # 실시간 호가 데이터 업데이트 시그널 추가
    order_book_update_signal = pyqtSignal(str, dict)
    # 체결 데이터 시그널 추가 (gubun, data)
    # data는 GetChejanData로 얻을 수 있는 정보 dict
    chejan_data_signal = pyqtSignal(str, dict)
    # 주문가능금액 시그널 추가 (int 형태)
    buyable_cash_signal = pyqtSignal(int)
    # 미체결 주문 목록 시그널 추가
    unexecuted_orders_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__() # QObject 초기화
        # D10 : print("KiwoomAPI __init__")
        # OCX 컨트롤 생성
        self.ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        # 이벤트 핸들러 연결
        self.ocx.OnEventConnect.connect(self._handler_login)
        self.ocx.OnReceiveConditionVer.connect(self._handler_condition_load) # 조건식 로드 이벤트
        self.ocx.OnReceiveTrData.connect(self._handler_tr_data) # TR 데이터 수신 이벤트 연결
        self.ocx.OnReceiveTrCondition.connect(self._handler_tr_condition) # 조건검색 TR 데이터 수신 이벤트 연결
        self.ocx.OnReceiveRealCondition.connect(self._handler_real_condition) # 실시간 조건검색 이벤트 연결
        self.ocx.OnReceiveRealData.connect(self._handler_real_data) # 실시간 시세 이벤트 연결
        # 주문/체결 이벤트 핸들러 연결 추가
        self.ocx.OnReceiveChejanData.connect(self._handler_chejan_data)

        self.tr_request_data = {} # TR 요청 데이터 저장용 (rqname 구분)
        self.condition_search_requests = {} # 조건검색 요청 저장용 (screen_no 구분)
        self.stock_info_requests = {} # 주식 기본 정보 요청 저장용 {screen_no: code}
        self.real_time_registered_codes = {} # 실시간 시세 등록된 종목 관리 {screen_no: [code1, code2, ...]}
        self.screen_no_counter = 3000 # 일반 TR 화면 번호 카운터
        self.real_cond_screen_no_counter = 4000 # 실시간 조건검색용 화면 번호 카운터
        self.real_time_screen_no_counter = 5000 # 실시간 시세용 화면 번호 카운터 (5000번대 사용)
        self.real_time_fid_list = "10;11;12;13" # 실시간으로 받을 FID 목록 (현재가;전일대비;등락률;누적거래량)
        self.connected = False # 연결 상태 플래그 추가

    def login(self):
        # 로그인 로직
        # D10 : print("Kiwoom API 로그인 시도...")
        # OCX의 CommConnect 메서드 호출 (로그인 창 실행)
        self.ocx.dynamicCall("CommConnect()")

    def get_connect_state(self):
        """API 연결 상태를 반환합니다."""
        # OpenAPI는 GetConnectState() 메서드를 제공함. self.connected 플래그 대신 직접 호출.
        state = self.ocx.dynamicCall("GetConnectState()") # 0: 미연결, 1: 연결
        return state == 1

    def get_condition_load(self):
        """조건검색식 목록 로드를 요청합니다."""
        # D10 : print("조건검색식 목록 로드 요청...")
        self.ocx.dynamicCall("GetConditionLoad()")

    def get_condition_name_list(self):
        """조건검색식 이름 목록을 가져와서 시그널을 발생시킵니다."""
        # D10 : print("조건검색식 이름 목록 요청...")
        data = self.ocx.dynamicCall("GetConditionNameList()") # "id^name;id^name;..."
        if data:
            conditions = {} # {id: name}
            try:
                condition_list = data.split(';')
                for condition in condition_list:
                    if condition:
                        cond_id, cond_name = condition.split('^')
                        conditions[cond_id] = cond_name
                # D10 : print(f"조건검색식 목록 수신: {conditions}")
                self.condition_list_signal.emit(conditions)
            except Exception as e:
                print(f"조건검색식 목록 파싱 오류: {e}, 원본 데이터: {data}")
        else:
            # D10 : print("수신된 조건검색식 목록 없음")
            pass # 목록 없어도 시그널은 빈 dict로 보내도록 수정
            self.condition_list_signal.emit({}) # 빈 목록 시그널

    def get_code_list_by_market(self, market_code):
        """지정된 시장의 종목 코드 리스트를 문자열로 반환합니다.

        :param market_code: '0': 코스피, '10': 코스닥 등
        :return: 종목 코드 리스트 문자열 (구분자: ';')
        """
        # D10 : print(f"{market_code} 시장 코드 목록 요청...")
        codes = self.ocx.dynamicCall("GetCodeListByMarket(QString)", market_code)
        # D10 : print(f"{market_code} 시장 코드 목록 수신 완료 (일부: {codes[:50]}...)")
        return codes

    def get_master_code_name(self, code):
        """종목 코드에 해당하는 종목명을 반환합니다."""
        # print(f"{code} 종목명 요청...") # 너무 많은 로그를 생성할 수 있어 주석 처리
        name = self.ocx.dynamicCall("GetMasterCodeName(QString)", code)
        # print(f"{code} 종목명: {name}") # 너무 많은 로그를 생성할 수 있어 주석 처리
        return name

    def get_account_info(self):
        """로그인 정보를 사용하여 계좌 정보를 가져오고 시그널을 발생시킵니다."""
        # D10 : print("계좌 정보 요청 (GetLoginInfo 사용)...")
        account_cnt = self.ocx.dynamicCall("GetLoginInfo(QString)", "ACCOUNT_CNT")
        acc_nos_str = self.ocx.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        user_id = self.ocx.dynamicCall("GetLoginInfo(QString)", "USER_ID")
        user_name = self.ocx.dynamicCall("GetLoginInfo(QString)", "USER_NAME")

        # ACCNO는 세미콜론으로 구분된 문자열이므로 리스트로 변환
        accounts = acc_nos_str.split(';')[:-1] # 마지막 빈 문자열 제거

        account_data = {
            "account_count": int(account_cnt) if account_cnt else 0,
            "accounts": accounts,
            "user_id": user_id,
            "user_name": user_name
        }
        # D10 : print(f"계좌 정보 수신: {account_data}")
        self.account_info_signal.emit(account_data)
        # return account_data # 직접 반환 대신 시그널 사용
        # return {} # 기존 코드 삭제

    def request_account_balance(self, account_no, password="", screen_no="1001"):
        """계좌평가잔고내역(opw00018) 조회를 요청합니다."""
        # D10 : print(f"{account_no} 계좌 잔고(opw00018) 요청...")
        rqname = "계좌평가잔고내역요청"
        trcode = "opw00018"

        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", password) # 비밀번호 필요시 설정 (API 확인 필요)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2") # 1:합산, 2:개별

        # 요청 데이터 저장 (핸들러에서 구분하기 위함)
        self.tr_request_data[rqname] = {"account_no": account_no}

        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                     rqname, trcode, 0, screen_no)
        if ret == 0:
            # D10 : print(f"'{rqname}' 요청 성공")
            pass # 성공 로그 제거
        else:
            print(f"'{rqname}' 요청 실패: {ret}")
            if rqname in self.tr_request_data:
                del self.tr_request_data[rqname] # 실패 시 저장된 요청 데이터 삭제

    def request_buyable_cash(self, account_no, password="", screen_no="1002"):
        """예수금상세현황(opw00001) 조회를 요청합니다."""
        # D10 : print(f"{account_no} 계좌 주문가능금액(opw00001) 요청...")
        rqname = "예수금상세현황요청"
        trcode = "opw00001"

        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", password)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        # self.ocx.dynamicCall("SetInputValue(QString, QString)", "조회구분", "2") # opw00001에는 조회구분 없음

        # 요청 데이터 저장 (필요시)
        self.tr_request_data[rqname] = {"account_no": account_no}

        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                     rqname, trcode, 0, screen_no)
        if ret == 0:
            # D10 : print(f"'{rqname}' 요청 성공")
            pass # 성공 로그 제거
        else:
            print(f"'{rqname}' 요청 실패: {ret}")
            if rqname in self.tr_request_data:
                del self.tr_request_data[rqname]

    def request_condition_search(self, condition_name, condition_index, is_real_time=False):
        """조건검색 결과 조회를 요청합니다 (일반/실시간)."""
        request_type = "실시간" if is_real_time else "일반"
        screen_no = self._get_unique_screen_no(is_real_time_cond=is_real_time) # 요청 타입에 맞는 화면번호 할당
        # D10 : print(f"{request_type} 조건검색 요청: 화면={screen_no}, 조건명={condition_name}, 인덱스={condition_index}")

        # 요청 정보 저장 (핸들러에서 구분하기 위함)
        self.condition_search_requests[screen_no] = {"name": condition_name, "index": condition_index, "is_real_time": is_real_time}

        search_type = 1 if is_real_time else 0 # 0: 첫 조회, 1: 실시간 조회 등록
        ret = self.ocx.dynamicCall("SendCondition(QString, QString, int, int)",
                                     screen_no, condition_name, condition_index, search_type)

        if ret == 1:
            # D10 : print(f"SendCondition ({request_type}) 요청 성공 (화면={screen_no})")
            pass # 성공 로그 제거
        else:
            print(f"SendCondition ({request_type}) 요청 실패: {ret} (화면={screen_no})")
            if screen_no in self.condition_search_requests:
                del self.condition_search_requests[screen_no]
        return screen_no # 성공/실패 여부와 관계없이 할당된 화면번호 반환

    def stop_real_condition_search(self, screen_no, condition_name, condition_index):
        """실시간 조건검색을 중지합니다."""
        # D10 : print(f"실시간 조건검색 중지 요청: 화면={screen_no}, 조건명={condition_name}, 인덱스={condition_index}")
        self.ocx.dynamicCall("SendConditionStop(QString, QString, int)", screen_no, condition_name, condition_index)
        # D10 : print(f"  -> 화면={screen_no} 실시간 조건 검색 중지 완료.") # 중지 로그 추가

    # --- 화면 번호 관리 --- #
    def _get_unique_screen_no(self, is_real_time_cond=False, is_real_time_data=False):
        if is_real_time_cond:
            self.real_cond_screen_no_counter += 1
            if self.real_cond_screen_no_counter > 4999:
                self.real_cond_screen_no_counter = 4000
            return str(self.real_cond_screen_no_counter)
        elif is_real_time_data:
            self.real_time_screen_no_counter += 1
            if self.real_time_screen_no_counter > 5999: # 5000번대 사용
                self.real_time_screen_no_counter = 5000
            return str(self.real_time_screen_no_counter)
        else: # 일반 TR
            self.screen_no_counter += 1
            if self.screen_no_counter > 3999:
                self.screen_no_counter = 3000
            return str(self.screen_no_counter)

    def request_stock_basic_info(self, code):
        """주식기본정보(opt10001) 조회를 요청합니다."""
        screen_no = self._get_unique_screen_no()
        # D10 : print(f"주식 기본 정보 요청: 화면={screen_no}, 종목코드={code}")
        rqname = "주식기본정보요청"
        trcode = "opt10001"
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)

        # 요청 정보 저장 (핸들러에서 구분하기 위함)
        self.stock_info_requests[screen_no] = code

        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                     rqname, trcode, 0, screen_no)
        if ret == 0:
            # D10 : print(f"'{rqname}' 요청 성공 (화면={screen_no})")
            pass # 성공 로그 제거
        else:
            print(f"'{rqname}' 요청 실패: {ret} (화면={screen_no})")
            if screen_no in self.stock_info_requests:
                del self.stock_info_requests[screen_no]

    # --- 이벤트 핸들러 --- #
    def _handler_login(self, err_code):
        # D10 : print(f"로그인 결과 수신: {err_code}")
        if err_code == 0:
            self.connected = True # 연결 상태 업데이트
        else:
            self.connected = False
        # 메인 윈도우에 로그인 결과 전달
        self.login_result_signal.emit(err_code)

    def _handler_condition_load(self, ret, msg):
        # D10 : print(f"조건식 목록 로드 결과: ret={ret}, msg={msg}")
        if ret == 1:
            self.get_condition_name_list() # 성공 시 이름 목록 가져오기
        else:
            print("조건식 목록 로드 실패")
            # 실패 시 빈 dict 시그널 발생
            self.condition_list_signal.emit({})

    def _handler_tr_data(self, screen_no, rqname, trcode, recordname, prev_next, data_len, err_code, msg1, msg2):
        # # D10 : print(f"TR 데이터 수신: screen={screen_no}, rqname={rqname}, trcode={trcode}")

        try:
            if rqname == "계좌평가잔고내역요청":
                # # D10 : print(f"  -> 계좌잔고(opw00018) 응답 처리 시작 (화면={screen_no})")
                # 싱글 데이터 추출
                total_purchase_amount = self._get_comm_data(trcode, rqname, 0, "총매입금액")
                total_eval_amount = self._get_comm_data(trcode, rqname, 0, "총평가금액")
                total_eval_pl_amount = self._get_comm_data(trcode, rqname, 0, "총평가손익금액") # 수정된 항목명
                total_earning_rate_str = self._get_comm_data(trcode, rqname, 0, "총수익률(%)") # API 응답 형식 확인 필요
                estimated_deposit = self._get_comm_data(trcode, rqname, 0, "추정예탁자산")

                balance_data = {
                    "총매입금액": int(total_purchase_amount) if total_purchase_amount else 0,
                    "총평가금액": int(total_eval_amount) if total_eval_amount else 0,
                    "총평가손익금액": int(total_eval_pl_amount) if total_eval_pl_amount else 0, # 수정된 키
                    "총수익률(%)": float(total_earning_rate_str) if total_earning_rate_str else 0.0, # 실수형으로 변환
                    "추정예탁자산": int(estimated_deposit) if estimated_deposit else 0
                }
                self.balance_data_signal.emit(balance_data)
                # # D10 : print(f"  -> 잔고 데이터 시그널 발생: {balance_data}")

                # 멀티 데이터 추출 (보유 종목)
                count = self.ocx.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
                # # D10 : print(f"  -> 보유 종목 수: {count}")
                holdings_list = []
                for i in range(count):
                    stock_code = self._get_comm_data(trcode, rqname, i, "종목번호").strip()
                    stock_name = self._get_comm_data(trcode, rqname, i, "종목명").strip()
                    holding_qty_str = self._get_comm_data(trcode, rqname, i, "보유수량").strip()
                    purchase_price_str = self._get_comm_data(trcode, rqname, i, "매입단가").strip() # KOA Studio 확인: "매입단가"
                    current_price_str = self._get_comm_data(trcode, rqname, i, "현재가").strip()
                    eval_pl_amount_str = self._get_comm_data(trcode, rqname, i, "평가손익").strip() # KOA Studio 확인: "평가손익"
                    earning_rate_str = self._get_comm_data(trcode, rqname, i, "수익률(%)").strip() # KOA Studio 확인: "수익률(%)"

                    # 종목코드 앞의 'A' 제거
                    stock_code_processed = stock_code[1:] if stock_code.startswith('A') else stock_code

                    try:
                        holding_qty = int(holding_qty_str) if holding_qty_str else 0
                        purchase_price = int(purchase_price_str) if purchase_price_str else 0
                        current_price = int(current_price_str) if current_price_str else 0
                        eval_pl_amount = int(eval_pl_amount_str) if eval_pl_amount_str else 0
                        earning_rate = float(earning_rate_str) if earning_rate_str else 0.0
                    except ValueError as ve:
                        print(f"  경고: opw00018 멀티 데이터 파싱 중 오류 (종목: {stock_name}): {ve}. 해당 항목은 0으로 처리됩니다.")
                        print(f"    -> 원본 값: qty='{holding_qty_str}', 매입가='{purchase_price_str}', 현재가='{current_price_str}', 평가손익='{eval_pl_amount_str}', 수익률='{earning_rate_str}'")
                        holding_qty, purchase_price, current_price, eval_pl_amount, earning_rate = 0, 0, 0, 0, 0.0


                    holdings_list.append({
                        "종목코드": stock_code_processed,
                        "종목명": stock_name,
                        "보유수량": holding_qty,
                        "매입가": purchase_price, # 키 이름 일관성 유지 (main.py _update_holdings_table 과 맞춤)
                        "현재가": current_price,
                        "평가손익": eval_pl_amount,
                        "수익률(%)": earning_rate
                    })
                # D10 : print(f"[KiwoomAPI] Emitting holdings_data_signal: {holdings_list}") # 로그 위치 변경 및 내용 명시
                self.holdings_data_signal.emit(holdings_list)
                # # D10 : print(f"  -> 보유 종목 데이터 시그널 발생 (종목 수: {len(holdings_list)})")

            elif rqname == "예수금상세현황요청":
                # D10 : print(f"  -> 예수금(opw00001) 응답 처리 시작 (화면={screen_no})")
                buyable_cash = self._get_comm_data(trcode, rqname, 0, "주문가능금액")
                # D10 : print(f"    -> 주문가능금액: {buyable_cash}")
                try:
                    self.buyable_cash_signal.emit(int(buyable_cash))
                except ValueError:
                    print(f"오류: 수신된 주문가능금액({buyable_cash})을 숫자로 변환할 수 없습니다.")

            elif rqname == "주식기본정보요청":
                # D10 : print(f"  -> 주식기본정보(opt10001) 응답 처리 시작 (화면={screen_no})")
                code = self._get_comm_data(trcode, rqname, 0, "종목코드").strip()
                name = self._get_comm_data(trcode, rqname, 0, "종목명")
                price = abs(int(self._get_comm_data(trcode, rqname, 0, "현재가"))) # 절대값
                change = self._get_comm_data(trcode, rqname, 0, "전일대비").strip()
                change_rate = self._get_comm_data(trcode, rqname, 0, "등락률").strip()
                volume = self._get_comm_data(trcode, rqname, 0, "거래량").strip()

                stock_info = {
                    "종목코드": code, # 실제 API에서 받은 코드를 사용
                    "현재가": int(price),
                    "전일대비": int(change) if change else 0,
                    "등락률(%)": float(change_rate) if change_rate else 0.0,
                    "거래량": int(volume) if volume else 0
                }
                # D10 : print(f"  -> Emitting stock_basic_info_signal for {code} (from screen {screen_no})")
                self.stock_basic_info_signal.emit(stock_info)

                # 처리 완료 후 화면 번호 사용 해제 (주의: 연속 조회 시 문제될 수 있음)
                # TR 조회는 일반적으로 화면번호 재사용이 가능하지만, 실시간 등록/해제 시에는 주의 필요
                # 일단 TR 조회 완료 후 화면 해제는 주석 처리 (필요시 복구)
                # self.ocx.dynamicCall("DisconnectRealData(QString)", screen_no)
                # print(f"화면 사용 해제: {screen_no}")

        except Exception as e:
            print(f"TR 데이터 수신 중 예외 발생: {e}")

    def _handler_tr_condition(self, screen_no, code_list_str, condition_name, condition_index, next_flag):
        # D10 : print(f"조건검색 TR 데이터 수신: 화면={screen_no}, 조건명={condition_name}, 인덱스={condition_index}")
        # D10 : print(f"  -> 종목코드 리스트(str): '{code_list_str}'")

        if screen_no not in self.condition_search_requests:
            # D10 : print(f"경고: 요청 정보가 없는 화면({screen_no})의 조건검색 결과 수신.")
            return

        request_info = self.condition_search_requests[screen_no]
        is_real_time = request_info.get("is_real_time", False)

        if not is_real_time: # 일반 조회인 경우에만 요청 정보 삭제
            # D10 : print(f"  -> 일반 조건검색 응답 완료. 화면={screen_no} 요청 정보 삭제.")
            del self.condition_search_requests[screen_no]
        # else: 실시간 조회는 중지 시 삭제
            # D10 : print(f"  -> 실시간 조건검색 응답. 화면={screen_no} 요청 정보 유지.")
            pass

        codes = []
        if code_list_str:
            codes = code_list_str.split(';')[:-1] # 마지막 빈 문자열 제거
            codes = [c.strip() for c in codes if c.strip()]
        # D10 : print(f"  -> 파싱된 종목코드 리스트: {codes}")
        self.condition_tr_result_signal.emit(screen_no, condition_name, codes)

    def _handler_real_condition(self, code, event_type, condition_name, condition_index):
        # D10 : print(f"실시간 조건 이벤트 수신: 종목코드={code}, 타입={event_type}, 조건명={condition_name}, 인덱스={condition_index}")
        # event_type: "I"=편입, "D"=이탈
        self.real_condition_update_signal.emit(code, event_type, condition_name, condition_index)

    def register_real_time_stock_data(self, screen_no, code_list_str, fid_list_str):
        """지정된 종목들에 대해 실시간 시세 데이터 수신을 등록합니다."""
        # D10 : print(f"실시간 시세 등록 요청: 화면={screen_no}")
        # D10 : print(f"  -> 종목: {code_list_str}")
        # D10 : print(f"  -> FID: {fid_list_str}")

        # 기존 화면 번호에 등록된 종목 있으면 해제 후 재등록
        if screen_no in self.real_time_registered_codes:
            # D10 : print(f"  -> 기존 화면({screen_no}) 실시간 데이터 해제")
            self.unregister_real_time_stock_data(screen_no)

        ret = self.ocx.dynamicCall("SetRealReg(QString, QString, QString, QString)",
                                   screen_no, code_list_str, fid_list_str, "0") # 0: 최초 등록, 1: 추가 등록

        if ret == 0:
            # D10 : print(f"SetRealReg 성공 (화면={screen_no})")
            self.real_time_registered_codes[screen_no] = code_list_str # 등록된 종목 리스트 저장
            return 0
        else:
            print(f"SetRealReg 실패: {ret} (화면={screen_no})")
            if screen_no in self.real_time_registered_codes:
                del self.real_time_registered_codes[screen_no] # 실패 시 정보 삭제
            return ret

    def unregister_real_time_stock_data(self, screen_no, code_list_str=None):
        """지정된 화면의 실시간 시세 데이터 수신을 해제합니다.
           code_list_str이 None이면 해당 화면의 모든 종목 해제.
           특정 종목만 해제하는 기능은 API 레벨에서 지원하지 않음 (화면 단위 해제만 가능).
        """
        # D10 : print(f"실시간 시세 해제 요청: 화면={screen_no}")

        # 특정 종목 해제는 SetRealRemove로 가능하나, 전체 해제가 더 간단하고 일반적
        # self.ocx.dynamicCall("SetRealRemove(QString, QString)", screen_no, "ALL") # 화면의 모든 종목 해제

        # DisconnectRealData는 해당 화면번호의 모든 실시간 데이터 연결을 끊음 (TR/Real 모두? 확인 필요)
        # SetRealReg으로 등록한 실시간 시세만 해제하려면 SetRealRemove 사용이 더 명확할 수 있음.
        # 우선 DisconnectRealData 사용 (API 문서 상 화면번호와 관련된 모든 실시간 데이터 중지)
        self.ocx.dynamicCall("DisconnectRealData(QString)", screen_no)

        if screen_no in self.real_time_registered_codes:
            # D10 : print(f"  -> 화면={screen_no}의 실시간 등록 정보 삭제")
            del self.real_time_registered_codes[screen_no]
            return True
        else:
            # D10 : print(f"경고: 화면={screen_no}는 실시간 등록 정보가 없습니다.")
            return False

    def _handler_real_data(self, code, real_type, real_data):
        # # D10 : print(f"실시간 데이터 수신: 종목코드={code}, 타입={real_type}") # 매우 빈번하게 호출될 수 있으므로 기본 주석처리
        # # D10 : print(f"  -> 데이터(str): {real_data}") # 이것도 매우 김

        if real_type == "주식체결":
            # # D10 : print(f"  -> 주식체결 데이터 처리 ({code})")
            # 필요한 FID만 추출하여 dict 생성 (여기서는 예시)
            fid_values = { # 필요한 FID와 기본값
                10: None, # 현재가
                11: None, # 전일대비
                12: None, # 등락률
                13: None, # 누적거래량
                15: None, # 거래량 (체결 시점)
                # ... 더 필요한 FID 추가 ...
            }
            for fid_str in self.real_time_fid_list.split(';'):
                if fid_str:
                    fid = int(fid_str)
                    value_str = self.ocx.dynamicCall("GetCommRealData(QString, int)", code, fid).strip()
                    try:
                        # 숫자형 FID는 float 또는 int로 변환 시도
                        if fid in [10, 11, 13, 15]: # 예시: 현재가, 전일대비, 누적거래량, 거래량
                           fid_values[fid] = int(value_str)
                        elif fid == 12: # 등락률
                           fid_values[fid] = float(value_str)
                        else:
                           fid_values[fid] = value_str # 나머지는 문자열
                    except ValueError:
                        # # D10 : print(f"    -> FID {fid} 값('{value_str}') 변환 오류")
                        fid_values[fid] = value_str # 변환 실패 시 문자열로 저장
            # # D10 : print(f"    -> 추출된 FID 데이터: {fid_values}")
            self.real_time_data_update_signal.emit(code, fid_values)

        elif real_type == "주식호가잔량":
            # # D10 : print(f"  -> 주식호가잔량 데이터 처리 ({code})")
            order_book_data = {}
            # FID 41~50: 매도호가, 51~60: 매수호가
            # FID 61~70: 매도호가잔량, 71~80: 매수호가잔량
            for fid in range(41, 81):
                value_str = self.ocx.dynamicCall("GetCommRealData(QString, int)", code, fid).strip()
                order_book_data[str(fid)] = value_str # 호가는 문자열로 처리 (부호 등 포함)
            # # D10 : print(f"    -> 추출된 호가 데이터: {order_book_data}")
            self.order_book_update_signal.emit(code, order_book_data)

        # 다른 real_type 처리 (예: 주식우선호가, 주식거래원 등)
        # else:
            # # D10 : print(f"  -> 처리되지 않은 실시간 타입: {real_type}")
            pass

    # --- 데이터 조회 편의 함수 --- #
    def _get_comm_data(self, trcode, rqname, index, item_name):
        """GetCommData 호출을 감싸는 헬퍼 함수"""
        data = self.ocx.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, index, item_name).strip()
        # # D10 : print(f"    _get_comm_data: TR={trcode}, RQ={rqname}, Idx={index}, Item={item_name} -> '{data}'")
        return data

    def send_order(self, rqname, screen_no, account_no, order_type, code, quantity, price, hoga_gb, order_no=""):
        """주문 전송 (SendOrder) 메서드"""
        # D10 : print(f"주문 전송 요청: RQ={rqname}, Scr={screen_no}, Acc={account_no}, Type={order_type}, Code={code}, Qty={quantity}, Price={price}, Hoga={hoga_gb}, OrgOrderNo={order_no}")
        try:
            ret = self.ocx.dynamicCall("SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                                       [rqname, screen_no, account_no, order_type, code, quantity, price, hoga_gb, order_no])
            # D10 : print(f"  -> SendOrder 반환 코드: {ret} (0이면 성공)")
            if ret != 0:
                print(f"SendOrder 실패: 코드={ret}")
            return ret
        except Exception as e:
            print(f"SendOrder 중 예외 발생: {e}")
            return -999 # 예외 발생 시 음수 반환 (예시)

    # --- 체결 데이터 처리 핸들러 --- #
    def _handler_chejan_data(self, gubun, item_cnt, fid_list):
        """체결 데이터 수신 핸들러"""
        # D10 : print(f"체결 데이터 수신: 구분={gubun}, ItemCount={item_cnt}, FIDList={fid_list}")
        chejan_data_raw = {}
        fids = fid_list.split(';')
        for fid_str_in_list in fids:
            if fid_str_in_list:
                value = self.ocx.dynamicCall("GetChejanData(int)", int(fid_str_in_list)).strip()
                chejan_data_raw[fid_str_in_list] = value

        if gubun == '1': # 잔고 변경 로그 강화
            # D10 : print(f"  [KiwoomAPI._handler_chejan_data] gubun='1' (잔고변경) 수신. chejan_data_raw: {chejan_data_raw}")
            pass

        # FID 설명 (사용자 제공 문서 기반 업데이트)
        fid_map = {
            # --- 공통 FID ---
            '9201': 'account_no',         # 계좌번호
            '9203': 'order_no',           # 주문번호 (체결 시 원주문번호일 수 있음)
            '9001': 'stock_code',         # 종목코드 (앞 'A' 또는 'J' 제거 필요)
            '302':  'stock_name',         # 종목명
            '908':  'order_chejan_time',  # 주문/체결시간 (HHMMSSMS - 문서 확인)

            # --- 주문/체결 관련 FID (gubun='0') ---
            # FID 10은 gubun='0'일 때 문서(42p)에 명확히 안나옴. 913이 주문상태.
            '913':  'order_status_text',  # 주문상태 (예: "접수", "체결") - (문서 42p FID 913)
            '900':  'order_qty',          # 주문수량 (원주문수량)
            '901':  'order_price',        # 주문가격
            '902':  'unexecuted_qty',     # 미체결수량
            '903':  'executed_cumulative_amount', # 체결누계금액 (체결단가 * 체결량의 누적)
            '904':  'original_order_no',  # 원주문번호
            '905':  'order_type_text',    # 주문구분 (+매수, -매도, 정정, 취소 등)
            '906':  'order_hoga_type',    # 매매구분/호가유형 코드 (예: "00" 지정가)
            '907':  'sell_buy_type_code', # 매도수구분코드 ("1": 매도, "2": 매수)
            '909':  'chejan_no',          # 체결번호
            '910':  'executed_price',     # 체결가 (실제 체결된 가격)
            '911':  'executed_qty',       # 체결량 (실제 체결된 수량)
            '912':  'telecom_order_id',   # 통신주문ID (문서 42p)
            '916':  'rejection_reason',   # 거부사유
            '917':  'screen_no_chejan',   # 화면번호
            '919':  'credit_gubun',       # 신용구분 (00:보통, 01:유통융자 등)
            '920':  'loan_date',          # 대출일 (문서 42p)
            '949':  'order_source',       # 통신주문구분 (KOA, HTS, MTS 등)
            '969':  'change_rate_order_event', # 등락율 (주문/체결 이벤트 시점) (문서 42p)

            # --- 잔고 변경 (gubun='1') 관련 FID (체결 발생에 따른 잔고 변화) ---
            '10':   'current_price_balance',# 현재가 (잔고 편입용, 체결 통보의 현재가와 다를 수 있음) - KOA Studio TR목록엔 '평가단가'로도 표현
            '930':  'holding_qty',          # 보유수량
            '931':  'purchase_price_avg',   # 매입단가 (평균단가)
            '990':  'eval_profit_loss',     # 평가손익 (문서 FID 990)
            '8019': 'profit_loss_rate',   # 손익율 (%) (문서 43p FID 8019) - 이 값을 사용
            '27':   'order_possible_qty',   # 주문가능수량
            '933':  'total_purchase_amount',# 총매입금액 (보유수량 * 매입단가)
            '951':  'deposit',            # 예수금 (D+2 예수금)
            '950':  'today_total_sell_pl',# 당일총매도손익
            '1246': 'prev_day_close',     # 전일종가
            '307':  'base_price_balance', # 기준가 (잔고 FID 307 - 문서 43p)
            '945':  'today_net_buy_qty',  # 당일순매수량 (문서 43p)
            '946':  'sell_buy_type_balance',# 매도/매수구분 (잔고용) (문서 43p)
        }

        parsed_data = {}
        for fid, key_name in fid_map.items():
            raw_value = chejan_data_raw.get(fid)
            if raw_value is None: # FID에 해당하는 값이 없는 경우
                # D10 : print(f"  [FID Parser] FID {fid} ('{key_name}') not found in chejan_data_raw. Skipping.")
                continue

            # 타입 변환이 필요한 키와 해당 타입 지정 (int 또는 float)
            conversion_map = {
                # 공통
                'order_no': int, 'original_order_no': int,
                # 주문/체결 (gubun='0')
                'order_qty': int, 'order_price': int, 'unexecuted_qty': int,
                'executed_qty': int, 'executed_price': int, 'executed_cumulative_qty': int,
                'executed_cumulative_amount': int,
                # 잔고 (gubun='1')
                'holding_qty': int, 'purchase_price_avg': int, 'current_price_balance': int,
                'eval_profit_loss': int, # FID 990 (평가손익)
                'profit_loss_rate': float, # FID 8019 (손익율(%))
                'order_possible_qty': int, 'bid_ask_type': int,
                'total_purchase_amount': int, 'deposit': int, 'today_total_sell_pl': int,
                # 신규 추가 (문서 기반)
                 'credit_ratio': float, 'loan_date': str, # 대출일은 문자열로 유지
                 'order_original_qty': int, 'order_type_text': str, # 주문구분(텍스트)는 문자열로 유지
                 'contract_unit': int, 'remaining_days': int,
                 'order_condition': str, # 주문조건은 문자열로 유지
                 'contract_number': str, # 체결번호는 문자열로 유지
            }

            target_type = conversion_map.get(key_name)
            parsed_value = raw_value # 기본적으로는 원본 값

            if target_type:
                try:
                    if target_type is int:
                        parsed_value = int(raw_value)
                    elif target_type is float:
                        parsed_value = float(raw_value)
                    # D10 : print(f"  [FID Parser] Converted FID {fid} ('{key_name}') to {target_type}: '{raw_value}' -> {parsed_value}")
                except ValueError:
                    # D10 : print(f"  [FID Parser] ValueError converting FID {fid} ('{key_name}') to {target_type}: '{raw_value}'. Using 0 or 0.0.")
                    parsed_value = 0 if target_type is int else 0.0
            # else:
                # D10 : print(f"  [FID Parser] No conversion for FID {fid} ('{key_name}'): '{raw_value}'")

            parsed_data[key_name] = parsed_value

        # --- 데이터 가공 및 추가 정보 생성 ---
        parsed_data['gubun'] = gubun

        if gubun == '1': # 잔고 변경 로그 강화
            pl_value = parsed_data.get('eval_profit_loss', 'N/A')
            rate_value = parsed_data.get('profit_loss_rate', 'N/A')
            # D10 : print(f"  [KiwoomAPI._handler_chejan_data] gubun='1' parsed_data 중: eval_profit_loss={pl_value}, profit_loss_rate={rate_value}")
            pass

        if gubun == '0':
            order_type_text = parsed_data.get('order_type_text', '')
            if '+매수' in order_type_text:
                parsed_data['order_action'] = '매수'
            elif '-매도' in order_type_text:
                parsed_data['order_action'] = '매도'
            elif '정정' in order_type_text:
                parsed_data['order_action'] = '정정'
            elif '취소' in order_type_text:
                parsed_data['order_action'] = '취소'
            else:
                parsed_data['order_action'] = order_type_text if order_type_text else '기타주문'

            if 'executed_qty' not in parsed_data: parsed_data['executed_qty'] = 0
            if 'unexecuted_qty' not in parsed_data:
                 order_qty = parsed_data.get('order_qty',0)
                 executed_qty = parsed_data.get('executed_qty',0)
                 parsed_data['unexecuted_qty'] = order_qty - executed_qty
        elif gubun == '1':
            parsed_data['order_action'] = '잔고변경'

        # D10 : print(f"파싱된 체결 데이터 ({'주문/체결' if gubun == '0' else '잔고변경' if gubun == '1' else '기타'}): {parsed_data}")
        self.chejan_data_signal.emit(gubun, parsed_data)

    # --- 주문 실행 로직 (Main Window로 이동 또는 여기서 구현) --- #
    def _execute_order(self):
        # 이 메서드는 실제 주문 로직을 담거나, 메인 윈도우에서 호출될 인터페이스 역할을 할 수 있습니다.
        # 현재는 사용되지 않으므로 pass 처리.
        pass

    # --- 미체결 내역 요청 --- #
    def request_unexecuted_orders(self, account_no, order_status="0", order_type="0", code="", screen_no="2001"):
        """미체결요청(opt10075) 조회를 수행합니다."""
        # D10 : print(f"{account_no} 미체결 내역(opt10075) 요청... (상태:{order_status}, 유형:{order_type}, 종목:{code})")
        rqname = "미체결요청"
        trcode = "opt10075"

        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "전체종목구분", "0" if code else "1") # 0:종목, 1:전체
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "매매구분", order_type) # 0:전체, 1:매도, 2:매수
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "체결구분", order_status) # 0:전체, 1:체결, 2:미체결

        self.tr_request_data[rqname] = {"account_no": account_no}

        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                     rqname, trcode, 0, screen_no)
        if ret == 0:
            # D10 : print(f"'{rqname}' 요청 성공")
            pass
        else:
            print(f"'{rqname}' 요청 실패: {ret}")
            if rqname in self.tr_request_data: del self.tr_request_data[rqname]

    # --- 주문 정보 요청 (주문번호 기반) --- #
    def request_order_info(self, account_no, order_no, screen_no="2002"):
        """주문체결내역 상세(opt10076) 조회를 수행합니다."""
        # D10 : print(f"{account_no} 주문 정보({order_no}) 상세(opt10076) 요청...")
        rqname = "주문정보조회요청"
        trcode = "opt10076"

        self.ocx.dynamicCall("SetInputValue(QString, QString)", "주문번호", order_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "계좌번호", account_no)
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "") # 필요시
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "상장폐지조회구분", "0") # 0:미포함, 1:포함
        self.ocx.dynamicCall("SetInputValue(QString, QString)", "주문상태구분", "0") # 0:전체, 1:접수, 2:체결...

        self.tr_request_data[rqname] = {"account_no": account_no, "order_no": order_no}

        ret = self.ocx.dynamicCall("CommRqData(QString, QString, int, QString)",
                                     rqname, trcode, 0, screen_no)
        if ret == 0:
            # D10 : print(f"'{rqname}' 요청 성공")
            pass
        else:
            print(f"'{rqname}' 요청 실패: {ret}")
            if rqname in self.tr_request_data: del self.tr_request_data[rqname]




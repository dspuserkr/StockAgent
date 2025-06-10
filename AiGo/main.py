# main.py (수정된 내용 포함)

import sys
import json # 추가
import os   # 추가
from collections import deque # 추가
from datetime import datetime, timedelta # timedelta 추가
# QSpinBox, QGroupBox, QMessageBox 추가
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableWidgetItem, QCompleter, QTableWidget, QAbstractItemView, QHeaderView, QLabel, QLineEdit, QListWidget, QMessageBox, QCheckBox, QSpinBox, QGroupBox, QComboBox, QPlainTextEdit, QMenu
from PyQt5.QtCore import Qt, QTimer, QEvent, QStringListModel, pyqtSignal # pyqtSignal 추가 (임시, 실제는 kiwoomAPI에 있어야 함)
from PyQt5.QtGui import QFont, QColor, QBrush, QPalette
from PyQt5 import uic
# kiwoomAPI 임포트
from kiwoomAPI import KiwoomAPI
# Stocks 클래스 임포트
from classGo import Stocks
# 헬퍼 함수 임포트
from classGo import get_name_by_code, get_code_by_name

# UI 파일 로드
form_class = uic.loadUiType("mainWindow.ui")[0]

# 전역 변수 또는 상수 정의 (예: 테이블 컬럼 인덱스)
COL_CODE = 0
COL_NAME = 1
COL_PRICE = 2
COL_CHANGE = 3
COL_CHANGE_RATE = 4
COL_VOLUME = 5

# --- KiwoomAPI 임시 신호 정의 (실제로는 kiwoomAPI.py 에 정의되어야 함) ---
class KiwoomAPISignals:
    unexecuted_orders_signal = pyqtSignal(list)
# ----------------------------------------------------------------------


# 메인 윈도우 클래스
class MyWindow(QMainWindow, form_class):
    def __init__(self):
        super().__init__()
        # setupUi 호출을 먼저 수행
        self.setupUi(self)

        # KiwoomAPI 인스턴스 생성
        self.kiwoom = KiwoomAPI()
        self.conditions = {} # 조건식 목록 저장용
        self.all_stocks = [] # 전체 종목 리스트 저장용
        self.nowStock = None # 현재 선택된 종목 (Stocks 객체)
        self.pending_requests = [] # 요청 대기열
        self.request_timer = QTimer(self) # 요청 타이머 생성
        self.request_timer.setInterval(210) # 요청 간격 설정 (ms)
        self.request_timer.timeout.connect(self._process_next_request)
        self.active_real_time_condition = None # 현재 활성화된 실시간 조건 정보 저장 {screen, name, index}
        self.active_condition_name = None # 현재 활성화된 조건 검색의 이름
        self.active_real_time_data_screen = None # 현재 사용중인 실시간 시세 화면 번호
        self.cell_font_timers = {} # {(row, col): QTimer} 폰트 복원 타이머 관리
        self.flagBold = True # 글꼴 굵기 변경 효과 플래그 추가 (기본값 True)
        self.current_order_book_code = None # 현재 호가 조회 중인 종목 코드
        self.current_order_book_fid_data = {} # 현재 호가 데이터 저장용 딕셔너리 추가
        self.current_account_no = None # 현재 선택된 계좌번호 추가

        # 매수/매도 판단용 코드 Set 추가
        self.condition_result_codes = set() # 현재 조건검색 결과 테이블에 있는 종목 코드
        self.holding_codes = set() # 현재 보유 종목 테이블에 있는 종목 코드
        self.holdings_data = [] # 보유 종목 상세 정보 저장용 리스트 추가
        self.pending_manual_buy_orders = {}  # 수동 매수 주문 추적용 딕셔너리

        # --- 매수 총액 설정 (사용자 요청 기능) ---
        self.buy_total_amount = 100000 # 기본 10만원, 추후 UI 연동 또는 설정으로 변경 가능

        # --- 주문 추적 초기화 ---
        self.active_orders = {} # {rqname: {order_info}} # 모든 주문 추적용

        # --- 최고가 추적 관련 초기화 ---
        self.highest_prices = {} # {종목코드: 최고가}
        self.previous_prices = {} # {종목코드: 직전 시세} 추가

        # --- 슈팅 감지 및 자동매수 관련 초기화 ---
        self.recent_ticks = {} # {종목코드: deque(maxlen=5)} - (timestamp, price, volume, ask_vol, bid_vol)
        self.buy_check_locks = {} # {종목코드: True/False} - 동시 매수 방지용 락
        self.auto_buy_lock_timer = QTimer(self) # 락 해제용 타이머
        self.auto_buy_lock_timer.setInterval(10000) # 락 유지 시간 (예: 10초)
        self.auto_buy_lock_timer.timeout.connect(self._clear_buy_locks)

        # 파일 이름을 현재 스크립트 위치 기준으로 설정
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.highest_price_file = os.path.join(base_dir, "highest_prices.json")
        # D10 : print(f"최고가 저장 파일 경로: {self.highest_price_file}")

        # --- 주기적 저장 타이머 설정 ---
        self.save_timer = QTimer(self)
        self.save_timer.setInterval(600000) # 10분 (10 * 60 * 1000 ms)
        self.save_timer.timeout.connect(self._save_highest_prices)
        # 타이머는 로그인 성공 후 시작

        # --- 미체결 동기화 타이머 설정 ---
        self.order_sync_timer = QTimer(self)
        self.order_sync_timer.setInterval(30000) # 30초 간격으로 미체결 내역 동기화 시도
        self.order_sync_timer.timeout.connect(self._request_unexecuted_orders)
        # 타이머는 로그인 성공 후 시작

        # --- 자동 완성 설정 ---
        self.stock_completer = QCompleter()
        self.stock_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.stock_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.stock_completer.activated[str].connect(self._on_name_completer_activated)
        popup_name = self.stock_completer.popup()
        if popup_name:
            popup_name.clicked.connect(self._on_name_completer_popup_clicked)

        self.code_completer = QCompleter()
        self.code_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.code_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.code_completer.activated[str].connect(self._on_code_completer_activated)
        popup_code = self.code_completer.popup()
        if popup_code:
            popup_code.clicked.connect(self._on_code_completer_popup_clicked)

        # --- 시그널-슬롯 연결 ---
        self.kiwoom.login_result_signal.connect(self._update_login_status)
        self.kiwoom.condition_list_signal.connect(self._update_condition_list)
        self.kiwoom.account_info_signal.connect(self._update_account_info)
        self.kiwoom.balance_data_signal.connect(self._update_balance_table)
        self.kiwoom.holdings_data_signal.connect(self._update_holdings_table)
        self.kiwoom.condition_tr_result_signal.connect(self._update_condition_search_results)
        self.kiwoom.stock_basic_info_signal.connect(self._update_condition_result_item)
        self.kiwoom.real_condition_update_signal.connect(self._update_real_condition_results)
        self.kiwoom.real_time_data_update_signal.connect(self._update_real_time_stock_data)
        self.kiwoom.order_book_update_signal.connect(self.update_order_book)
        self.kiwoom.chejan_data_signal.connect(self._handler_chejan_data) # 체결 시그널 연결
        self.kiwoom.buyable_cash_signal.connect(self._update_buyable_cash_label) # 주문가능금액 시그널 연결 추가

        # --- 미체결 주문 목록 수신 시그널 연결 (kiwoomAPI.py에 구현 필요) ---
        # 임시 KiwoomAPI 시그널 객체 사용
        temp_signals = KiwoomAPISignals() # 실제로는 self.kiwoom.unexecuted_orders_signal 사용
        if hasattr(self.kiwoom, 'unexecuted_orders_signal'):
             self.kiwoom.unexecuted_orders_signal.connect(self._update_order_numbers)
             # D10 : print("KiwoomAPI의 unexecuted_orders_signal 연결됨.")
        else:
             print("경고: KiwoomAPI에 unexecuted_orders_signal이 없습니다. 임시 시그널을 사용합니다.")
             # 임시 시그널 연결 (테스트용)
             # temp_signals.unexecuted_orders_signal.connect(self._update_order_numbers)


        # --- UI 위젯 시그널 연결 ---
        # 기존 위젯들
        if hasattr(self, 'listConditions'):
            self.listConditions.itemClicked.connect(self._on_condition_selected)
        else: print("경고: UI에 listConditions 위젯이 없습니다.")
        if hasattr(self, 'checkBoxAutoDelete'):
            self.checkBoxAutoDelete.stateChanged.connect(self._on_auto_delete_toggled)
        else: print("경고: UI에 checkBoxAutoDelete 위젯이 없습니다.")
        if hasattr(self, 'tableWidgetHoldings'):
            self.tableWidgetHoldings.cellClicked.connect(self._on_stock_selected)
        else: print("경고: UI에 tableWidgetHoldings 위젯이 없습니다.")
        if hasattr(self, 'tableWidgetConditionResults'):
            self.tableWidgetConditionResults.cellClicked.connect(self._on_stock_selected)
        else: print("경고: UI에 tableWidgetConditionResults 위젯이 없습니다.")
        # 이름 입력 필드
        if hasattr(self, 'lineEditNowStockName'):
            self.lineEditNowStockName.setCompleter(self.stock_completer)
            self.lineEditNowStockName.installEventFilter(self)
            self.lineEditNowStockName.returnPressed.connect(self._on_search_by_name)
        else: print("경고: UI에 lineEditNowStockName 위젯이 없습니다.")
        # 코드 입력 필드
        if hasattr(self, 'lineEditNowStockCode'):
            self.lineEditNowStockCode.setCompleter(self.code_completer)
            self.lineEditNowStockCode.installEventFilter(self)
            self.lineEditNowStockCode.returnPressed.connect(self._on_search_by_code)
        else: print("경고: UI에 lineEditNowStockCode 위젯이 없습니다.")

        # --- 주문 관련 UI 시그널 연결 ---
        # 매수 그룹박스
        if hasattr(self, 'btnSendOrderBuy'): # 이름 수정: btnSendOrder -> btnSendOrderBuy
            self.btnSendOrderBuy.clicked.connect(self._execute_order)
        else: print("경고: UI에 btnSendOrderBuy 위젯이 없습니다.") # 경고 메시지도 수정
        if hasattr(self, 'comboHogaTypeBuy'):  # 이름 수정: comboHogaType -> comboHogaTypeBuy
            hoga_index = self.comboHogaTypeBuy.findText("시장가")
            if hoga_index != -1:
                self.comboHogaTypeBuy.setCurrentIndex(hoga_index)
            self.comboHogaTypeBuy.currentIndexChanged.connect(self._on_hoga_type_changed)
            self._on_hoga_type_changed(self.comboHogaTypeBuy.currentIndex())  # 초기 상태 업데이트
        else:
            print("경고: UI에 comboHogaTypeBuy 위젯이 없습니다.")  # 경고 메시지도 수정

        # 매도 그룹박스 (새로 추가)
        if hasattr(self, 'btnSendOrderSell'):
            self.btnSendOrderSell.clicked.connect(self._execute_order) # 기존 함수 재활용
        else: print("경고: UI에 btnSendOrderSell 위젯이 없습니다.")
        if hasattr(self, 'comboHogaTypeSell'):
            hoga_index = self.comboHogaTypeSell.findText("시장가")
            if hoga_index != -1:
                self.comboHogaTypeSell.setCurrentIndex(hoga_index)
            self.comboHogaTypeSell.currentIndexChanged.connect(self._on_hoga_type_changed)
        else:
            print("경고: UI에 comboHogaTypeSell 위젯이 없습니다.")
        if hasattr(self, 'comboOrderTypeSell'):
            # "매도" 항목의 인덱스를 찾아 기본값으로 설정
            sell_index = self.comboOrderTypeSell.findText("매도")
            if sell_index != -1:
                self.comboOrderTypeSell.setCurrentIndex(sell_index)
            else:
                print("경고: comboOrderTypeSell 에서 '매도' 항목을 찾을 수 없습니다.")
        else: print("경고: UI에 comboOrderTypeSell 위젯이 없습니다.")

        # 호가창 -> 주문 준비 버튼 시그널 연결 (새로 추가)
        if hasattr(self, 'btToBuyOrder'):
            self.btToBuyOrder.clicked.connect(self._prepare_order_from_order_book)
            # D10 : print("btToBuyOrder 시그널 연결됨.")
        else: print("경고: UI에 btToBuyOrder 위젯이 없습니다.")

        if hasattr(self, 'btToSellOrder'):
            self.btToSellOrder.clicked.connect(self._prepare_order_from_order_book)
            # D10 : print("btToSellOrder 시그널 연결됨.")
        else: print("경고: UI에 btToSellOrder 위젯이 없습니다.")

        # --- UI 요소 초기화 ---
        self._setup_account_table()
        self._setup_balance_table()
        self._setup_holdings_table()
        self._setup_condition_results_table()
        self.init_order_book_tables()

        # 프로그램 시작 시 자동 로그인 시도
        self._load_highest_prices() # 로그인 전 일단 로드 시도 (파일이 있다면)
        self.kiwoom.login()

    # --- 최고가 파일 로드/저장 메서드 ---
    def _load_highest_prices(self):
        """highest_prices.json 파일에서 최고가 데이터를 로드합니다."""
        try:
            if os.path.exists(self.highest_price_file):
                with open(self.highest_price_file, 'r', encoding='utf-8') as f:
                    self.highest_prices = json.load(f)
                # D10 : print(f"최고가 데이터 로드 완료. {len(self.highest_prices)}개 종목.")
            else:
                # D10 : print("최고가 데이터 파일이 존재하지 않습니다. 새로 시작합니다.")
                self.highest_prices = {}
        except json.JSONDecodeError:
            print(f"오류: 최고가 데이터 파일({self.highest_price_file}) 형식이 잘못되었습니다. 데이터를 초기화합니다.")
            self.highest_prices = {}
        except Exception as e:
            print(f"최고가 데이터 로드 중 오류 발생: {e}")
            self.highest_prices = {} # 오류 시 초기화

    def _save_highest_prices(self):
        """현재 최고가 데이터를 highest_prices.json 파일에 저장합니다."""
        # D10 : print("최고가 데이터 저장 시도...")
        try:
            with open(self.highest_price_file, 'w', encoding='utf-8') as f:
                json.dump(self.highest_prices, f, ensure_ascii=False, indent=4)
            # D10 : print(f"최고가 데이터 저장 완료. {len(self.highest_prices)}개 종목. 파일: {self.highest_price_file}")
        except Exception as e:
            print(f"최고가 데이터 저장 중 오류 발생: {e}")

    # --- Setup Methods ---
    def _setup_account_table(self):
        if hasattr(self, 'tableWidgetAccounts'):
            self.tableWidgetAccounts.setColumnCount(3)
            self.tableWidgetAccounts.setHorizontalHeaderLabels(["계좌번호", "사용자ID", "사용자명"])
            # D10 : print("계좌 정보 테이블 컬럼 설정 완료.")

    def _setup_balance_table(self):
        if hasattr(self, 'tableWidgetBalance'):
            headers = ["총매입금액", "총평가금액", "총손익금액", "총수익률(%)", "추정예탁자산", "계좌번호"]
            self.tableWidgetBalance.setColumnCount(len(headers))
            self.tableWidgetBalance.setHorizontalHeaderLabels(headers)
            self.tableWidgetBalance.setRowCount(1)
            # D10 : print("계좌 잔고 테이블 컬럼 설정 완료.")

    def _setup_holdings_table(self):
        if hasattr(self, 'tableWidgetHoldings'):
            headers = ["종목코드", "종목명", "보유수량", "매입가", "현재가", "평가손익", "수익률(%)"]
            self.tableWidgetHoldings.setColumnCount(len(headers))
            self.tableWidgetHoldings.setHorizontalHeaderLabels(headers)
            # D10 : print("보유 종목 테이블 컬럼 설정 완료.")

    def _setup_condition_results_table(self):
        if hasattr(self, 'tableWidgetConditionResults'):
            headers = [""] * (COL_VOLUME + 1)
            headers[COL_CODE] = "종목코드"
            headers[COL_NAME] = "종목명"
            headers[COL_PRICE] = "현재가"
            headers[COL_CHANGE] = "전일대비"
            headers[COL_CHANGE_RATE] = "등락률(%)"
            headers[COL_VOLUME] = "거래량"
            self.tableWidgetConditionResults.setColumnCount(len(headers))
            self.tableWidgetConditionResults.setHorizontalHeaderLabels(headers)
            # D10 : print("조건검색 결과 테이블 컬럼 설정 완료.")

    # --- KiwoomAPI Signal Handlers ---
    def _update_login_status(self, err_code):
        if err_code == 0:
            self.lblLogin.setText("로그인 성공")
            # D10 : print("전체 종목 코드 및 이름 가져오기 시작...")
            kospi_codes_str = self.kiwoom.get_code_list_by_market('0')
            kosdaq_codes_str = self.kiwoom.get_code_list_by_market('10')
            kospi_codes = kospi_codes_str.split(';') if kospi_codes_str else []
            kosdaq_codes = kosdaq_codes_str.split(';') if kosdaq_codes_str else []
            all_codes = kospi_codes + kosdaq_codes
            # D10 : print(f"총 {len(all_codes)}개 종목 코드 확인")
            stock_list = []
            for code in all_codes:
                if code:
                    name = self.kiwoom.get_master_code_name(code)
                    if name:
                        stock_list.append(Stocks(code, name, 0)) # current_price=0으로 초기화
            # D10 : print(f"--- 총 {len(stock_list)}개 Stocks 객체 생성 완료 ---")
            self.all_stocks = stock_list
            # D10 : print("Calling _setup_completers after populating all_stocks...")
            self._setup_completers()

            # D10 : print("로그인 성공. 최고가 주기적 저장 타이머 시작.")
            self.save_timer.start() # 타이머 시작
            # 로그인 후 데이터 로드 재시도 (혹시 파일이 그새 생겼거나 할 경우 대비)
            self._load_highest_prices()

            # D10 : print("계좌 정보 요청 시작...")
            self.kiwoom.get_account_info()
            self.kiwoom.get_condition_load()
        else:
            self.lblLogin.setText(f"로그인 실패 (에러 코드: {err_code})")
            # 로그인 실패 시 타이머 시작 안함
            pass

    def _update_condition_list(self, condition_dict):
        # D10 : print("UI 조건검색식 목록 업데이트")
        self.conditions = condition_dict
        if hasattr(self, 'listConditions'):
            self.listConditions.clear()
            for condition_name in condition_dict.values():
                self.listConditions.addItem(condition_name)
        else: print("경고: UI에 listConditions 위젯이 없습니다.")

    def _update_account_info(self, account_data):
        # D10 : print("UI 계좌 정보 업데이트")
        accounts = account_data.get('accounts', [])
        user_id = account_data.get('user_id', '')
        user_name = account_data.get('user_name', '')

        if hasattr(self, 'tableWidgetAccounts'):
            self.tableWidgetAccounts.setRowCount(0)
            if accounts:
                self.tableWidgetAccounts.setRowCount(len(accounts))
                for row, acc_no in enumerate(accounts):
                    self.tableWidgetAccounts.setItem(row, 0, QTableWidgetItem(acc_no))
                    self.tableWidgetAccounts.setItem(row, 1, QTableWidgetItem(user_id))
                    self.tableWidgetAccounts.setItem(row, 2, QTableWidgetItem(user_name))
                self.tableWidgetAccounts.resizeColumnsToContents()
            else: # D10 : print("표시할 계좌 정보 없음 (테이블)")
                pass
        else: print("오류: UI에 tableWidgetAccounts가 없습니다.")

        # 계좌 콤보박스(매수/매도) 모두 업데이트
        if hasattr(self, 'comboAccountBuy'):
            self.comboAccountBuy.clear()
            self.comboAccountBuy.addItems(accounts)
        else:
            print("경고: UI에 comboAccountBuy 위젯이 없습니다.")
        if hasattr(self, 'comboAccountSell'):
            self.comboAccountSell.clear()
            self.comboAccountSell.addItems(accounts)
        else:
            print("경고: UI에 comboAccountSell 위젯이 없습니다.")

        if accounts:
            self.current_account_no = accounts[0] # 첫 번째 계좌를 현재 계좌로 설정
            # D10 : print(f"현재 계좌번호 설정됨: {self.current_account_no}")
            # D10 : print(f"첫 번째 계좌({self.current_account_no}) 잔고 및 주문가능금액 요청...")
            self.kiwoom.request_account_balance(self.current_account_no) # opw00018
            self.kiwoom.request_buyable_cash(self.current_account_no)   # opw00001 추가 호출
        else:
            self.current_account_no = None # 계좌가 없으면 None으로 설정
            # D10 : print("조회할 계좌 없음. current_account_no를 None으로 설정.")
            pass

    def _update_balance_table(self, balance_data):
        # D10 : print("UI 계좌 잔고 업데이트")
        # D10 : print(f"  수신 데이터: {balance_data}")
        if hasattr(self, 'tableWidgetAccountBalance'):
            # 기존 테이블 내용 삭제 (헤더 제외)
            # self.tableWidgetAccountBalance.setRowCount(0)

            # 표시할 항목과 순서 정의 (key: balance_data의 키, label: 테이블에 표시될 한글명)
            items_to_display = [
                {'key': '총매입금액', 'label': '총매입금액'},
                {'key': '총평가금액', 'label': '총평가금액'},
                {'key': '총평가손익금액', 'label': '총평가손익금액'}, # 수정된 키
                {'key': '총수익률(%)', 'label': '총수익률(%)'},
                {'key': '추정예탁자산', 'label': '추정예탁자산'}
            ]

            self.tableWidgetAccountBalance.setRowCount(len(items_to_display))

            for row, item_info in enumerate(items_to_display):
                data_key = item_info['key']
                label_text = item_info['label']

                # 항목명 아이템 설정
                label_item = QTableWidgetItem(label_text)
                self.tableWidgetAccountBalance.setItem(row, 0, label_item)

                # 값 아이템 설정
                value = balance_data.get(data_key)
                value_str = ""
                if value is not None:
                    if data_key == '총수익률(%)':
                        try:
                            value_str = f"{float(value):.2f}%"
                        except ValueError:
                            value_str = str(value) # 변환 실패시 원본 표시
                    else:
                        try:
                            value_str = f"{int(value):,}"
                        except ValueError:
                            value_str = str(value) # 변환 실패시 원본 표시
                
                value_item = QTableWidgetItem(value_str)
                value_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tableWidgetAccountBalance.setItem(row, 1, value_item)
        else:
            # D10 : print("경고: tableWidgetAccountBalance 가 UI에 정의되지 않았습니다.")
            pass

    def _update_holdings_table(self, holdings_list):
        """보유 종목 정보를 QTableWidgetHoldings에 업데이트합니다."""
        # D10 : print("UI 보유 종목 업데이트")
        # D10 : print(f"  수신 데이터 (타입: {type(holdings_list)}): {holdings_list}")
        # D10 : print(f"Updating holdings table with: {holdings_list}")

        if hasattr(self, 'tableWidgetHoldings'):
            self.tableWidgetHoldings.setRowCount(0) # 기존 내용 초기화

        self.holdings_data = holdings_list # 수신된 데이터를 멤버 변수에 저장
        
        # 종목코드가 비어있는 경우 종목명으로 찾아서 채워넣기
        for item_data in self.holdings_data:
            if not item_data.get("종목코드") and item_data.get("종목명"):
                code = get_code_by_name(item_data["종목명"], self.all_stocks)
                if code:
                    item_data["종목코드"] = code
                    # D10 : print(f"종목코드 채워넣기: {item_data['종목명']} -> {code}")
        
        self.tableWidgetHoldings.setRowCount(len(self.holdings_data)) # 저장된 데이터 사용
        headers = [self.tableWidgetHoldings.horizontalHeaderItem(i).text() for i in range(self.tableWidgetHoldings.columnCount())]

        for row, item_data in enumerate(self.holdings_data):
            # D10 : print(f"holdings_data[{row}]: {item_data}")  # 전체 데이터 출력
            code = item_data.get("종목코드")
            if not code:
                print(f"경고: row {row}의 종목코드가 비어 있음. 데이터: {item_data}")
                continue  # 또는 빈칸으로 표시
            name = item_data.get("종목명")
            quantity = item_data.get("보유수량")
            purchase_price = item_data.get("매입가")
            current_price = item_data.get("현재가")
            gain_loss = item_data.get("평가손익", 0) # API에서 제공하는 값 사용
            gain_loss_rate = item_data.get("수익률(%)", 0.0) # API에서 제공하는 값 사용
            self.tableWidgetHoldings.setItem(row, 0, QTableWidgetItem(code))
            self.tableWidgetHoldings.setItem(row, 1, QTableWidgetItem(name))
            self.tableWidgetHoldings.setItem(row, 2, QTableWidgetItem(str(quantity)))
            self.tableWidgetHoldings.setItem(row, 3, QTableWidgetItem(str(purchase_price)))
            self.tableWidgetHoldings.setItem(row, 4, QTableWidgetItem(str(current_price)))
            self.tableWidgetHoldings.setItem(row, 5, QTableWidgetItem(f"{gain_loss:,}")) # 포맷팅 추가
            self.tableWidgetHoldings.setItem(row, 6, QTableWidgetItem(f"{gain_loss_rate:.2f}%")) # 소수점 2자리 포맷팅
        self.tableWidgetHoldings.resizeColumnsToContents()
        self.holding_codes = {item_data["종목코드"] for item_data in self.holdings_data if item_data.get("종목코드")} # 저장된 데이터 사용
        # D10 : print(f"Updated holding_codes: {len(self.holding_codes)} items. Holdings data count: {len(self.holdings_data)}") # 로그 강화

        # --- 최고가 데이터 초기화/업데이트 로직 ---
        # D10 : print("보유 종목 기준 최고가 데이터 초기화/확인 시작...")
        updated_count = 0
        initialized_count = 0
        for item_data in self.holdings_data:
            code = item_data.get("종목코드")
            if code:
                if code not in self.highest_prices:
                    # 최고가 데이터에 없는 보유 종목이면 매입가로 초기화
                    purchase_price = item_data.get("매입가", 0)
                    if purchase_price > 0:
                        self.highest_prices[code] = purchase_price
                        print(f"  -> 최고가 초기화: {code} = {purchase_price:,} (매입가 기준)")
                        initialized_count += 1
                    else:
                         print(f"  -> 경고: {code}의 매입가가 0 이하({purchase_price})이므로 최고가 초기화 불가.")
                # else:
                    # 이미 있는 경우는 건드리지 않음 (실시간 데이터로 업데이트되거나 유지됨)
                    # # D10 : print(f"  -> 최고가 확인: {code} = {self.highest_prices[code]:,}") # 로그 필요시 해제

        # D10 : print(f"최고가 데이터 초기화 완료. 신규 초기화: {initialized_count}개.")
        # 보유 목록 업데이트 후 저장 한번 수행 (선택 사항)
        # self._save_highest_prices()

        if self.holdings_data:
            # D10 : print("보유종목 holdings_data 샘플:", self.holdings_data[0])
            pass
        else:
            # D10 : print("보유종목 holdings_data가 비어있음")
            pass

    def _update_condition_search_results(self, screen_no, condition_name, code_list):
        # D10 : print(f"UI 조건검색 결과 업데이트 시작 (화면={screen_no}, 조건명={condition_name}, 종목수={len(code_list)})")
        if not hasattr(self, 'tableWidgetConditionResults'):
            print("오류: UI에 tableWidgetConditionResults가 없습니다."); return
        self.tableWidgetConditionResults.setRowCount(len(code_list))
        headers = [self.tableWidgetConditionResults.horizontalHeaderItem(i).text() for i in range(self.tableWidgetConditionResults.columnCount())]
        self.pending_requests.clear()
        if self.request_timer.isActive(): self.request_timer.stop()
        if self.active_real_time_data_screen:
            print(f"Unregistering previous real-time data from screen {self.active_real_time_data_screen}")
            self.kiwoom.unregister_real_time_stock_data(self.active_real_time_data_screen)
            self.active_real_time_data_screen = None
        self._clear_all_font_timers()
        codes_to_register_realtime = []
        for row, code in enumerate(code_list):
            stock_name = get_name_by_code(code, self.all_stocks) or ""
            item_data = {"종목코드": code, "종목명": stock_name}
            if code:
                self.pending_requests.append(code)
                codes_to_register_realtime.append(code)
            for col, key in enumerate(headers):
                value = item_data.get(key, "")
                table_item = QTableWidgetItem(str(value))
                if key in ["현재가", "전일대비", "거래량", "등락률(%)"]:
                    table_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tableWidgetConditionResults.setItem(row, col, table_item)
        if self.pending_requests:
            # D10 : print(f"Starting QTimer for {len(self.pending_requests)} stock info requests...")
            self.request_timer.start()
        else: self.tableWidgetConditionResults.resizeColumnsToContents()
        if codes_to_register_realtime:
            # D10 : print(f"Registering real-time data for {len(codes_to_register_realtime)} stocks...")
            realtime_screen_no = self.kiwoom._get_unique_screen_no(is_real_time_data=True)
            code_str = ";".join(codes_to_register_realtime)
            fid_str = self.kiwoom.real_time_fid_list
            ret = self.kiwoom.register_real_time_stock_data(realtime_screen_no, code_str, fid_str)
            if ret == 0:
                self.active_real_time_data_screen = realtime_screen_no
                # D10 : print(f"Real-time data registration successful, screen: {self.active_real_time_data_screen}")
            else:
                # D10 : print(f"Real-time data registration failed (ret={ret}).")
                self.active_real_time_data_screen = None
        self.condition_result_codes = set(codes_to_register_realtime)
        # D10 : print(f"Updated condition_result_codes: {len(self.condition_result_codes)} items")

        # --- 실시간 최고가 업데이트 로직 추가 ---
        # 아래 로직은 _update_real_time_stock_data 메서드에서 처리되므로 여기서는 주석 처리합니다.
        # if code in self.holding_codes: # 보유 종목인 경우에만
        #     current_price_val = fid_data.get(10) # FID 10: 현재가
        #     if current_price_val is not None:
        #         try:
        #             current_price = int(current_price_val) # 정수로 변환 시도
        #             stored_highest = self.highest_prices.get(code, 0) # .get()으로 안전하게 접근
        #
        #             if current_price > stored_highest:
        #                 self.highest_prices[code] = current_price
        #                 stock_name = get_name_by_code(code, self.all_stocks) or ""
        #                 print(f"*** 최고가 갱신 *** {stock_name}({code}): {stored_highest:,} -> {current_price:,}")
        #                 # 최고가 갱신 시 바로 저장 (선택 사항, 빈번할 수 있음)
        #                 # self._save_highest_prices()
        #
        #         except ValueError:
        #             # print(f"실시간 가격({current_price_val})을 숫자로 변환 불가 - {code}") # 너무 자주 나올 수 있어 주석 처리
        #             pass
        #     # else:
        #         # print(f"FID 10 (현재가) 데이터 없음 - {code}") # 로그 필요시 해제
        #
        # # --- 기존 매수/매도 점검 로직 --- #
        # # 아래 로직은 _update_real_time_stock_data 메서드에서 처리되므로 여기서는 주석 처리합니다.
        # if code in self.condition_result_codes: self._check_buy_condition(code, fid_data)
        # if code in self.holding_codes: self._check_sell_condition(code, fid_data)

    def _update_condition_result_item(self, stock_info):
        code = stock_info.get("종목코드")
        # print(f"  -> _update_condition_result_item called for code: {code}") # 주석 처리
        if not code or not hasattr(self, 'tableWidgetConditionResults'): return
        target_row = -1
        for row in range(self.tableWidgetConditionResults.rowCount()):
            item = self.tableWidgetConditionResults.item(row, 0)
            if item and item.text() == code: target_row = row; break
        # print(f"  -> Found target row {target_row} for code {code}") # 주석 처리
        if target_row != -1:
            def update_cell(row, col, value, format_str="{:,}", color=None, align=Qt.AlignRight | Qt.AlignVCenter):
                display_text = ""
                if isinstance(value, (int, float)):
                    if format_str.endswith("%"):
                        display_text = format_str.format(value)
                        if value > 0: display_text = "+" + display_text
                    elif format_str == "{:+,}": display_text = format_str.format(value)
                    else: display_text = format_str.format(value)
                else: display_text = str(value)
                item = self.tableWidgetConditionResults.item(row, col) or QTableWidgetItem()
                item.setText(display_text)
                item.setTextAlignment(align)
                item.setForeground(color if color else Qt.black)
                if not self.tableWidgetConditionResults.item(row, col):
                    self.tableWidgetConditionResults.setItem(row, col, item)
            price = stock_info.get("현재가", 0); change = stock_info.get("전일대비", 0)
            change_rate = stock_info.get("등락률(%)", 0.0); volume = stock_info.get("거래량", 0)
            price_color = Qt.red if change > 0 else (Qt.blue if change < 0 else Qt.black)
            change_color = Qt.red if change > 0 else (Qt.blue if change < 0 else Qt.black)
            rate_color = Qt.red if change_rate > 0 else (Qt.blue if change_rate < 0 else Qt.black)
            update_cell(target_row, COL_CODE, code)
            update_cell(target_row, COL_PRICE, price, color=price_color)
            update_cell(target_row, COL_CHANGE, change, format_str="{:+,}", color=change_color)
            update_cell(target_row, COL_CHANGE_RATE, change_rate, format_str="{:.2f}%", color=rate_color)
            update_cell(target_row, COL_VOLUME, volume)
        else: print(f"경고: 테이블에서 종목코드 '{code}'를 찾을 수 없음 (상세 정보 업데이트 실패)")

    def _update_real_condition_results(self, code, event_type, condition_name, condition_index):
        event_desc = "편입" if event_type == "I" else "이탈"
        print(f"[실시간 조건 업데이트] {condition_name}: {code} {event_desc}")
        if event_type == "I": # 편입
            target_row = -1
            for row in range(self.tableWidgetConditionResults.rowCount()):
                item = self.tableWidgetConditionResults.item(row, 0)
                if item and item.text() == code: target_row = row; break
            if target_row == -1:
                row_count = self.tableWidgetConditionResults.rowCount()
                self.tableWidgetConditionResults.insertRow(row_count)
                target_row = row_count
                stock_name = get_name_by_code(code, self.all_stocks) or ""
                self.tableWidgetConditionResults.setItem(target_row, COL_CODE, QTableWidgetItem(code))
                self.tableWidgetConditionResults.setItem(target_row, COL_NAME, QTableWidgetItem(stock_name))
                if code not in self.pending_requests:
                    self.pending_requests.append(code)
                    if not self.request_timer.isActive(): self.request_timer.start()
                if self.active_real_time_data_screen:
                    current_codes = set(self.kiwoom.real_time_registered_codes.get(self.active_real_time_data_screen, "").split(';'))
                    if code not in current_codes:
                        current_codes.add(code)
                        code_str = ";".join(filter(None, current_codes))
                        fid_str = self.kiwoom.real_time_fid_list
                        print(f"  -> 재등록 요청 (편입): {code}")
                        self.kiwoom.register_real_time_stock_data(self.active_real_time_data_screen, code_str, fid_str)
                self.condition_result_codes.add(code)
                print(f"  -> 조건 결과 편입: {code}, 현재 Set 크기: {len(self.condition_result_codes)}")
            else: print(f"  -> 종목 {code} 이미 테이블에 존재 (행 {target_row})")
        elif event_type == "D": # 이탈
            target_row = -1
            for row in range(self.tableWidgetConditionResults.rowCount()):
                item = self.tableWidgetConditionResults.item(row, 0)
                if item and item.text() == code: target_row = row; break
            if target_row != -1:
                print(f"  -> 조건 결과 테이블에서 {code} (행 {target_row}) 제거")
                self.tableWidgetConditionResults.removeRow(target_row)
                self._clear_timers_for_row(target_row)
                if code in self.condition_result_codes:
                    self.condition_result_codes.remove(code)
                    print(f"  -> 조건 결과 이탈: {code}, 현재 Set 크기: {len(self.condition_result_codes)}")
                if self.active_real_time_data_screen:
                    current_codes = set(self.kiwoom.real_time_registered_codes.get(self.active_real_time_data_screen, "").split(';'))
                    if code in current_codes:
                        current_codes.remove(code)
                        code_str = ";".join(filter(None, current_codes))
                        fid_str = self.kiwoom.real_time_fid_list
                        print(f"  -> 재등록 요청 (이탈): {code}")
                        self.kiwoom.register_real_time_stock_data(self.active_real_time_data_screen, code_str, fid_str)
            else: print(f"  -> 이탈 종목 {code} 테이블에 없음")

    def _update_real_time_stock_data(self, code, fid_data):
        # D10 : print(f"실시간 데이터 업데이트 수신 (L1856): {code}, fid_data: {fid_data}")

        # tableWidgetConditionResults 업데이트 로직 (이 부분을 수정/강화)
        if hasattr(self, 'tableWidgetConditionResults'):
            target_row = -1
            for row in range(self.tableWidgetConditionResults.rowCount()):
                item = self.tableWidgetConditionResults.item(row, COL_CODE)
                if item and item.text() == code:
                    target_row = row
                    break

            if target_row != -1:
                # print(f"D0 : 조건결과 테이블 업데이트 시작 for {code}, row={target_row}, fid_data={fid_data}") # 디버그 로그

                # 이전에 정의된 update_cell_realtime 과 유사한 함수를 사용하거나 여기서 직접 구현
                # 여기서는 직접 구현하는 방식으로 진행합니다.

                price = fid_data.get(10)      # 현재가 FID 10
                change = fid_data.get(11)     # 전일대비 FID 11
                change_rate = fid_data.get(12)# 등락률 FID 12
                volume = fid_data.get(13)     # 누적거래량 FID 13

                # print(f"D0 : {code} 값 추출: price={price}, change={change}, change_rate={change_rate}, volume={volume}")


                def _set_table_item(row, col, value, is_price_related=False, is_rate=False, is_change=False):
                    item = self.tableWidgetConditionResults.item(row, col)
                    if not item:
                        item = QTableWidgetItem()
                        self.tableWidgetConditionResults.setItem(row, col, item)

                    display_text = ""
                    item_color = Qt.black

                    if value is not None:
                        try:
                            if is_change: # 전일대비
                                val = int(value)
                                display_text = f"{val:+,}"
                                if val > 0: item_color = Qt.red
                                elif val < 0: item_color = Qt.blue
                            elif is_rate: # 등락률
                                val = float(value)
                                display_text = f"{val:+.2f}%"
                                if val > 0: item_color = Qt.red
                                elif val < 0: item_color = Qt.blue
                            else: # 현재가, 거래량 등
                                val = int(value)
                                display_text = f"{val:,}"
                                if is_price_related and change is not None: # 현재가인 경우 전일대비 기준으로 색상 결정
                                    change_val_for_color = int(change)
                                    if change_val_for_color > 0: item_color = Qt.red
                                    elif change_val_for_color < 0: item_color = Qt.blue
                        except ValueError:
                            display_text = str(value) # 숫자 변환 실패 시 문자열 그대로

                    item.setText(display_text)
                    item.setForeground(QBrush(item_color))
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                if price is not None:
                    _set_table_item(target_row, COL_PRICE, price, is_price_related=True)
                if change is not None:
                    _set_table_item(target_row, COL_CHANGE, change, is_change=True)
                if change_rate is not None:
                    _set_table_item(target_row, COL_CHANGE_RATE, change_rate, is_rate=True)
                if volume is not None:
                    _set_table_item(target_row, COL_VOLUME, volume)

                # 실시간 데이터 수신 시 배경색 변경 및 복원 로직 (기존 다른 _update_real_time_stock_data 참고)
                highlight_color = Qt.cyan
                default_bg_color = self.tableWidgetConditionResults.palette().color(QPalette.Base) # 기본 배경색

                cells_to_reset_bg = []
                for col_idx in [COL_PRICE, COL_CHANGE, COL_CHANGE_RATE, COL_VOLUME]: # 업데이트된 컬럼들
                    cell_item = self.tableWidgetConditionResults.item(target_row, col_idx)
                    if cell_item:
                        cell_item.setBackground(highlight_color)
                        cells_to_reset_bg.append(cell_item)
                
                if cells_to_reset_bg:
                    QTimer.singleShot(300, lambda items=cells_to_reset_bg, color=default_bg_color: self._reset_row_background(items, color))


        # 보유종목 테이블 업데이트 로직은 FID 번호로 되어있는지 확인 필요 (현재는 "현재가" 한글키 사용 중)
        # 이 부분도 필요시 수정해야 합니다.
        if hasattr(self, 'tableWidgetHoldings'):
            target_holding_row = -1
            for row in range(self.tableWidgetHoldings.rowCount()):
                code_item = self.tableWidgetHoldings.item(row, 0) # 보유종목테이블의 종목코드 컬럼 인덱스 확인 필요
                if code_item and code_item.text() == code:
                    target_holding_row = row
                    break
            
            if target_holding_row != -1:
                current_price_val = fid_data.get(10) # 현재가 FID
                if current_price_val is not None:
                    # print(f"D0 : 보유종목 {code} 현재가 업데이트: {current_price_val}")
                    price_item = self.tableWidgetHoldings.item(target_holding_row, 4) # 현재가 컬럼 인덱스 4 가정
                    if not price_item:
                        price_item = QTableWidgetItem()
                        self.tableWidgetHoldings.setItem(target_holding_row, 4, price_item)
                    price_item.setText(str(current_price_val))
                    price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    # TODO: 보유종목 테이블의 평가손익, 수익률 등도 실시간 업데이트 필요시 로직 추가


        # 현재 선택된 종목 정보 (nowStock) 업데이트
        if self.nowStock and self.nowStock.code == code:
            current_price_val = fid_data.get(10)
            if current_price_val is not None:
                self.nowStock.current_price = int(current_price_val) # Stocks 객체도 업데이트
                # D10 : print(f"    -> 현재 선택된 종목({self.nowStock.name}) 정보 업데이트: 현재가 {self.nowStock.current_price}")
                if hasattr(self, 'labelNowStockCurrentPrice'): # UI에 해당 라벨이 있다면 업데이트
                    self.labelNowStockCurrentPrice.setText(f"{self.nowStock.current_price:,}원")

        # 최고가 업데이트 로직 (이미 FID 10을 사용하도록 되어 있을 수 있음, 확인)
        # current_price 변수가 이미 한글키로 할당된 상태이므로, fid_data.get(10)을 사용해야 함.
        current_price_for_highest = fid_data.get(10)
        if current_price_for_highest is not None:
            try:
                price_val_int = int(current_price_for_highest)
                # D10 : print(f"  -> 최고가 업데이트 로직 진입 for {code}. 현재 최고가: {self.highest_prices.get(code, 0)}, 새 현재가: {price_val_int}")
                if price_val_int > self.highest_prices.get(code, 0):
                    self.highest_prices[code] = price_val_int
                    # D10 : print(f"    -> 새로운 최고가 기록: {code} - {price_val_int}")
                    # self.highest_price_updated_flag = True # 이 플래그 사용 여부 확인
            except ValueError:
                pass # 숫자 변환 실패 시 최고가 업데이트 건너뜀

    def _handler_chejan_data(self, gubun, data): # data는 kiwoomAPI.py의 parsed_data
        # D10 : print(f"체결/잔고 데이터 수신 (main.py): gubun={gubun}, data={data}")

        order_no = data.get('order_no', '') # 공통
        # kiwoomAPI.py에서 'stock_code' (A 제거된), 'stock_name'으로 전달됨
        stock_code_from_data = data.get('stock_code', '종목코드없음') 
        stock_name_display = data.get('stock_name', '종목명없음')

        # --- 수동 매수 주문 추적 --- (기존 로직 유지, 필요시 data 키 변경)
        # 이 부분은 data에서 사용하는 키가 변경되었다면 함께 수정 필요
        # 예: data.get('order_status_code') -> data.get('order_status_text') 또는 다른 FID 값
        # 예: data.get('executed_qty_total') -> data.get('executed_cumulative_amount') 또는 'executed_qty'의 누적
        if gubun == '0': # 주문접수/체결
            unexecuted_qty_manual = data.get('unexecuted_qty', 0)
            executed_qty_manual = data.get('executed_qty', 0)
            order_status_text_manual = data.get('order_status_text', '') # '접수', '체결' 등

            # D10 : print(f"[수동매수추적] gubun '0' 수신. 주문번호: {order_no}, 상태: {order_status_text_manual}, 미체결량: {unexecuted_qty_manual}, 체결량: {executed_qty_manual}")

            if order_no in self.pending_manual_buy_orders:
                # D10 : print(f"  -> [수동매수추적] 추적중인 주문번호 {order_no} 발견.")
                tracked_info = self.pending_manual_buy_orders[order_no]

                if order_status_text_manual == "체결":
                    tracked_info["filled_qty"] = tracked_info.get("filled_qty", 0) + executed_qty_manual
                    tracked_info["unexecuted_qty"] = unexecuted_qty_manual
                    # D10 : print(f"    -> [수동매수추적] '체결' 상태. 누적체결량: {tracked_info['filled_qty']}, 잔여미체결량: {unexecuted_qty_manual}")

                    if unexecuted_qty_manual == 0:
                        tracked_info["status"] = "fully_filled"
                        # D10 : print(f"      -> [수동매수추적] 완전 체결됨. 주문번호 {order_no} 추적 종료.")
                        # self._log_order_message(f"수동매수: {stock_name_display}({stock_code_from_data}) {tracked_info.get('initial_quantity',0)}주 매수주문 완전체결 완료 (주문번호:{order_no})")
                        # del self.pending_manual_buy_orders[order_no] # 여기서 삭제하지 않고, 잔고처리까지 확인 후 삭제하거나 다른 방식으로 관리
                    else:
                        # 부분 체결 상태 업데이트
                        total_ordered = tracked_info.get('initial_quantity', tracked_info.get('filled_qty',0) + unexecuted_qty_manual)
                        # 아래 라인의 get("filled_qty")를 get('filled_qty')로 수정
                        tracked_info["status"] = f"partially_filled ({tracked_info.get('filled_qty')}/{total_ordered})"
                        # D10 : print(f"    -> [수동매수추적] 부분 체결됨. 상태: {tracked_info['status']}, 미체결: {unexecuted_qty_manual}")
        # --- End 수동 매수 주문 추적 ---

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if gubun == '0': # 주문접수/체결
            order_action_display = data.get('order_action_display', '알수없음') # 매수/매도/정정/취소 등
            order_status_text = data.get('order_status_text', '알수없음')     # 접수/체결 등
            # order_hoga_type_text = data.get('order_hoga_type_text', '')     # 지정가, 시장가 등 (없으면 빈 문자열)
            order_qty = data.get('order_qty', 0)
            order_price = data.get('order_price', 0)
            executed_qty = data.get('executed_qty', 0)
            executed_price = data.get('executed_price', 0)
            unexecuted_qty = data.get('unexecuted_qty', 0)
            # order_time = data.get('order_time', '시간없음') # HHMMSS 형식
            # 체결시간은 executed_time_str 사용 (HHMMSSms)
            executed_time_str = data.get('executed_time_str', '') # 체결시간(HHMMSSms)

            # 호가 유형 처리 (이전에 수정한 내용 반영)
            hoga_type_map = {
                "00": "지정가", "03": "시장가", "05": "조건부지정가",
                "06": "최유리지정가", "07": "최우선지정가",
                # 추가적인 호가 유형이 있다면 여기에 정의
            }
            order_status_raw = data.get('order_status_raw', '') # FID 908 (주문/체결상태 상세 코드)

            # status_message 생성 로직 수정
            status_message = order_action_display
            order_hoga_type_from_api = data.get('order_hoga_type', '')
            # hoga_type_map에 키가 있으면 변환된 값, 없으면 원래 값 (비어있으면 빈 값)
            resolved_hoga_type_text = hoga_type_map.get(order_hoga_type_from_api, order_hoga_type_from_api)

            if resolved_hoga_type_text: # 빈 문자열이 아닐 경우에만 추가
                 status_message += f" ({resolved_hoga_type_text})"

            if order_status_text == "접수" or order_status_text == "확인":
                msg = f"[{now_str}] 주문알림: {stock_name_display}({stock_code_from_data}) {status_message} {order_status_text} (주문량:{order_qty:,}주), 주문번호: {order_no}"
            elif order_status_text == "체결":
                msg = f"[{now_str}] 체결알림: {stock_name_display}({stock_code_from_data}) {status_message} 체결! (체결량:{executed_qty:,}주, 체결가:{executed_price:,}원, 미체결량:{unexecuted_qty:,}주), 주문번호: {order_no}"
                if unexecuted_qty > 0:
                    msg += f" (부분체결)"
                else:
                    msg += f" (완전체결)"
            else: # 기타 상태 (예: "취소", "정정" 등)
                msg = f"[{now_str}] 주문상태: {stock_name_display}({stock_code_from_data}) {status_message} {order_status_text}, 주문번호: {order_no}"
            
            self._log_order_message(msg, log_type="order")

        elif gubun == '1': # 잔고변경
            # D10 : print(f"잔고 데이터 (gubun='1') 수신. 계좌({data.get('account_no', '알수없음')}) 잔고 및 보유종목 재요청.")
            # kiwoomAPI.py에서 'holding_qty', 'purchase_price_avg', 'current_price_balance', 'eval_profit_loss', 'profit_loss_rate' 사용
            holding_qty = data.get('holding_qty', 0)
            avg_price = data.get('purchase_price_avg', 0)
            current_price = data.get('current_price_balance', 0)
            eval_profit_loss = data.get('eval_profit_loss', 0)
            profit_loss_rate = data.get('profit_loss_rate', 0.0)
            
            msg = f"[{now_str}] 잔고변경통보: {stock_name_display}({stock_code_from_data}), 보유량:{holding_qty:,}, 평균단가:{avg_price:,}, 현재가:{current_price:,} (손익:{eval_profit_loss:,}, 수익률:{profit_loss_rate:.2f}%)"
            self._log_order_message(msg, log_type="balance")

            # 잔고 변경 시, 해당 계좌의 잔고 및 보유 종목을 다시 요청
            account_no_from_data = data.get('account_no')
            if account_no_from_data:
                # D10 : print(f"잔고 데이터 (gubun='1') 수신. 계좌({account_no_from_data}) 잔고 및 보유종목 재요청.")
                self.kiwoom.request_account_balance(account_no_from_data)
            else:
                print("경고: account_no가 설정되지 않아 체결 후 잔고 재요청을 할 수 없습니다.")

    # --- UI Interaction Slots ---
    def _on_condition_selected(self, item):
        selected_condition_name = item.text()
        # D10 : print(f"조건식 선택됨: {selected_condition_name}")
        selected_condition_index = -1
        for index, name in self.conditions.items():
            if name == selected_condition_name: selected_condition_index = int(index); break
        if selected_condition_index != -1:
            self._stop_current_real_condition()
            is_real_time_checked = self.checkBoxAutoDelete.isChecked() if hasattr(self, 'checkBoxAutoDelete') else False
            if is_real_time_checked:
                print(f"실시간 조건 검색 요청: 이름={selected_condition_name}, 인덱스={selected_condition_index}") # 실시간 요청은 남김
                screen_no = self.kiwoom.request_condition_search(selected_condition_name, selected_condition_index, is_real_time=True)
                self.active_real_time_condition = {"screen": screen_no, "name": selected_condition_name, "index": selected_condition_index}
            else:
                # D10 : print(f"일반 조건 검색 요청: 이름={selected_condition_name}, 인덱스={selected_condition_index}")
                self.kiwoom.request_condition_search(selected_condition_name, selected_condition_index, is_real_time=False)
        else: print(f"오류: 선택된 조건식 '{selected_condition_name}'의 인덱스를 찾을 수 없습니다.")

    def _on_auto_delete_toggled(self, state):
        print(f"실시간 자동갱신 체크박스 상태 변경: {state == Qt.Checked}")
        current_item = self.listConditions.currentItem() if hasattr(self, 'listConditions') else None
        if state == Qt.Checked:
            if current_item:
                print("체크됨 -> 현재 선택된 조건으로 실시간 감시 시작")
                self._on_condition_selected(current_item)
            else: print("체크됨 -> 선택된 조건 없음")
        else:
            print("체크 해제됨 -> 현재 실시간 감시 중지")
            self._stop_current_real_condition()

    def _stop_current_real_condition(self):
        if self.active_real_time_condition:
            info = self.active_real_time_condition
            print(f"기존 실시간 감시 중지: 화면={info['screen']}, 이름={info['name']}, 인덱스={info['index']}")
            self.kiwoom.stop_real_condition_search(info['screen'], info['name'], info['index'])
            self.active_real_time_condition = None
            if self.active_real_time_data_screen:
                print(f"Unregistering real-time data (screen: {self.active_real_time_data_screen}) as real condition search stopped.")
                self.kiwoom.unregister_real_time_stock_data(self.active_real_time_data_screen)
                self.active_real_time_data_screen = None

    def _on_stock_selected(self, row, column):
        print(f"****** _on_stock_selected ENTRY ****** (row={row}, col={column})") # 함수 진입 확인용 최상단 로그
        sender_table = self.sender()
        code_item = None
        name_item = None
        price_item = None # 현재가 아이템을 저장할 변수
        code = ""
        name = ""
        current_price = 0

        if sender_table == self.tableWidgetHoldings:
            print("****** _on_stock_selected: Source = tableWidgetHoldings ******")
            if self.tableWidgetHoldings.item(row, 0): # COL_CODE
                code_item = self.tableWidgetHoldings.item(row, 0)
            if self.tableWidgetHoldings.item(row, 1): # COL_NAME
                name_item = self.tableWidgetHoldings.item(row, 1)
            if self.tableWidgetHoldings.item(row, 4): # 현재가 컬럼 (인덱스 4)
                price_item = self.tableWidgetHoldings.item(row, 4)

        elif sender_table == self.tableWidgetConditionResults:
            print("****** _on_stock_selected: Source = tableWidgetConditionResults ******")
            if self.tableWidgetConditionResults.item(row, COL_CODE):
                code_item = self.tableWidgetConditionResults.item(row, COL_CODE)
            if self.tableWidgetConditionResults.item(row, COL_NAME):
                name_item = self.tableWidgetConditionResults.item(row, COL_NAME)
            if self.tableWidgetConditionResults.item(row, COL_PRICE): # 현재가 컬럼 (COL_PRICE = 2)
                price_item = self.tableWidgetConditionResults.item(row, COL_PRICE)
        else:
            print(f"****** _on_stock_selected: Unknown sender_table: {sender_table} ******")
            return

        if code_item:
            code = code_item.text().strip()
        if name_item:
            name = name_item.text().strip()
        
        price_text_raw = "ERROR"
        if price_item and price_item.text():
            price_text_raw = price_item.text()
            try:
                # 부호(+, -) 및 기타 문자 제거
                price_text_cleaned = price_text_raw.replace(',', '').replace('원', '').replace('+', '').replace('-', '')
                if price_text_cleaned: # 빈 문자열이 아닌 경우에만 변환 시도
                    current_price = int(price_text_cleaned)
                else:
                    current_price = 0 # 빈 문자열이면 0으로 처리
            except ValueError:
                print(f"****** _on_stock_selected: Error converting price '{price_text_raw}' to int for {code} ******")
                current_price = 0
        else:
            print(f"****** _on_stock_selected: price_item or price_item.text() is None/empty for {code} ******")
            current_price = 0
        
        print(f"****** _on_stock_selected: Parsed values: code='{code}', name='{name}', price_text_raw='{price_text_raw}', current_price_final={current_price} ******")

        if code and name:
            if self.nowStock is None or self.nowStock.code != code:
                self.nowStock = Stocks(code, name, current_price) 
            else: # 이미 self.nowStock 객체가 존재하면 현재가만 업데이트
                self.nowStock.current_price = current_price
            
            print(f"****** _on_stock_selected: self.nowStock updated: {self.nowStock} ******")

            self._update_selected_stock_display(code, name) # 이 함수 내부 로그는 이미 있음
            self.request_order_book_for_current_stock()

            # 매수 UI 업데이트 로직 (QSpinBox 사용 가정 및 로그 추가)
            has_groupbox_buy = hasattr(self, 'groupBoxBuyOrder') # 이름 수정: groupBoxBuy -> groupBoxBuyOrder
            has_spin_price_buy = hasattr(self, 'spinPriceBuy')
            has_spin_quantity_buy = hasattr(self, 'spinQuantityBuy')
            has_combo_hoga_buy = hasattr(self, 'comboHogaTypeBuy')
            
            print(f"****** _on_stock_selected: UI 요소 확인: groupBoxBuyOrder? {has_groupbox_buy}, spinPriceBuy? {has_spin_price_buy}, spinQuantityBuy? {has_spin_quantity_buy}, comboHogaTypeBuy? {has_combo_hoga_buy} ******")

            if has_groupbox_buy and has_spin_price_buy and has_spin_quantity_buy and has_combo_hoga_buy:
                if current_price > 0:
                    calculated_quantity = 0
                    if self.buy_total_amount > 0:
                        calculated_quantity = self.buy_total_amount // current_price
                    calculated_quantity = max(1, calculated_quantity)

                    print(f"****** _on_stock_selected: 매수 UI 업데이트 시도: current_price={current_price}, calculated_quantity={calculated_quantity}, buy_total_amount={self.buy_total_amount} ******")

                    hoga_type_buy = self.comboHogaTypeBuy.currentText()
                    print(f"****** _on_stock_selected: 매수 호가 유형: {hoga_type_buy} ******")

                    if hoga_type_buy != "시장가":
                        self.spinPriceBuy.setValue(current_price)
                        print(f"****** _on_stock_selected: spinPriceBuy SET to {current_price} ******")
                    else:
                        self.spinPriceBuy.setValue(0)
                        print(f"****** _on_stock_selected: spinPriceBuy SET to 0 (시장가) ******") 
                    
                    self.spinQuantityBuy.setValue(calculated_quantity)
                    print(f"****** _on_stock_selected: spinQuantityBuy SET to {calculated_quantity} ******")
                    
                    log_msg = f"{name}({code}) 현재가({current_price:,}) 기준으로 매수 주문정보 임시 업데이트 (수량: {calculated_quantity})."
                    self._log_order_message(log_msg, log_type="system")
                else:
                    print(f"****** _on_stock_selected: 매수 UI 업데이트 건너뜀 - current_price ({current_price})가 0 이하. 기본값 사용. ******")
                    self.spinPriceBuy.setValue(0)
                    self.spinQuantityBuy.setValue(1)
                    log_msg = f"{name}({code})의 현재가를 가져오지 못했거나 0 이하이므로, 매수 주문정보를 기본값으로 설정합니다."
                    self._log_order_message(log_msg, log_type="system")
                print(f"****** _on_stock_selected: 매수 UI 업데이트 로직 실행 완료 후. spinPriceBuy={self.spinPriceBuy.value()}, spinQuantityBuy={self.spinQuantityBuy.value()} ******")
            else:
                print(f"****** _on_stock_selected: 필수 UI 요소 중 하나 이상 없음 (groupBoxBuyOrder, spinPriceBuy, spinQuantityBuy, comboHogaTypeBuy). 매수 UI 업데이트 건너뜀. ******") # 로그 메시지에도 반영
                pass
        else:
            print(f"****** _on_stock_selected: Code ('{code}') 또는 Name ('{name}') 이 비어있어 처리 중단. ******")
            self._clear_selected_stock_display(clicked_widget=sender_table)

    def _on_search_by_name(self):
        if not hasattr(self, 'lineEditNowStockName'): return
        search_text = self.lineEditNowStockName.text().strip()
        print(f"Searching by name (Enter pressed): '{search_text}'")
        self._search_and_set_stock(search_text, search_by='name')

    def _on_search_by_code(self):
        if not hasattr(self, 'lineEditNowStockCode'): return
        search_text = self.lineEditNowStockCode.text().strip()
        print(f"Searching by code (Enter pressed): '{search_text}'")
        self._search_and_set_stock(search_text, search_by='code')

    def _search_and_set_stock(self, search_text, search_by='name'):
        # D10 : print(f"_search_and_set_stock called with: '{search_text}' by '{search_by}'")
        code = ""
        name = ""
        target_stock = None

        if search_by == 'name':
            name = search_text
            code = get_code_by_name(name, self.all_stocks)
        elif search_by == 'code':
            code = search_text
            name = get_name_by_code(code, self.all_stocks)
        
        if code and name:
            # D10 : print(f"  -> Stock found: {name} ({code})")
            # 여기서 Stocks 객체를 생성할 때 현재가를 알 수 없으므로 0 또는 기본값으로 설정
            # 또는, API 요청으로 현재가를 가져온 후 설정할 수 있으나, 지금은 0으로 설정
            self.nowStock = Stocks(code, name, 0) # current_price=0으로 초기화
            # D10 : print(f"  -> self.nowStock updated: {self.nowStock}")
            self._update_selected_stock_display(code, name)
            self.request_order_book_for_current_stock()
            return True
        else:
            # D0 : print(f"  -> Stock not found: '{search_text}'")
            self._clear_selected_stock_display(clicked_text=search_text) # 검색 실패 시 UI 초기화
            # QMessageBox.warning(self, "종목 검색 실패", f"'{search_text}'에 해당하는 종목을 찾을 수 없습니다.")
            self._log_order_message(f"'{search_text}'에 해당하는 종목을 찾을 수 없습니다.", log_type="system")
            return False

    def _update_selected_stock_display(self, code, name):
        """검색 등을 통해 선택된 종목 정보를 lineEditNowStockCode/Name에 표시합니다."""
        print(f"[UI UPDATE] _update_selected_stock_display called with Code: {code}, Name: {name}") # 함수 호출 로그
        if hasattr(self, 'lineEditNowStockCode'):
            self.lineEditNowStockCode.setText(code)
            print(f"  -> Set lineEditNowStockCode = {code}") # 설정 로그
        else:
            print("  -> lineEditNowStockCode not found!") # 실패 로그
        if hasattr(self, 'lineEditNowStockName'):
            self.lineEditNowStockName.setText(name)
            print(f"  -> Set lineEditNowStockName = {name}") # 설정 로그
        else:
            print("  -> lineEditOrderName not found!") # 실패 로그 (이전 복붙 오류 수정: Name)
        print("[UI UPDATE] _update_selected_stock_display finished.") # 함수 종료 로그

    def _clear_selected_stock_display(self, clicked_widget=None, clicked_text=""):
        """검색 필드 등에서 선택이 해제되었을 때 lineEditNowStockCode/Name을 초기화합니다."""
        print("[UI UPDATE] _clear_selected_stock_display called.") # 함수 호출 로그
        if hasattr(self, 'lineEditNowStockCode'):
            if clicked_widget is not getattr(self, 'lineEditNowStockCode', None):
                self.lineEditNowStockCode.clear()
                print("  -> Cleared lineEditNowStockCode")
            else:
                self.lineEditNowStockCode.setText(clicked_text) # 클릭된 위젯이면 텍스트 유지
        if hasattr(self, 'lineEditNowStockName'):
            if clicked_widget is not getattr(self, 'lineEditNowStockName', None):
                self.lineEditNowStockName.clear()
                print("  -> Cleared lineEditNowStockName")
            else:
                self.lineEditNowStockName.setText(clicked_text) # 클릭된 위젯이면 텍스트 유지
        print("[UI UPDATE] _clear_selected_stock_display finished.")

    # --- Order Execution Slots/Methods ---
    def _on_hoga_type_changed(self, index):
        sender_combo = self.sender() # 시그널을 보낸 콤보박스 확인
        if not sender_combo: return

        hoga_type = sender_combo.currentText()
        is_market_price = (hoga_type == "시장가")

        target_spinbox = None
        if sender_combo is getattr(self, 'comboHogaType', None): # 매수 박스 콤보박스인가?
            target_spinbox = getattr(self, 'spinPrice', None)
            print(f"매수 호가 유형 변경 감지: {hoga_type}")
        elif sender_combo is getattr(self, 'comboHogaTypeSell', None): # 매도 박스 콤보박스인가?
            target_spinbox = getattr(self, 'spinPriceSell', None)
            print(f"매도 호가 유형 변경 감지: {hoga_type}")
        else:
             print(f"경고: 알 수 없는 호가 콤보박스({sender_combo.objectName()})에서 시그널 발생")
             return


        if target_spinbox:
            print(f"  -> 대상 스핀박스: {target_spinbox.objectName()}")
            target_spinbox.setValue(0 if is_market_price else target_spinbox.value())
            target_spinbox.setEnabled(not is_market_price)
            print(f"  -> 시장가: {is_market_price}, 스핀박스 활성화: {not is_market_price}, 값: {target_spinbox.value()}")
        else:
            print(f"경고: {sender_combo.objectName()}에 연결된 가격 스핀박스를 찾을 수 없습니다.")


    def _execute_order(self):
        sender_button = self.sender()
        if not sender_button:
            # print("주문 오류: sender 버튼을 찾을 수 없음")
            return

        is_sell_order = (sender_button is getattr(self, 'btnSendOrderSell', None))
        order_action = "매도" if is_sell_order else "매수"
        # print(f"--- {order_action} 주문 실행 시작 (버튼: {sender_button.objectName()}) ---")

        # 위젯 이름 접미사 결정
        suffix = "Sell" if is_sell_order else "Buy"
        order_type_combo_name = f"comboOrderType{suffix}"

        account_combo_name = f'comboAccountSell' if is_sell_order else 'comboAccountBuy'
        if not hasattr(self, account_combo_name):
            QMessageBox.warning(self, "주문 오류", f"UI 요소 '{account_combo_name}'을(를) 찾을 수 없습니다.")
            return

        code_edit_name = f"lineEditOrderCode{suffix}"
        name_edit_name = f"lineEditOrderName{suffix}"
        hoga_combo_name = f"comboHogaType{suffix}"
        price_spin_name = f"spinPrice{suffix}"
        quantity_spin_name = f"spinQuantity{suffix}"

        widget_values = {}
        required_widget_names = [account_combo_name, order_type_combo_name, code_edit_name, name_edit_name, hoga_combo_name, price_spin_name, quantity_spin_name]
        for widget_name in required_widget_names:
            if not hasattr(self, widget_name):
                QMessageBox.warning(self, "주문 오류", f"UI 요소 '{widget_name}'을(를) 찾을 수 없습니다.")
                return
            widget = getattr(self, widget_name)
            if isinstance(widget, (QLineEdit,)):
                widget_values[widget_name] = widget.text().strip()
            elif isinstance(widget, (QComboBox,)):
                widget_values[widget_name] = widget.currentText()
            elif isinstance(widget, (QSpinBox,)):
                widget_values[widget_name] = widget.value()
            else:
                # print(f"경고: 알 수 없는 위젯 타입({type(widget)}) - {widget_name}")
                widget_values[widget_name] = None

        account_no = widget_values[account_combo_name]
        order_type_str = widget_values[order_type_combo_name]
        code = widget_values[code_edit_name]
        stock_name = widget_values[name_edit_name]
        hoga_type_str = widget_values[hoga_combo_name]
        price = widget_values[price_spin_name]
        quantity = widget_values[quantity_spin_name]

        # print(f"  계좌: {account_no}, 유형: {order_type_str}, 종목: {stock_name}({code}), 구분: {hoga_type_str}, 가격: {price}, 수량: {quantity}")

        # 유효성 검사
        if not account_no:
            QMessageBox.warning(self, "주문 오류", "계좌번호가 선택되지 않았습니다.")
            return
        if not code or len(code) != 6 or not code.isdigit():
            QMessageBox.warning(self, "주문 오류", "유효한 종목코드가 입력되지 않았습니다.")
            return
        if quantity <= 0:
            QMessageBox.warning(self, "주문 오류", "주문 수량은 0보다 커야 합니다.")
            return
        if hoga_type_str == "지정가" and price <= 0:
            QMessageBox.warning(self, "주문 오류", "지정가 주문의 경우 가격이 0보다 커야 합니다.")
            return
        if order_type_str not in ["매수", "매도"]:
            QMessageBox.warning(self, "주문 오류", "유효하지 않은 주문 유형입니다.")
            return

        rqname = f"{order_type_str}_{code}"
        screen_no = self.kiwoom._get_unique_screen_no()
        order_type_map = {"매수": 1, "매도": 2}
        order_type = order_type_map.get(order_type_str)
        if (order_type == 1 and is_sell_order) or (order_type == 2 and not is_sell_order):
            QMessageBox.warning(self, "주문 오류", "주문 유형과 버튼이 일치하지 않습니다.")
            return

        hoga_gb_map = {"지정가": "00", "시장가": "03"}
        hoga_gb = hoga_gb_map.get(hoga_type_str)
        if hoga_gb is None:
            QMessageBox.warning(self, "주문 오류", "유효하지 않은 호가 유형입니다.")
            return
        if hoga_type_str == "시장가":
            price = 0
        # print(f"  최종 주문 정보 -> RQName: {rqname}, Screen: {screen_no}, Acc: {account_no}, Type: {order_type}, Code: {code}, Qty: {quantity}, Price: {price}, Hoga: {hoga_gb}")

        ret = self.kiwoom.send_order(rqname, screen_no, account_no, order_type, code, quantity, price, hoga_gb)
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        price_str = '시장가' if hoga_type_str == '시장가' else f'{price:,}원'
        log_msg = f"[{now_str}] {order_type_str} 주문: {stock_name}({code}) {price_str} {quantity:,}주\n"
        if ret == 0:
            log_msg += "  -> 주문 요청 성공\n"
            self.statusBar().showMessage(f"주문 요청 성공: {rqname}", 5000)
        else:
            error_msg = self.kiwoom.get_error_message(ret)
            log_msg += f"  -> 주문 요청 실패 (코드: {ret}) {error_msg}\n"
            self.statusBar().showMessage(f"주문 요청 실패: {error_msg}", 5000)
            QMessageBox.critical(self, "주문 실패", f"주문 요청 실패 (코드: {ret}) {error_msg}")
        if hasattr(self, 'plainTextEditOrderLog'):
            self.plainTextEditOrderLog.appendPlainText(log_msg)
        # print(f"--- {order_action} 주문 실행 종료 ---")

    # --- Helper Methods (Completer, Font/Background Reset, etc.) ---
    def eventFilter(self, source, event):
        if source in [getattr(self, 'lineEditNowStockName', None), getattr(self, 'lineEditNowStockCode', None)] and event.type() == QEvent.MouseButtonPress:
            if source:
                # D10 : print(f"Event Filter: MouseButtonPress detected on {source.objectName()}.")
                QTimer.singleShot(0, source.selectAll)
        return super().eventFilter(source, event)

    def _setup_completers(self):
        # D10 : print("_setup_completers called.")
        if not self.all_stocks:
            # D10 : print("자동 완성을 위한 종목 리스트(all_stocks)가 아직 준비되지 않았습니다.")
            return
        stock_names = [stock.name for stock in self.all_stocks if stock.name]
        name_model = QStringListModel(stock_names); self.stock_completer.setModel(name_model)
        # D10 : print(f"  -> 이름 자동 완성 모델 설정 완료 ({len(stock_names)}개).")
        stock_codes = [stock.code for stock in self.all_stocks if stock.code]
        code_model = QStringListModel(stock_codes); self.code_completer.setModel(code_model)
        # D10 : print(f"  -> 코드 자동 완성 모델 설정 완료 ({len(stock_codes)}개).")

    def _on_name_completer_activated(self, text):
        print(f"이름 자동 완성 선택됨 (activated signal - Enter/DoubleClick): {text}")
        self._search_and_set_stock(text, search_by='name')

    def _on_code_completer_activated(self, text):
        print(f"코드 자동 완성 선택됨 (activated signal - Enter/DoubleClick): {text}")
        self._search_and_set_stock(text, search_by='code')

    def _on_name_completer_popup_clicked(self, index):
        model = self.stock_completer.model()
        if model:
            selected_name = model.data(index); print(f"이름 자동 완성 팝업 클릭됨: {selected_name}")
            self._search_and_set_stock(selected_name, search_by='name')
            self.stock_completer.popup().hide()

    def _on_code_completer_popup_clicked(self, index):
        model = self.code_completer.model()
        if model:
            selected_code = model.data(index); print(f"코드 자동 완성 팝업 클릭됨: {selected_code}")
            self._search_and_set_stock(selected_code, search_by='code')
            self.code_completer.popup().hide()

    def _reset_row_background(self, items, color):
        for item in items:
            try: item.setBackground(color)
            except RuntimeError: pass

    def _reset_item_font_and_clear_timer(self, item, original_font, cell_key):
        try: item.setFont(original_font)
        except RuntimeError: pass
        finally:
            if cell_key in self.cell_font_timers:
                del self.cell_font_timers[cell_key]

    def _clear_all_font_timers(self):
        for timer in list(self.cell_font_timers.values()): timer.stop()
        self.cell_font_timers.clear()

    def _clear_timers_for_row(self, row_index):
        keys_to_remove = [key for key in self.cell_font_timers if key[0] == row_index]
        for key in keys_to_remove:
            if key in self.cell_font_timers:
                timer = self.cell_font_timers.pop(key); timer.stop()

    # --- Auto Trading Condition Check (Placeholders) ---
    def _check_buy_condition(self, code, fid_data):
        print(f"[매수 점검] 종목: {code}, 데이터: {fid_data.get(10, 'N/A')} (현재가 FID 10)")
        # TODO: Implement buy logic and call _execute_order if condition met

    def _check_sell_condition(self, code, fid_data):
        print(f"[매도 점검] 종목: {code}, 데이터: {fid_data.get(10, 'N/A')} (현재가 FID 10)")
        # TODO: Implement sell logic and call _execute_order if condition met

    # --- Order Book Methods ---
    def init_order_book_tables(self):
        if hasattr(self, 'tableWidgetAsk') and hasattr(self, 'tableWidgetBid'):
            self.setup_table_widget(self.tableWidgetAsk, ['잔량', '호가'])
            self.setup_table_widget(self.tableWidgetBid, ['호가', '잔량'])
            self.tableWidgetAsk.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
            self.tableWidgetAsk.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
            self.tableWidgetBid.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            self.tableWidgetBid.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            for i in range(10):
                self.tableWidgetAsk.insertRow(i); self.tableWidgetBid.insertRow(i)
                for j in range(2):
                    ask_item = QTableWidgetItem(""); ask_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter); ask_item.setBackground(QColor(230, 240, 255)); self.tableWidgetAsk.setItem(i, j, ask_item)
                    bid_item = QTableWidgetItem(""); bid_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter); bid_item.setBackground(QColor(255, 235, 235)); self.tableWidgetBid.setItem(i, j, bid_item)
        else: print("오류: 호가 테이블 위젯(Ask 또는 Bid)이 없습니다.")

    def setup_table_widget(self, table_widget: QTableWidget, headers: list):
        table_widget.setColumnCount(len(headers)); table_widget.setHorizontalHeaderLabels(headers)
        table_widget.verticalHeader().setVisible(False); table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_widget.setSelectionMode(QAbstractItemView.NoSelection); table_widget.setFocusPolicy(Qt.NoFocus)
        table_widget.setRowCount(0) # 초기 행은 init_order_book_tables 등에서 추가

    def request_order_book_for_current_stock(self):
        # D10 : print("request_order_book_for_current_stock called")
        if self.nowStock and self.nowStock.code:
            new_code = self.nowStock.code
            # D10 : print(f"  -> Requesting for: {new_code} ({self.nowStock.name})")
            screen_no_order_book = "9001" # 호가 전용 화면 번호 사용
            if self.current_order_book_code and self.current_order_book_code != new_code:
                # 화면 번호에 등록된 모든 종목 해제 (이전 종목 해제)
                self.kiwoom.unregister_real_time_stock_data(screen_no_order_book)
                # D10 : print(f"  -> 실시간 호가 해지 요청 (이전): {self.current_order_book_code} (화면: {screen_no_order_book})")

            if self.current_order_book_code != new_code:
                self.clear_order_book_tables(); self.current_order_book_code = new_code

                # --- FID 리스트 수정 ---
                # 매도호가(41-50), 매수호가(51-60), 매도호가잔량(61-70), 매수호가잔량(71-80) 모두 등록
                fid_list = ";".join(map(str, list(range(41, 81)))) # 41부터 80까지의 FID 문자열 생성
                # D10 : print(f"  -> Registering with FIDs: {fid_list}") # 등록할 FID 목록 로그 추가

                # SetRealReg 호출 (code: 단일 종목, fid_list: 전체 호가 FID)
                result = self.kiwoom.register_real_time_stock_data(screen_no_order_book, new_code, fid_list)
                if result == 0: # D10 : print(f"  -> 실시간 호가 등록 요청 성공: {self.current_order_book_code} (화면: {screen_no_order_book})")
                    pass
                else: # D10 : print(f"  -> 실시간 호가 등록 요청 실패: {self.current_order_book_code} (화면: {screen_no_order_book}, 결과코드: {result})"); 
                    self.current_order_book_code = None
                    pass
        else: print("  -> No stock selected, stopping order book."); self.stop_order_book_real_time()

    def stop_order_book_real_time(self):
        # D10 : print("stop_order_book_real_time called")
        screen_no_order_book = "9001"
        if self.current_order_book_code:
            self.kiwoom.unregister_real_time_stock_data(screen_no_order_book)
            print(f"  -> 실시간 호가 해지 요청: {self.current_order_book_code} (화면: {screen_no_order_book})")
            self.current_order_book_code = None; self.clear_order_book_tables()
        else: print("  -> No active order book to stop.")

    def clear_order_book_tables(self):
        # D10 : print("Clearing order book tables...")
        for table_widget in [getattr(self, 'tableWidgetAsk', None), getattr(self, 'tableWidgetBid', None)]:
            if table_widget:
                for i in range(table_widget.rowCount()):
                    for j in range(table_widget.columnCount()):
                        item = table_widget.item(i, j)
                        if item: item.setText("")
                        else: table_widget.setItem(i, j, QTableWidgetItem(""))

    def update_order_book(self, code, fid_data):
        # D10 : print(f"[UI UPDATE] update_order_book called for Code: {code}") # 메서드 호출 확인 로그
        if code != self.current_order_book_code:
            # D10 : print(f"  -> Skipping update. Current book: {self.current_order_book_code}, Received: {code}") # 업데이트 스킵 로그
            return

        self.current_order_book_fid_data = fid_data # 수신된 호가 데이터를 멤버 변수에 저장
        # D10 : print(f"  -> Saved current order book data for {code}.") # 저장 확인 로그 추가

        if not hasattr(self, 'tableWidgetAsk') or not hasattr(self, 'tableWidgetBid'):
            print("오류: 호가 테이블 위젯(tableWidgetAsk or tableWidgetBid)이 없습니다."); return

        # D10 : print(f"  -> Updating Ask/Bid tables for {code}...") # 테이블 업데이트 시작 로그
        ask_prices_fids = [str(fid) for fid in range(41, 51)]; ask_volumes_fids = [str(fid) for fid in range(61, 71)]
        bid_prices_fids = [str(fid) for fid in range(51, 61)]; bid_volumes_fids = [str(fid) for fid in range(71, 81)]

        def _update_cell(table, row, col, value):
            item = table.item(row, col)
            if not item:
                item = QTableWidgetItem(); table.setItem(row, col, item)
                bg_color = QColor(230, 240, 255) if table is self.tableWidgetAsk else QColor(255, 235, 235)
                item.setBackground(bg_color); item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            display_text = ""; final_color = Qt.black
            if value is not None and value != "":
                try:
                    is_price = (table is self.tableWidgetAsk and col == 1) or (table is self.tableWidgetBid and col == 0)
                    if is_price:
                        numeric_part = value.replace('+', '') # + 부호 제거
                        price_val = int(numeric_part)
                        display_text = f"{price_val:,}"
                        if price_val > 0:
                            final_color = Qt.red
                        elif price_val < 0:
                            final_color = Qt.blue
                        else:
                            final_color = Qt.black
                    else: display_text = f"{int(value):,}" # 잔량
                except (ValueError, TypeError) as e:
                    display_text = str(value)
                    # print(f"    Error formatting cell value '{value}' (Table: {table.objectName()}, R:{row}, C:{col}): {e}") # 포맷팅 오류 로그
            item.setText(display_text); item.setForeground(final_color)
            # 로그 추가 (어떤 셀이 어떤 값으로 업데이트되는지 확인)
            # print(f"    -> Set Cell({table.objectName()}, R:{row}, C:{col}) = {display_text}")
            pass # 너무 많은 로그가 나올 수 있으므로 일단 주석처리

        try: # 테이블 업데이트 중 발생할 수 있는 오류 방지
            # 매도 호가 업데이트
            for i in range(10):
                row_index = 9 - i;
                ask_volume = fid_data.get(ask_volumes_fids[i])
                ask_price = fid_data.get(ask_prices_fids[i])
                _update_cell(self.tableWidgetAsk, row_index, 0, ask_volume)
                _update_cell(self.tableWidgetAsk, row_index, 1, ask_price)

            # 매수 호가 업데이트
            for i in range(10):
                row_index = i;
                bid_price = fid_data.get(bid_prices_fids[i])
                bid_volume = fid_data.get(bid_volumes_fids[i])
                _update_cell(self.tableWidgetBid, row_index, 0, bid_price)
                _update_cell(self.tableWidgetBid, row_index, 1, bid_volume)

            # D10 : print(f"  -> Ask/Bid tables update complete for {code}.") # 테이블 업데이트 완료 로그

        except Exception as e:
            print(f"  -> [UI UPDATE 중 오류 발생] Code: {code}, Error: {e}")

    # --- Async Request Handling ---
    def _process_next_request(self):
        if self.pending_requests:
            code = self.pending_requests.pop(0)
            # print(f"Processing request for: {code} (remaining: {len(self.pending_requests)})") # 주석 처리
            self.kiwoom.request_stock_basic_info(code)
        else:
            # print("All pending requests processed. Stopping timer.") # 주석 처리 (필요시 해제)
            self.request_timer.stop()
            if hasattr(self, 'tableWidgetConditionResults'): self.tableWidgetConditionResults.resizeColumnsToContents()

    # --- Window Close Event ---
    def closeEvent(self, event):
        print("프로그램 종료 처리 시작...")
        self._stop_current_real_condition()
        if self.active_real_time_data_screen:
            print(f"종료 전 실시간 시세 해제 (화면: {self.active_real_time_data_screen})")
            self.kiwoom.unregister_real_time_stock_data(self.active_real_time_data_screen)
            self.active_real_time_data_screen = None
        self.stop_order_book_real_time()
        if self.request_timer.isActive(): self.request_timer.stop(); print("요청 타이머 중지됨.")
        self._clear_all_font_timers()
        if self.save_timer.isActive():
            self.save_timer.stop()
            print("최고가 저장 타이머 중지됨.")
        self._save_highest_prices() # 종료 전 최종 저장
        print("프로그램 종료.")
        super().closeEvent(event)

    def _prepare_order_from_order_book(self):
        # D10 : print("호가창 종목 정보 확인: ...") # 이 로그는 버튼 클릭 시점에 따라 다름
        sending_button = self.sender()
        is_buy_order = False
        target_group_box_name = ""
        order_code_edit = None
        order_name_edit = None
        order_quantity_spin = None
        order_hoga_type_combo = None
        order_price_spin = None
        current_price_label = None # 매수/매도에 따라 다른 가격 라벨 참조

        if sending_button == self.btToBuyOrder:
            # D10 : print(" -> 매수 주문 준비 요청")
            is_buy_order = True
            target_group_box_name = "groupBoxBuy"
            order_code_edit = self.lineEditOrderCodeBuy
            order_name_edit = self.lineEditOrderNameBuy
            order_quantity_spin = self.spinQuantityBuy
            order_hoga_type_combo = self.comboHogaTypeBuy
            order_price_spin = self.spinPriceBuy
            if hasattr(self, 'labelOrderBookAskPrice1'): # 매수 시 매도 1호가 참고
                current_price_label = self.labelOrderBookAskPrice1
        elif sending_button == self.btToSellOrder:
            # D10 : print(" -> 매도 주문 준비 요청")
            target_group_box_name = "groupBoxSell"
            order_code_edit = self.lineEditOrderCodeSell
            order_name_edit = self.lineEditOrderNameSell
            order_quantity_spin = self.spinQuantitySell
            order_hoga_type_combo = self.comboHogaTypeSell
            order_price_spin = self.spinPriceSell
            if hasattr(self, 'labelOrderBookBidPrice1'): # 매도 시 매수 1호가 참고
                current_price_label = self.labelOrderBookBidPrice1
        else:
            # D10 : print("알 수 없는 버튼으로부터의 요청")
            return

        if not self.current_order_book_code or not self.nowStock:
            # D10 : print("  -> 현재 선택된 호가 종목이 없습니다.")
            QMessageBox.warning(self, "주문 준비 오류", "먼저 호가를 조회할 종목을 선택해주세요.")
            return

        order_code_edit.setText(self.current_order_book_code)
        order_name_edit.setText(self.nowStock.name)

        # 현재가 설정 (매수 시 매도호가, 매도 시 매수호가)
        current_market_price_str = "0"
        if current_price_label and current_price_label.text():
            try:
                current_market_price_str = current_price_label.text().replace(",", "")
                current_market_price = int(current_market_price_str)
                order_price_spin.setValue(current_market_price)
                # D10 : print(f"  -> 현재 {('매도 1호가' if is_buy_order else '매수 1호가')}: {current_market_price}")
            except ValueError:
                # D10 : print(f"  -> 경고: 호가창의 가격('{current_price_label.text()}')을 숫자로 변환할 수 없습니다.")
                order_price_spin.setValue(0)
        else:
            # D10 : print("  -> 경고: 호가창에서 현재가를 가져올 수 없습니다.")
            order_price_spin.setValue(0)
        
        # 주문 가능 금액 확인 (매수 시에만)
        available_cash = 0
        if is_buy_order and hasattr(self, 'labelBuyableCashAmount') and self.labelBuyableCashAmount.text():
            cash_text = self.labelBuyableCashAmount.text().replace("원", "").replace(",", "").strip()
            try:
                available_cash = int(cash_text)
                # D10 : print(f"  -> 현재 주문 가능 금액: {available_cash:,}")
            except ValueError:
                # D10 : print(f"  -> 경고: 주문 가능 금액('{self.labelBuyableCashAmount.text()}')을 숫자로 변환할 수 없습니다.")
                pass

        # 수량 계산 (매수 시에만, 최대 10만원 또는 주문가능금액 내에서)
        if is_buy_order:
            calculated_quantity = 0
            price_for_qty_calc = order_price_spin.value() # 여기서 order_price_spin은 self.spinPriceBuy 입니다.

            # 시장가 주문 (가격이 0)이거나, 지정가이지만 가격 설정이 아직 안된 경우 (nowStock.current_price 사용)
            price_for_qty_calc_alternative = 0 # 초기화
            if price_for_qty_calc == 0: # 시장가 주문 또는 아직 가격 미설정
                if self.nowStock and self.nowStock.current_price > 0:
                    # D10 : print(f"  -> 매수 수량 계산: 시장가 또는 가격 미정(0). self.nowStock.current_price ({self.nowStock.current_price}) 사용")
                    price_for_qty_calc_alternative = self.nowStock.current_price
                else:
                    # D10 : print(f"  -> 매수 수량 계산: 시장가 주문이지만 self.nowStock.current_price 사용 불가. 수량 0으로 설정됨.")
                    pass # price_for_qty_calc_alternative 는 0 유지
            elif price_for_qty_calc > 0: # 지정가 주문이고 가격이 설정된 경우
                # D10 : print(f"  -> 매수 수량 계산: 지정가. order_price_spin.value() ({price_for_qty_calc}) 사용")
                price_for_qty_calc_alternative = price_for_qty_calc
            # price_for_qty_calc < 0 인 경우는 없다고 가정 (QSpinBox의 최소값은 0)

            if price_for_qty_calc_alternative > 0:
                # self.buy_total_amount 사용 (이전 _on_stock_selected 와 유사한 로직)
                # 주문 가능 금액을 self.buy_total_amount 와 실제 API가 알려준 주문가능 현금 중 작은 값으로 제한
                buyable_amount_limit = self.buy_total_amount
                if available_cash > 0: # available_cash는 위에서 계산된 값
                    buyable_amount_limit = min(self.buy_total_amount, available_cash)
                else: # API로부터 주문가능금액을 받지 못한 경우, self.buy_total_amount 만 사용
                    # D10: print(f"  -> 주문가능금액(available_cash) 정보 없음. self.buy_total_amount ({self.buy_total_amount}) 기준으로 계산")
                    pass

                if buyable_amount_limit >= price_for_qty_calc_alternative: # 최소 1주는 살 수 있어야 함
                    calculated_quantity = buyable_amount_limit // price_for_qty_calc_alternative
                else:
                    calculated_quantity = 0 # 살 돈이 없거나, 1주 가격보다 적으면 0주
                # D10 : print(f"  -> 수량계산용 가격: {price_for_qty_calc_alternative}, 최대주문금액한도: {buyable_amount_limit}, 계산된수량: {calculated_quantity}")
            else: # price_for_qty_calc_alternative 가 0 이하인 경우 (예: 시장가인데 현재가 정보도 없는 극단적 상황)
                # D10 : print(f"  -> 매수 수량 계산: 유효한 가격 정보 없음 (price_for_qty_calc_alternative={price_for_qty_calc_alternative}). 수량 0으로 설정.")
                calculated_quantity = 0
            
            order_quantity_spin.setValue(calculated_quantity)
            # D10 : print(f"  -> 계산된 주문 수량 (최대 {self.buy_total_amount/10000 if hasattr(self, 'buy_total_amount') else '알수없음'}만원, 주문가능금액 {available_cash:,}원 내): {calculated_quantity}")

        # 기본값 설정
        # D10 : print(f"   -> Set lineEditOrderCodeBuy = {order_code_edit.text()}")
        # D10 : print(f"   -> Set lineEditOrderNameBuy = {order_name_edit.text()}")
        # D10 : print(f"   -> Set spinQuantityBuy = {order_quantity_spin.value()}")
        # D10 : print(f"   -> Set comboHogaTypeBuy = {order_hoga_type_combo.currentText()}")
        # D10 : print(f"   -> Set spinPriceBuy = {order_price_spin.value()}")

        # 매도 시에는 현재 보유 수량을 자동으로 입력 (선택적 기능)
        if not is_buy_order and self.current_order_book_code in self.holding_codes:
            for holding in self.holdings_data:
                if holding.get("종목코드") == self.current_order_book_code:
                    order_quantity_spin.setValue(holding.get("보유수량", 0))
                    # D10 : print(f"  -> 매도 주문 준비: 보유수량 {holding.get('보유수량',0)}주 자동 입력")
                    break

        # 해당 주문 그룹박스로 포커스 이동 또는 탭 활성화 (UI 구조에 따라 다름)
        # 예: self.tabWidgetOrder.setCurrentWidget(self.findChild(QWidget, target_group_box_name).parentWidget()) 
        # 만약 QGroupBox가 QTabWidget의 페이지라면 위와 같이 처리
        # 여기서는 간단히 메시지 박스로 알림
        # QMessageBox.information(self, "주문 준비 완료", f"{('매수' if is_buy_order else '매도')} 주문 정보가 입력되었습니다.")

    # --- 주문가능금액 라벨 업데이트 슬롯 추가 ---
    def _update_buyable_cash_label(self, cash_amount):
        """수신된 주문가능금액으로 lblBuyableMoney 라벨을 업데이트합니다."""
        if hasattr(self, 'lblBuyableMoney'):
            try:
                # 숫자를 콤마 포맷 및 " 원" 문자열 추가하여 표시
                formatted_cash = f"{int(cash_amount):,} 원"
                self.lblBuyableMoney.setText(formatted_cash)
                # D10 : print(f"[UI UPDATE] lblBuyableMoney 업데이트: {formatted_cash}")
            except ValueError:
                print(f"오류: 수신된 주문가능금액({cash_amount})을 숫자로 변환할 수 없습니다.")
                self.lblBuyableMoney.setText("오류")
            except Exception as e:
                print(f"lblBuyableMoney 업데이트 중 오류 발생: {e}")
                self.lblBuyableMoney.setText("오류")
        else:
            print("경고: UI에 lblBuyableMoney 위젯이 없습니다.")

    def _execute_auto_sell(self, code):
        """주어진 종목코드에 대해 자동 매도 주문(시장가, 전량)을 실행합니다."""
        print(f"--- 자동 매도 실행 시도: {code} ---")

        # 보유 수량 확인
        holding_qty = 0
        holding_info = next((item for item in self.holdings_data if item.get("종목코드") == code), None)
        if holding_info:
            holding_qty = holding_info.get("보유수량", 0)
        else:
            print(f"  -> 자동 매도 실패: {code} 보유 정보를 찾을 수 없음")
            return

        if holding_qty <= 0:
            print(f"  -> 자동 매도 실패: {code} 보유 수량({holding_qty}) 없음")
            return

        # 계좌번호 확인
        account_no = None
        if hasattr(self, 'comboAccount'):
            account_no = self.comboAccount.currentText()
        if not account_no:
             # QMessageBox.warning(self, "자동 매도 오류", "계좌번호가 선택되지 않았습니다.") # 자동 실행이므로 메시지박스 부적합
             print(f"  -> 자동 매도 실패: 계좌번호를 찾을 수 없음 (comboAccount 확인 필요)")
             return

        # 시장가 매도 주문 파라미터 설정
        rqname = f"자동매도_{code}_{self.kiwoom._get_unique_screen_no()}"
        screen_no = self.kiwoom._get_unique_screen_no()
        order_type = 2 # 신규매도
        price = 0 # 시장가
        hoga_gb = "03" # 시장가

        print(f"  자동 매도 주문 정보 -> RQName: {rqname}, Screen: {screen_no}, Acc: {account_no}, Code: {code}, Qty: {holding_qty}, Hoga: 시장가")

        # KiwoomAPI 주문 함수 호출
        ret = self.kiwoom.send_order(rqname, screen_no, account_no, order_type, code, holding_qty, price, hoga_gb)
        if ret == 0:
            print(f"  -> 자동 매도 주문 요청 성공 (결과 코드: {ret})")
            # TODO: 매도 재주문 로직 연동 필요 (여기서 추적 시작?)
        else:
            error_msg = self.kiwoom.get_error_message(ret) if hasattr(self.kiwoom, 'get_error_message') else f"에러코드 {ret}"
            print(f"  -> 자동 매도 주문 요청 실패 (결과 코드: {ret}), 메시지: {error_msg}")
        print(f"--- 자동 매도 실행 완료: {code} ---")
        pass # 들여쓰기 오류 해결을 위해 pass 추가

    # --- 자동 매수 락 해제 슬롯 --- #
    def _clear_buy_locks(self):
        """타임아웃 시 모든 자동 매수 락을 해제합니다."""
        # 실제로는 락을 건 종목만 해제하는 것이 더 정교하나, 우선 간단히 구현
        codes_to_unlock = list(self.buy_check_locks.keys())
        if codes_to_unlock:
             print(f"[AUTO-BUY] Clearing buy locks for: {codes_to_unlock}")
             self.buy_check_locks.clear()
        # self.auto_buy_lock_timer.stop() # 매번 해제 후 멈출 필요는 없음

    # --- Auto Trading Condition Check --- #
    def _check_buy_condition(self, code, current_tick_data):
        """슈팅(매수) 조건을 검사합니다."""
        # print(f"[AUTO-BUY] Checking buy condition for {code}") # 필요시 로그 활성화
        ticks = self.recent_ticks.get(code)
        if not ticks or len(ticks) < 2:
            return # 비교할 데이터 부족

        # 최신 틱과 그 이전 틱 데이터 추출
        now, current_price, current_volume, current_ask_vol, current_bid_vol = current_tick_data
        prev_time, previous_price, previous_volume, _, _ = ticks[-2] # 이전 틱 정보

        # 1. 가격 급등 확인 (1% 이상 상승)
        price_condition = current_price > (previous_price * 1.01)
        if price_condition: print(f"  [Buy Check {code}] Price condition met: {previous_price} -> {current_price}")

        # 2. 거래량 급증 확인 (최근 5틱 평균 대비 200% 증가)
        volume_condition = False
        recent_volumes = [t[2] for t in ticks] # 최근 틱들의 누적거래량
        if len(recent_volumes) >= 2: # 최소 2개 이상 있어야 평균 의미 있음
            # 평균 계산 (단순 산술 평균)
            mean_volume = sum(recent_volumes) / len(recent_volumes)
            # 현재 누적거래량이 평균의 3배(200% 증가)보다 큰지 확인
            if mean_volume > 0 : # 0으로 나누는 것 방지
                 volume_condition = current_volume > (mean_volume * 3.0)
                 if volume_condition: print(f"  [Buy Check {code}] Volume condition met: Current={current_volume}, Mean={mean_volume:.0f}")
            # else: print(f"  [Buy Check {code}] Mean volume is 0, skipping volume check.")

        # 3. 매수세 우위 확인 (매도 1호가 잔량 < 매수 1호가 잔량)
        spread_condition = current_ask_vol < current_bid_vol
        if spread_condition: print(f"  [Buy Check {code}] Spread condition met: AskVol={current_ask_vol} < BidVol={current_bid_vol}")

        # --- 최종 판단 및 실행 --- #
        if price_condition and volume_condition and spread_condition:
            stock_name = get_name_by_code(code, self.all_stocks) or ""
            print(f"!!! 자동 매수 조건 충족 (슈팅 감지) !!! {stock_name}({code}) at {current_price:,}")

            # 매수 락 설정 및 타이머 시작 (최초 한번만)
            if not self.buy_check_locks.get(code):
                 self.buy_check_locks[code] = True
                 print(f"  -> Setting buy lock for {code}")
                 if not self.auto_buy_lock_timer.isActive():
                     self.auto_buy_lock_timer.start()

                 # --- 자동 매수 주문 실행 --- #
                 # 사용자 확인 결과: 가격 기준(매도1호가), 호가 구분(시장가)
                 # 가격 파라미터는 _execute_auto_buy 내부에서 재확인하므로 전달 안 함
                 hoga_gb = "03" # 시장가

                 self._execute_auto_buy(code, None, hoga_gb) # price는 None 전달

        # else: # 조건 미충족 시 로그 (너무 많을 수 있음)
            # print(f"  [Buy Check {code}] Conditions not met.")

    # def _check_sell_condition(self, code, fid_data): # 기존 시그니처 변경
    def _check_sell_condition(self, code, current_price, previous_price):
        """보유 종목의 매도 조건을 확인하고 충족 시 매도 주문을 실행합니다."""
        # print(f"[매도 점검] 종목: {code}, 현재가: {current_price}, 직전가: {previous_price}") # 필요시 로그 활성화

        # --- 필요한 데이터 조회 --- #
        purchase_price = 0
        highest_price = self.highest_prices.get(code, 0) # 저장된 최고가
        holding_info = next((item for item in self.holdings_data if item.get("종목코드") == code), None)

        if not holding_info:
            # print(f"  -> 매도 점검 중단: {code} 보유 정보를 찾을 수 없음") # 너무 빈번할 수 있음
            return # 보유 정보 없으면 중단

        purchase_price = holding_info.get("매입가", 0)

        if purchase_price <= 0:
            print(f"  -> 매도 점검 중단: {code} 매입가({purchase_price}) 오류")
            return # 매입가 없으면 기준 계산 불가

        # --- 매도 조건 판단 --- #
        should_sell = False
        reason = ""

        # 조건 1: 저수익 구간 (최고가 <= 매수가 * 1.02)
        if highest_price <= purchase_price * 1.02:
            sell_target_price = purchase_price * 0.98 # -2% 손절 라인
            if current_price < sell_target_price:
                should_sell = True
                reason = f"저수익 구간(-2% 손절): 현재가({current_price:,}) < 목표가({sell_target_price:,.0f})"
        # 조건 2: 고수익 구간 (최고가 > 매수가 * 1.02)
        else:
            if previous_price is not None and previous_price > 0: # 직전 시세가 유효한 경우
                sell_target_price = previous_price * 0.98 # 직전 시세 대비 -2% 하락 라인
                if current_price < sell_target_price:
                    should_sell = True
                    reason = f"고수익 구간(-2% 급락): 현재가({current_price:,}) < 직전가({previous_price:,})*0.98 ({sell_target_price:,.0f})"
            # else: # 직전 시세 없는 경우 (첫 시세 수신 등) - 여기서는 매도 안 함

        # --- 매도 실행 --- #
        if should_sell:
            stock_name = holding_info.get("종목명", "")
            print(f"!!! 자동 매도 조건 충족 !!! {stock_name}({code}) - 이유: {reason}")
            self._execute_auto_sell(code) # 자동 매도 함수 호출

    def _execute_auto_buy(self, code, price, hoga_gb):
        """자동 매수 주문을 실행합니다. (시장가, 매도1호가 기준 수량 계산)"""
        print(f"--- 자동 매수 실행 시도 (시장가): {code} ---")

        # --- 매도 1호가 재확인 (가장 최신 호가 정보 사용) --- #
        ask_price_1 = 0
        ask_price_1_str = self.current_order_book_fid_data.get('41') # FID 41: 매도최우선호가
        if ask_price_1_str:
            try:
                ask_price_1 = int(ask_price_1_str.replace('+', '').replace('-', ''))
            except ValueError:
                print(f"  -> 오류: 자동 매수 시점의 매도 1호가({ask_price_1_str})를 숫자로 변환할 수 없습니다.")
        if ask_price_1 <= 0:
            print(f"  -> 자동 매수 실패: 유효한 매도 1호가가 없어 수량 계산 불가.")
            self._release_buy_lock(code)
            return
        print(f"  -> 매수 주문 기준 가격 (매도 1호가): {ask_price_1:,}")

        # --- 주문 가능 금액 확인 --- #
        buyable_cash = 0
        if hasattr(self, 'lblBuyableMoney'):
             cash_str = self.lblBuyableMoney.text().replace(' 원', '').replace(',', '')
             try: buyable_cash = int(cash_str)
             except ValueError: pass
        if buyable_cash <= 0:
             print(f"  -> 자동 매수 실패: 주문 가능 금액({buyable_cash}) 부족")
             self._release_buy_lock(code)
             return

        # --- 수량 계산 (매도 1호가 기준) --- #
        max_order_amount = 100000 # 최대 10만원
        calculated_qty = 0
        effective_buyable_amount = min(buyable_cash, max_order_amount)
        # 시장가 주문 시에도 예상 체결 가격 기준으로 수량 계산 필요
        calculated_qty = effective_buyable_amount // ask_price_1

        if calculated_qty <= 0:
            print(f"  -> 자동 매수 실패: 계산된 수량({calculated_qty}) 0 이하 (매도1호가: {ask_price_1}, 예산: {effective_buyable_amount})" )
            self._release_buy_lock(code)
            return
        print(f"  -> 계산된 매수 수량: {calculated_qty}")

        # --- 계좌번호 확인 --- #
        account_no = None
        if hasattr(self, 'comboAccount'): account_no = self.comboAccount.currentText()
        if not account_no:
            print(f"  -> 자동 매수 실패: 계좌번호를 찾을 수 없음")
            self._release_buy_lock(code)
            return

        # --- 주문 파라미터 설정 (시장가) --- #
        rqname = f"자동매수(시장가)_{code}_{self.kiwoom._get_unique_screen_no()}" # RQName 변경
        screen_no = self.kiwoom._get_unique_screen_no()
        order_type = 1 # 신규매수
        price = 0 # 시장가 주문 시 가격은 0
        hoga_gb = "03" # 시장가

        print(f"  자동 매수 주문 정보 -> RQName: {rqname}, Screen: {screen_no}, Acc: {account_no}, Code: {code}, Qty: {calculated_qty}, Hoga: 시장가")

        # --- 주문 전송 --- #
        ret = self.kiwoom.send_order(rqname, screen_no, account_no, order_type, code, calculated_qty, price, hoga_gb)
        if ret == 0:
            print(f"  -> 자동 매수(시장가) 주문 요청 성공 (결과 코드: {ret})")
            # 시장가 주문은 재주문 로직이 필요 없을 수 있으나, 일단 추적 시작은 고려 가능
            # TODO: 시장가 주문 추적 및 처리 로직 (필요 시)
        else:
            error_msg = self.kiwoom.get_error_message(ret) if hasattr(self.kiwoom, 'get_error_message') else f"에러코드 {ret}"
            print(f"  -> 자동 매수(시장가) 주문 요청 실패 (결과 코드: {ret}), 메시지: {error_msg}")
            # 실패 시 락 해제 고려
            # self._release_buy_lock(code)

        # 성공/실패와 관계없이 락은 타이머로 해제되거나, 여기서 해제할 수도 있음. 일단 타이머 유지.
        print(f"--- 자동 매수(시장가) 실행 완료: {code} ---")

    def _release_buy_lock(self, code):
        """특정 종목의 매수 락을 즉시 해제합니다."""
        if code in self.buy_check_locks:
            del self.buy_check_locks[code]
            print(f"  -> Buy lock released immediately for {code}")

    def _request_unexecuted_orders(self):
        # D10 : print("_request_unexecuted_orders 호출됨")
        print(f"--- _request_unexecuted_orders 호출됨 (타이머에 의해 주기적 실행) ---") # 로그 추가
        if self.current_account_no:
            # D10 : print(f"  -> 계좌번호 {self.current_account_no}에 대한 미체결 내역 요청")
            print(f"  -> 계좌번호 {self.current_account_no} 미체결 내역 요청 실행.") # 로그 추가
            self.kiwoom.request_unexecuted_orders(self.current_account_no)
        else:
            # D10 : print("  -> 계좌번호가 선택되지 않아 미체결 내역을 요청할 수 없습니다.")
            print("  -> 경고: current_account_no가 없어 미체결 내역 요청 불가.") # 로그 수정
            QMessageBox.warning(self, "미체결 조회", "계좌번호가 선택되지 않았습니다.")
            pass

    def _execute_auto_sell(self, code, current_price):
        # D10 : print(f"Автоматическая продажа для {code} по цене {current_price} (заглушка)")
        pass

    def _get_current_highest_price(self, code):
        # D10 : print(f"Attempting to get highest price for {code}")
        highest_price = self.highest_prices.get(code, 0)
        # D10 : print(f"  -> Current highest for {code} from dict: {highest_price}")
        return highest_price

    def _save_highest_prices_periodically(self):
        # D10 : print("주기적 최고가 저장 시작...")
        self._save_highest_prices()
        if self.save_timer:
            # ... (기존 코드 유지) ...
            # D10 : print("최고가 저장 타이머 시작됨.")
            pass # self.save_timer.start()가 이미 있음


    def _update_real_time_stock_data(self, code, fid_data):
        # D10 : print(f"실시간 데이터 업데이트 수신 (L1856): {code}, fid_data: {fid_data}")

        # tableWidgetConditionResults 업데이트 로직 (이 부분을 수정/강화)
        if hasattr(self, 'tableWidgetConditionResults'):
            target_row = -1
            for row in range(self.tableWidgetConditionResults.rowCount()):
                item = self.tableWidgetConditionResults.item(row, COL_CODE)
                if item and item.text() == code:
                    target_row = row
                    break

            if target_row != -1:
                # print(f"D0 : 조건결과 테이블 업데이트 시작 for {code}, row={target_row}, fid_data={fid_data}") # 디버그 로그

                # 이전에 정의된 update_cell_realtime 과 유사한 함수를 사용하거나 여기서 직접 구현
                # 여기서는 직접 구현하는 방식으로 진행합니다.

                price = fid_data.get(10)      # 현재가 FID 10
                change = fid_data.get(11)     # 전일대비 FID 11
                change_rate = fid_data.get(12)# 등락률 FID 12
                volume = fid_data.get(13)     # 누적거래량 FID 13

                # print(f"D0 : {code} 값 추출: price={price}, change={change}, change_rate={change_rate}, volume={volume}")


                def _set_table_item(row, col, value, is_price_related=False, is_rate=False, is_change=False):
                    item = self.tableWidgetConditionResults.item(row, col)
                    if not item:
                        item = QTableWidgetItem()
                        self.tableWidgetConditionResults.setItem(row, col, item)

                    display_text = ""
                    item_color = Qt.black

                    if value is not None:
                        try:
                            if is_change: # 전일대비
                                val = int(value)
                                display_text = f"{val:+,}"
                                if val > 0: item_color = Qt.red
                                elif val < 0: item_color = Qt.blue
                            elif is_rate: # 등락률
                                val = float(value)
                                display_text = f"{val:+.2f}%"
                                if val > 0: item_color = Qt.red
                                elif val < 0: item_color = Qt.blue
                            else: # 현재가, 거래량 등
                                val = int(value)
                                display_text = f"{val:,}"
                                if is_price_related and change is not None: # 현재가인 경우 전일대비 기준으로 색상 결정
                                    change_val_for_color = int(change)
                                    if change_val_for_color > 0: item_color = Qt.red
                                    elif change_val_for_color < 0: item_color = Qt.blue
                        except ValueError:
                            display_text = str(value) # 숫자 변환 실패 시 문자열 그대로

                    item.setText(display_text)
                    item.setForeground(QBrush(item_color))
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                if price is not None:
                    _set_table_item(target_row, COL_PRICE, price, is_price_related=True)
                if change is not None:
                    _set_table_item(target_row, COL_CHANGE, change, is_change=True)
                if change_rate is not None:
                    _set_table_item(target_row, COL_CHANGE_RATE, change_rate, is_rate=True)
                if volume is not None:
                    _set_table_item(target_row, COL_VOLUME, volume)

                # 실시간 데이터 수신 시 배경색 변경 및 복원 로직 (기존 다른 _update_real_time_stock_data 참고)
                highlight_color = Qt.cyan
                default_bg_color = self.tableWidgetConditionResults.palette().color(QPalette.Base) # 기본 배경색

                cells_to_reset_bg = []
                for col_idx in [COL_PRICE, COL_CHANGE, COL_CHANGE_RATE, COL_VOLUME]: # 업데이트된 컬럼들
                    cell_item = self.tableWidgetConditionResults.item(target_row, col_idx)
                    if cell_item:
                        cell_item.setBackground(highlight_color)
                        cells_to_reset_bg.append(cell_item)
                
                if cells_to_reset_bg:
                    QTimer.singleShot(300, lambda items=cells_to_reset_bg, color=default_bg_color: self._reset_row_background(items, color))


        # 보유종목 테이블 업데이트 로직은 FID 번호로 되어있는지 확인 필요 (현재는 "현재가" 한글키 사용 중)
        # 이 부분도 필요시 수정해야 합니다.
        if hasattr(self, 'tableWidgetHoldings'):
            target_holding_row = -1
            for row in range(self.tableWidgetHoldings.rowCount()):
                code_item = self.tableWidgetHoldings.item(row, 0) # 보유종목테이블의 종목코드 컬럼 인덱스 확인 필요
                if code_item and code_item.text() == code:
                    target_holding_row = row
                    break
            
            if target_holding_row != -1:
                current_price_val = fid_data.get(10) # 현재가 FID
                if current_price_val is not None:
                    # print(f"D0 : 보유종목 {code} 현재가 업데이트: {current_price_val}")
                    price_item = self.tableWidgetHoldings.item(target_holding_row, 4) # 현재가 컬럼 인덱스 4 가정
                    if not price_item:
                        price_item = QTableWidgetItem()
                        self.tableWidgetHoldings.setItem(target_holding_row, 4, price_item)
                    price_item.setText(str(current_price_val))
                    price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    # TODO: 보유종목 테이블의 평가손익, 수익률 등도 실시간 업데이트 필요시 로직 추가


        # 현재 선택된 종목 정보 (nowStock) 업데이트
        if self.nowStock and self.nowStock.code == code:
            current_price_val = fid_data.get(10)
            if current_price_val is not None:
                self.nowStock.current_price = int(current_price_val) # Stocks 객체도 업데이트
                # D10 : print(f"    -> 현재 선택된 종목({self.nowStock.name}) 정보 업데이트: 현재가 {self.nowStock.current_price}")
                if hasattr(self, 'labelNowStockCurrentPrice'): # UI에 해당 라벨이 있다면 업데이트
                    self.labelNowStockCurrentPrice.setText(f"{self.nowStock.current_price:,}원")

        # 최고가 업데이트 로직 (이미 FID 10을 사용하도록 되어 있을 수 있음, 확인)
        # current_price 변수가 이미 한글키로 할당된 상태이므로, fid_data.get(10)을 사용해야 함.
        current_price_for_highest = fid_data.get(10)
        if current_price_for_highest is not None:
            try:
                price_val_int = int(current_price_for_highest)
                # D10 : print(f"  -> 최고가 업데이트 로직 진입 for {code}. 현재 최고가: {self.highest_prices.get(code, 0)}, 새 현재가: {price_val_int}")
                if price_val_int > self.highest_prices.get(code, 0):
                    self.highest_prices[code] = price_val_int
                    # D10 : print(f"    -> 새로운 최고가 기록: {code} - {price_val_int}")
                    # self.highest_price_updated_flag = True # 이 플래그 사용 여부 확인
            except ValueError:
                pass # 숫자 변환 실패 시 최고가 업데이트 건너뜀

    def _handle_order_confirmation(self, order_details):
        # D10 : print(f"주문 확인 처리: {order_details}")
        msg = (f"주문 전송 시도:\n"
               f"계좌: {order_details['account']}\n"
               f"주문유형: {order_details['order_type_str']}\n"
               f"종목: {order_details['stock_name']}({order_details['code']})\n"
               f"거래구분: {order_details['hoga_type_str']}\n"
               f"주문수량: {order_details['quantity']}주\n"
               f"주문가격: {order_details['price'] if order_details['hoga_type_str'] == '지정가' else '시장가'}원\n")
        QMessageBox.information(self, "주문 확인", msg)


    def _process_order_result(self, rqname, trcode, order_no, success):
        # D10 : print(f"주문 결과 처리: rqname={rqname}, trcode={trcode}, order_no={order_no}, success={success}")
        if success:
            # D10 : print(f"  -> 주문 성공: 주문번호 {order_no}")
            self.statusBar().showMessage(f"주문 성공: {order_no}", 5000)
            self.kiwoom.request_unexecuted_orders_repeat()
            if self.current_account_no:
                self.kiwoom.request_account_balance(self.current_account_no)
                self.kiwoom.request_buyable_cash(self.current_account_no)
        else:
            # D10 : print(f"  -> 주문 실패: {order_no if order_no else '번호없음'}. rqname={rqname}")
            QMessageBox.critical(self, "주문 실패", f"주문 전송에 실패했습니다 (rqname: {rqname}).\n"
                                             f"주문번호: {order_no if order_no else 'N/A'}")
            self.statusBar().showMessage(f"주문 실패: {rqname}", 5000)

    def _update_order_numbers(self, order_numbers):
        # D10 : print(f"미체결 주문번호 업데이트 수신: {order_numbers}")
        print(f"--- _update_order_numbers --- 미체결 주문 {len(order_numbers)}건 수신: {order_numbers}") # 상세 로그 추가
        self.unexecuted_order_numbers = order_numbers
        # D10 : print(f"  -> self.unexecuted_order_numbers 업데이트됨: {self.unexecuted_order_numbers}")
        if hasattr(self, 'listWidgetUnexecutedOrders'):
            self.listWidgetUnexecutedOrders.clear()
            self.listWidgetUnexecutedOrders.addItems(order_numbers)
            # D10 : print("  -> 미체결 주문번호 리스트 UI 업데이트됨.")
        if hasattr(self, 'labelUnexecutedCount'):
            self.labelUnexecutedCount.setText(f"미체결: {len(order_numbers)}건")
            # D10 : print(f"  -> 미체결 건수 레이블 업데이트: {len(order_numbers)}건")

    def _get_last_order_number(self):
        # D10 : print("_get_last_order_number 호출됨")
        if self.order_log:
            last_order_no = self.order_log[-1].get('주문번호', '')
            # D10 : print(f"  -> 마지막 주문번호: {last_order_no}")
            return last_order_no
        # D10 : print("  -> 기록된 주문 없음.")
        return ""

    def _show_context_menu_holdings(self, position):
        # D10 : print("보유종목 테이블 우클릭 메뉴 요청")
        if not hasattr(self, 'tableWidgetHoldings'): return

        selected_items = self.tableWidgetHoldings.selectedItems()
        if not selected_items:
            # D10 : print("  -> 선택된 아이템 없음.")
            return

        selected_row = self.tableWidgetHoldings.row(selected_items[0])
        code_item = self.tableWidgetHoldings.item(selected_row, 0)
        name_item = self.tableWidgetHoldings.item(selected_row, 1)
        qty_item = self.tableWidgetHoldings.item(selected_row, 2)

        if not code_item or not name_item or not qty_item:
            # D10 : print("  -> 선택된 행에서 종목 정보 (코드/이름/수량) 누락.")
            return

        code = code_item.text()
        name = name_item.text()
        quantity = qty_item.text()
        # D10 : print(f"  -> 선택된 종목: {name}({code}), 수량: {quantity}")

        menu = QMenu()
        sell_action_text = f"{name}({code}) {quantity}주 매도"
        sell_action = menu.addAction(sell_action_text)
        # D10 : print(f"  -> 매도 액션 생성: '{sell_action_text}'")

        action = menu.exec_(self.tableWidgetHoldings.mapToGlobal(position))

        if action == sell_action:
            # D10 : print(f"  -> '{sell_action_text}' 액션 선택됨.")
            self._sell_selected_stock_slot(code, name, quantity)


    def _sell_selected_stock_slot(self, code, name, quantity_str):
        # D10 : print(f"매도 슬롯 호출됨: {name}({code}), 수량 문자열: '{quantity_str}'")
        try:
            quantity = int(quantity_str.replace(',', ''))
            if quantity <= 0:
                QMessageBox.warning(self, "매도 오류", "매도 가능 수량이 없습니다.")
                # D10 : print("  -> 매도 수량 0 이하 오류")
                return
        except ValueError:
            QMessageBox.warning(self, "매도 오류", "매도 수량 형식이 올바르지 않습니다.")
            # D10 : print(f"  -> 매도 수량 '{quantity_str}' 정수 변환 오류")
            return

        # D10 : print(f"  -> 변환된 매도 수량: {quantity}")

        confirm_msg = f"{name}({code}) {quantity}주를 시장가로 매도하시겠습니까?"
        reply = QMessageBox.question(self, '매도 확인', confirm_msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            # D10 : print("  -> 사용자가 매도 확인.")
            self._sell_stock(code, quantity)
        else:
            # D10 : print("  -> 사용자가 매도 취소.")
            pass


    def _sell_stock(self, code, quantity, price=0, order_type="시장가"):
        # D10 : print(f"매도 주문 실행: {code}, 수량:{quantity}, 가격:{price}, 유형:{order_type}")
        if not self.kiwoom.get_connect_state():
            QMessageBox.warning(self, "주문 오류", "키움증권 서버에 연결되어 있지 않습니다.")
            # D10 : print("  -> 연결 안됨 오류")
            return

        if not self.current_account_no:
            QMessageBox.warning(self, "주문 오류", "선택된 계좌가 없습니다.")
            # D10 : print("  -> 계좌 없음 오류")
            return

        # s 시장가, 1 지정가  <-- 이 부분을 주석 처리합니다.
        hoga_gb = "03" if order_type == "시장가" else "00" # 시장가: 03, 지정가: 00

        # D10 : print(f"  -> 주문 파라미터: 계좌={self.current_account_no}, 유형=매도(1), 코드={code}, 수량={quantity}, 가격={price}, 호가구분={hoga_gb}")

        order_spec = {
            "rqname": f"매도주문_{code}",
            "screen_no": self.kiwoom.get_screen_no(), # 새 화면번호 사용
            "acc_no": self.current_account_no,
            "order_type": 2,  # 1: 신규매수, 2: 신규매도, 3: 매수취소, 4: 매도취소, 5: 매수정정, 6: 매도정정
            "code": code,
            "quantity": quantity,
            "price": price,
            "hoga_gb": hoga_gb, # 00:지정가, 03:시장가 등
            "org_order_no": "" # 원주문번호 (정정/취소시 필요)
        }
        self._send_order_and_log(order_spec)


    def _send_order_and_log(self, order_spec):
        # D10 : print(f"SendOrder 호출: {order_spec['rqname']}")
        order_no_returned = self.kiwoom.send_order(
            order_spec["rqname"],
            order_spec["screen_no"],
            order_spec["acc_no"],
            order_spec["order_type"],
            order_spec["code"],
            order_spec["quantity"],
            order_spec["price"],
            order_spec["hoga_gb"],
            order_spec["org_order_no"]
        )
        # D10 : print(f"  -> SendOrder 반환값 (주문 결과 코드): {order_no_returned} (0이면 성공, 아니면 오류코드)")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "시간": timestamp,
            "요청명": order_spec['rqname'],
            "계좌번호": order_spec['acc_no'],
            "주문유형": order_spec['order_type'], # 숫자 그대로 기록
            "종목코드": order_spec['code'],
            "주문수량": order_spec['quantity'],
            "주문가격": order_spec['price'],
            "호가구분": order_spec['hoga_gb'],
            "원주문번호": order_spec['org_order_no'],
            "API반환값": order_no_returned, # SendOrder의 반환값 (성공:0, 실패:오류코드)
            "주문번호": "" # 실제 주문번호는 Chejan 통해 받음
        }
        self.order_log.append(log_entry)
        # D10 : print(f"  -> 주문 로그 기록됨: {log_entry}")

        if order_no_returned == 0: # 성공
            # D10 : print(f"  -> 주문 요청 성공 ({order_spec['rqname']}). 실제 주문번호는 체결/잔고 데이터로 확인.")
            self.statusBar().showMessage(f"주문 요청 성공: {order_spec['rqname']}", 5000)
            self._process_order_result(order_spec['rqname'], "", "", True) # 임시 주문번호 없음
        else: # 실패
            error_msg = f"주문 요청 실패 ({order_spec['rqname']}). 오류코드: {order_no_returned}"
            print(f"오류: {error_msg}") # 이것은 남김
            self.statusBar().showMessage(error_msg, 5000)
            QMessageBox.critical(self, "주문 실패", error_msg)
            self._process_order_result(order_spec['rqname'], "", "", False)


    def _request_and_display_order_info(self, order_no):
        # D10 : print(f"주문 상세 정보 요청: {order_no}")
        if not self.kiwoom.get_connect_state(): print("오류: 키움 연결 안됨"); return
        if not self.current_account_no: print("오류: 계좌 선택 안됨"); return

        self.kiwoom.request_order_info(self.current_account_no, order_no)
        # 결과는 _on_receive_tr_data 에서 opt10076 으로 처리됨

    def closeEvent(self, event):
        # D10 : print("프로그램 종료 이벤트 발생")
        self._save_highest_prices() # 종료 시 최고가 저장
        if self.save_timer and self.save_timer.isActive():
            self.save_timer.stop()
            # D10 : print("최고가 저장 타이머 중지됨.")

        if self.kiwoom.get_connect_state():
            # D10 : print("Kiwoom API 연결 해제 시도...")
            # 모든 실시간 데이터 해제
            # 현재 조건검색 실시간 중단
            if self.active_condition_name and self.active_condition_index is not None:
                # D10 : print(f"  -> 조건검색 실시간 중단: {self.active_condition_name} (scr: {self.condition_real_time_screen})")
                self.kiwoom.send_condition_stop(self.condition_real_time_screen, self.active_condition_name, self.active_condition_index)
                self.condition_real_time_screen = None # 화면번호 사용 완료
                self.active_condition_name = None
                self.active_condition_index = None

            # 등록된 모든 실시간 데이터 해제 (화면번호 9000번대 사용 가정)
            # D10 : print("  -> 등록된 모든 실시간 데이터 해제 시도 (화면번호 9000~9XXX)...")
            for i in range(100): # 충분한 범위의 화면번호, 실제 사용한 화면만 관리하는게 더 좋음
                self.kiwoom.unregister_real_time_stock_data(str(9000 + i))

            self.kiwoom.disconnect()
            # D10 : print("Kiwoom API 연결 해제 완료.")
        super().closeEvent(event)
        # D10 : print("애플리케이션 종료.")

    # --- 화면 번호 관리 --- #
    def _get_unique_screen_no(self, is_real_time_cond=False, is_real_time_data=False):
        if is_real_time_cond:
            return self.kiwoom._get_unique_screen_no(is_real_time_data=True)
        elif is_real_time_data:
            return self.kiwoom._get_unique_screen_no(is_real_time_data=True)
        else:
            return self.kiwoom._get_unique_screen_no()

    def _log_order_message(self, message, log_type="order"): # log_type 인자 추가 및 기본값 설정
        if hasattr(self, 'plainTextEditOrderLog'):
            self.plainTextEditOrderLog.appendPlainText(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    myWindow = MyWindow()
    myWindow.show()
    sys.exit(app.exec_())
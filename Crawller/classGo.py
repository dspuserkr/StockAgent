# classGo.py

class Stocks:
    def __init__(self, code, name, current_price=0):
        self.code = code
        self.name = name
        self.current_price = current_price

    def __repr__(self):
        return f"Stocks(code='{self.code}', name='{self.name}', current_price={self.current_price})"

# --- Helper Functions --- #

def get_name_by_code(code, stock_list):
    """Stocks 객체 리스트에서 종목 코드로 종목명을 찾습니다."""
    for stock in stock_list:
        if stock.code == code:
            return stock.name
    return None # 찾지 못한 경우

def get_code_by_name(name, stock_list):
    """Stocks 객체 리스트에서 종목명으로 종목 코드를 찾습니다."""
    for stock in stock_list:
        if stock.name == name:
            return stock.code
    return "" # 찾지 못한 경우 빈 문자열 반환

class DailyStockData:
    def __init__(self,
                 종목코드: str = "",
                 종목명: str = "",
                 일자: str = "",
                 시가: str = "",
                 고가: str = "",
                 저가: str = "",
                 현재가: str = "",
                 거래량: str = "",
                 거래대금: str = "",
                 sma5: str = "",
                 sma10: str = "",
                 sma20: str = "",
                 sma60: str = "",
                 sma120: str = "",
                 sma240: str = "",
                 ema5: str = "",
                 ema10: str = "",
                 ema20: str = "",
                 ema60: str = "",
                 ema120: str = "",
                 ema240: str = "",
                 rsi14: str = "",
                 macd: str = "",
                 macd_sig: str = "",
                 macd_hist: str = "",
                 bb_upper: str = "",
                 bb_mid: str = "",
                 bb_lower: str = "",
                 stoch_k: str = "",
                 stoch_d: str = ""):
        self.종목코드 = 종목코드
        self.종목명 = 종목명
        self.일자 = 일자
        self.시가 = 시가
        self.고가 = 고가
        self.저가 = 저가
        self.현재가 = 현재가
        self.거래량 = 거래량
        self.거래대금 = 거래대금
        self.sma5 = sma5
        self.sma10 = sma10
        self.sma20 = sma20
        self.sma60 = sma60
        self.sma120 = sma120
        self.sma240 = sma240
        self.ema5 = ema5
        self.ema10 = ema10
        self.ema20 = ema20
        self.ema60 = ema60
        self.ema120 = ema120
        self.ema240 = ema240
        self.rsi14 = rsi14
        self.macd = macd
        self.macd_sig = macd_sig
        self.macd_hist = macd_hist
        self.bb_upper = bb_upper
        self.bb_mid = bb_mid
        self.bb_lower = bb_lower
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d

    def __repr__(self):
        return (f"DailyStockData(일자='{self.일자}', 종목코드='{self.종목코드}', "
                f"현재가='{self.현재가}', 거래량='{self.거래량}')")

    @classmethod
    def get_csv_headers(cls):
        return [
            "종목코드", "종목명", "일자", "시가", "고가", "저가", "현재가", 
            "거래량", "거래대금",
            "sma5", "sma10", "sma20", "sma60", "sma120", "sma240",
            "ema5", "ema10", "ema20", "ema60", "ema120", "ema240",
            "rsi14", "macd", "macd_sig", "macd_hist", 
            "bb_upper", "bb_mid", "bb_lower",
            "stoch_k", "stoch_d"
        ]

    def to_dict(self):
        return {header: getattr(self, header.replace("거 래량", "거래량"), "") for header in self.get_csv_headers()}

class MinStockData:
    def __init__(self,
                 종목코드: str = "",
                 종목명: str = "",
                 체결시간: str = "",
                 시가: str = "",
                 고가: str = "",
                 저가: str = "",
                 현재가: str = "",
                 거래량: str = "",
                 거래대금: str = "",
                 이격도5: str = "",
                 이격도20: str = "",
                 전일종가: str = "",

                 # 이동평균선
                 sma5: str = "",
                 sma10: str = "",
                 sma20: str = "",
                 sma60: str = "",
                 sma120: str = "",
                 sma240: str = "",
                 ema5: str = "",
                 ema10: str = "",
                 ema20: str = "",
                 ema60: str = "",
                 ema120: str = "",
                 ema240: str = "",
                 # RSI
                 rsi14: str = "",
                 # Stochastic
                 stoch_k: str = "",
                 stoch_d: str = "",
                 # 볼린저 밴드
                 bb_upper: str = "",
                 bb_mid: str = "",
                 bb_lower: str = "",
                 # MACD
                 macd: str = "",
                 macd_sig: str = "",
                 macd_hist: str = "",
                 # 매물대 차트 (Volume Profile)
                 vp_high: str = "",
                 vp_mid: str = "",
                 vp_low: str = ""):
        self.종목코드 = 종목코드
        self.종목명 = 종목명
        self.체결시간 = 체결시간
        self.시가 = 시가
        self.고가 = 고가
        self.저가 = 저가
        self.현재가 = 현재가
        self.거래량 = 거래량
        self.거래대금 = 거래대금
        # 추가 필드
        self.이격도5 = 이격도5
        self.이격도20 = 이격도20
        self.전일종가 = 전일종가
        # 이동평균선
        self.sma5 = sma5
        self.sma10 = sma10
        self.sma20 = sma20
        self.sma60 = sma60
        self.sma120 = sma120
        self.sma240 = sma240
        self.ema5 = ema5
        self.ema10 = ema10
        self.ema20 = ema20
        self.ema60 = ema60
        self.ema120 = ema120
        self.ema240 = ema240
        # RSI
        self.rsi14 = rsi14
        # Stochastic
        self.stoch_k = stoch_k
        self.stoch_d = stoch_d
        # 볼린저 밴드
        self.bb_upper = bb_upper
        self.bb_mid = bb_mid
        self.bb_lower = bb_lower
        # MACD
        self.macd = macd
        self.macd_sig = macd_sig
        self.macd_hist = macd_hist
        # 매물대 차트
        self.vp_high = vp_high
        self.vp_mid = vp_mid
        self.vp_low = vp_low

    def __repr__(self):
        return (f"MinStockData(체결시간='{self.체결시간}', 종목코드='{self.종목코드}', "
                f"현재가='{self.현재가}', 거래량='{self.거래량}')")

    @classmethod
    def get_csv_headers(cls):
        return [
            "종목코드", "종목명", "체결시간", "시가", "고가", "저가", "현재가", 
            "거래량", "거래대금",
            "이격도5", "이격도20", "전일종가",
            "sma5", "sma10", "sma20", "sma60", "sma120", "sma240",
            "ema5", "ema10", "ema20", "ema60", "ema120", "ema240",
            "rsi14",
            "stoch_k", "stoch_d",
            "bb_upper", "bb_mid", "bb_lower",
            "vp_high", "vp_mid", "vp_low"
        ]

    def to_dict(self):
        return {header: getattr(self, header, "") for header in self.get_csv_headers()}

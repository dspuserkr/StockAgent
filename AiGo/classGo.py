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

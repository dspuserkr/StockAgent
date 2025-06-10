import sys
import os
sys.path.append(os.path.dirname(__file__))
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QDate
import subprocess
from datetime import datetime, timedelta
from kiwoomAPI import KiwoomAPI
from classGo import DailyStockData, MinStockData
import util
import time

# 예시: 종목코드 리스트와 이름을 준비하는 부분 (실제 코드에 맞게 수정 필요)
def get_code_list():
    # 실제로는 KiwoomAPI의 get_code_list_by_market 등으로 코드/이름 리스트를 만드세요
    # 예시: [("000020", "동화약품"), ...]
    return [("000020", "동화약품"), ("000040", "KR모터스")]  # 실제 코드로 대체

def main():
    app = QApplication(sys.argv)
    kiwoom = KiwoomAPI()
    kiwoom.login()
    # 날짜, 일봉/분봉 등 파라미터는 실제 사용에 맞게 입력
    start_date = "20220427"
    end_date = "20240427"
    day_min = "일봉"  # 또는 "분봉"
    code_list = get_code_list()
    total = len(code_list)
    print(f"전체 종목 수: {total}")
    try:
        for idx, (code, name) in enumerate(code_list):
            if day_min == "일봉":
                kiwoom.request_daily_chart_data(code, base_date=end_date, start_date_for_filter=start_date)
                data_list = kiwoom.stock_data
                util.save_chart_data_to_csv(start_date, end_date, "일봉", code, name, data_list, {})
            else:
                kiwoom.request_minute_chart_data(code, tick_interval="1", start_date_for_filter=start_date, end_date_for_filter=end_date)
                data_list = kiwoom.stock_data
                util.save_chart_data_to_csv(start_date, end_date, "분봉", code, name, data_list, {})
            if idx % 20 == 0 or idx == total - 1:
                print(f"[{idx+1}/{total}]")
            time.sleep(0.7)  # TR 제한
    except KeyboardInterrupt:
        print("중지됨 (KeyboardInterrupt)")
    print("작업 완료")
    sys.exit(app.exec_())

class CrawllerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = os.path.join(os.path.dirname(__file__), "CrawllerWindow.ui")
        uic.loadUi(ui_path, self)
        self.move(100, 100)
        self.raise_()
        self.activateWindow()
        self.proc = None
        self.btnStartCrawlling.clicked.connect(self.run_crawlling)
        self.btnQuit.clicked.connect(self.stop_crawlling)
        # 디폴트값 설정
        today = QDate.currentDate()
        self.dateEditEnd.setDate(today)
        self.cBoxSelectDayMin.setCurrentText("일봉")
        self.set_start_date_default("일봉")
        self.cBoxSelectDayMin.currentTextChanged.connect(self.set_start_date_default)

    def set_start_date_default(self, day_min):
        today = QDate.currentDate()
        if day_min == "일봉":
            start = today.addYears(-2)
        else:
            start = today.addMonths(-1)
        self.dateEditStart.setDate(start)

    def run_crawlling(self):
        day_min = self.cBoxSelectDayMin.currentText()  # "일봉" or "분봉"
        start_date = self.dateEditStart.date().toString("yyyyMMdd")
        end_date = self.dateEditEnd.date().toString("yyyyMMdd")
        script_path = os.path.join(os.path.dirname(__file__), "fromKiwoom.py")
        cmd = [
            "python", script_path,
            "--daymin", day_min,
            "--start", start_date,
            "--end", end_date
        ]
        self.pTELog.appendPlainText(f"실행: {' '.join(cmd)}")
        self.proc = subprocess.Popen(cmd)

    def stop_crawlling(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.pTELog.appendPlainText("콘솔 데이터 수집 프로세스 중지 요청됨.")
        else:
            self.pTELog.appendPlainText("진행 중인 콘솔 프로세스가 없습니다.")

if __name__ == "__main__":
    main() 
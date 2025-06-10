from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QDate, Qt
import sys
from datetime import datetime, timedelta
import subprocess
import os
from Crawller.CrawllerMain import CrawllerWindow
# from common.KiwoomAPI import KiwoomAPI  # 로그인 관련 코드 삭제
# from common.classGo import DailyStockData, MinStockData  # 필요 없으면 삭제
# from common import util  # 필요 없으면 삭제
import signal

class KiwoomApplicationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("KiwoomApplicationWindow.ui", self)
        self.move(0, 0)  # 윈도우를 (0,0) 위치로 이동
        self.raise_()  # 항상 앞으로 오도록
        self.activateWindow()  # 포커스 주기
        # self.kiwoom = KiwoomAPI()  # 삭제
        # self.kiwoom.login_result_signal.connect(self._on_login_result)  # 삭제
        # self._login_kiwoom()  # 삭제
        self.btnCrawller.clicked.connect(self.run_crawller)
        self.btnAiGo.clicked.connect(self.run_aigo)

    # def _login_kiwoom(self):  # 삭제
    #     self.lblConnection.setText("No Connection")
    #     self.kiwoom.login()

    # def _on_login_result(self, err_code):  # 삭제
    #     if err_code == 0:
    #         self.lblConnection.setText("로그인 성공")
    #     else:
    #         self.lblConnection.setText("No Connection")

    def run_crawller(self):
        self.pTELog.appendPlainText("크롤러 실행 버튼이 눌렸습니다.")
        self.crawller_window = CrawllerWindow()
        self.crawller_window.show()

    def run_aigo(self):
        self.pTELog.appendPlainText("AiGo 실행 버튼이 눌렸습니다.")

def handle_exit(signum, frame):
    print("프로세스가 종료되었습니다.")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_exit)
signal.signal(signal.SIGINT, handle_exit)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KiwoomApplicationWindow()
    window.show()
    input("Press Enter to exit...")
    sys.exit(app.exec_())

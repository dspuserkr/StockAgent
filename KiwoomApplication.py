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

# TODO: 주식일봉차트요청 (opt10081) TR 요청 시 ErrCode가 비어있는 에러 발생. 이벤트 루프가 이미 존재하거나, 응답이 비정상적으로 돌아오는 경우가 있음. 
#       - 이벤트 루프 중복 생성/종료 로직 점검 필요
#       - TR 요청/응답 흐름 및 에러 발생 시점 상세 로그 추가 및 원인 분석 필요

def check_stop_flag():
    stop_flag_path = os.path.join(os.path.dirname(__file__), "stop.flag")
    if os.path.exists(stop_flag_path):
        print("중지 플래그 감지, 안전하게 종료합니다.")
        os.remove(stop_flag_path)
        return True
    return False

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
    print("Made by Stewart Kim !!!")
    sys.exit(app.exec_())

# 현재 파일 기준 상위 폴더 경로 구하기
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
exclusion_file_path = os.path.join(parent_dir, "관리종목, 담보대출불가능종목, ETF, 초저유동성종목, 증거금.txt")

try:
    with open(exclusion_file_path, 'r', encoding='utf-8') as f:
        exclusion_keywords = [kw.strip() for kw in f.read().split(',') if kw.strip()]
    print(f"D1: 제외 키워드 로드 완료: {len(exclusion_keywords)}개")
except Exception as e:
    print(f"D1: 제외 키워드 파일 로드 실패: {e}")

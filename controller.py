import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
import time


def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str, manual_numbers: list = None):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    if _mode == lotto645.Lotto645Mode.MANUAL:
        assert manual_numbers is not None, "수동 모드에서는 manual_numbers가 필요합니다."
    response = lotto.buy_lotto645(authCtrl, cnt, _mode, manual_numbers=manual_numbers)
    response['balance'] = lotto.get_balance(auth_ctrl=authCtrl)
    return response

def check_winning_lotto645(authCtrl: auth.AuthController) -> dict:
    lotto = lotto645.Lotto645()
    item = lotto.check_winning(authCtrl)
    return item

def buy_win720(authCtrl: auth.AuthController, username: str):
    pension = win720.Win720()
    response = pension.buy_Win720(authCtrl, username)
    response['balance'] = pension.get_balance(auth_ctrl=authCtrl)
    return response

def check_winning_win720(authCtrl: auth.AuthController) -> dict:
    pension = win720.Win720()
    item = pension.check_winning(authCtrl)
    return item

def send_message(mode: int, lottery_type: int, response: dict, token: str, chat_id: str, userid: str):
    notify = notification.Notification()

    if mode == 0:
        if lottery_type == 0:
            notify.send_lotto_winning_message(userid, response, token, chat_id)
        else:
            notify.send_win720_winning_message(userid, response, token, chat_id)
    elif mode == 1:
        if lottery_type == 0:
            notify.send_lotto_buying_message(userid, response, token, chat_id)
        else:
            notify.send_win720_buying_message(userid, response, token, chat_id)

def check():
    load_dotenv()

    usernames = os.environ.get('USERNAME', '').splitlines()  # 개행으로 구분된 USERNAME 처리
    passwords = os.environ.get('PASSWORD', '').splitlines()  # 개행으로 구분된 PASSWORD 처리
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    if len(usernames) != len(passwords):
        print("USERNAME과 PASSWORD의 개수가 일치하지 않습니다.")
        return

    for username, password in zip(usernames, passwords):  # 각 사용자에 대해 반복
        print(f"Processing for user: {username}")

        globalAuthCtrl = auth.AuthController()
        try:
            globalAuthCtrl.login(username, password)
        except Exception as e:
            print(f"[controller] 로그인 실패 for user {username}: {e}")
            # Skip this user and continue with next one
            continue

        response = check_winning_lotto645(globalAuthCtrl)
        send_message(0, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)

        time.sleep(10)

        response = check_winning_win720(globalAuthCtrl)
        send_message(0, 1, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)


def buy():
    load_dotenv()

    usernames = os.environ.get('USERNAME', '').splitlines()  # 개행으로 구분된 USERNAME 처리
    passwords = os.environ.get('PASSWORD', '').splitlines()  # 개행으로 구분된 PASSWORD 처리
    auto_count = int(os.environ.get('AUTO_COUNT', 5))  # 자동 구매 개수
    manual_count = int(os.environ.get('MANUAL_COUNT', 0))  # 수동 구매 개수
    manual_numbers_raw = os.environ.get('MANUAL_NUMBERS', '').splitlines()  # 개행으로 구분된 수동 번호
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    if len(usernames) != len(passwords):
        print("USERNAME과 PASSWORD의 개수가 일치하지 않습니다.")
        return

    # 자동 및 수동 구매 개수 합계 검증
    total_count = auto_count + manual_count
    if total_count > 5:
        print("AUTO_COUNT와 MANUAL_COUNT의 합은 최대 5개여야 합니다.")
        return

    # 수동 번호 처리
    manual_numbers = []
    for line in manual_numbers_raw:
        try:
            numbers = list(map(int, line.split(',')))  # 쉼표로 구분된 번호를 정수 리스트로 변환
            if len(numbers) != 6 or not all(1 <= num <= 45 for num in numbers):
                raise ValueError("번호는 6개이며 각 번호는 1~45 사이여야 합니다.")
            manual_numbers.append(numbers)
        except ValueError as e:
            print(f"수동 번호 처리 중 오류 발생: {e}")
            return

    if len(manual_numbers) != manual_count:
        print("MANUAL_COUNT와 제공된 수동 번호의 개수가 일치하지 않습니다.")
        return

    for username, password in zip(usernames, passwords):  # 각 사용자에 대해 반복
        print(f"Processing for user: {username}")

        globalAuthCtrl = auth.AuthController()
        globalAuthCtrl.login(username, password)

        # 자동 구매 처리
        if auto_count > 0:
            response = buy_lotto645(globalAuthCtrl, auto_count, "AUTO")
            send_message(1, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)

        time.sleep(10)

        # 수동 구매 처리
        if manual_count > 0:
            response = buy_lotto645(globalAuthCtrl, manual_count, "MANUAL", manual_numbers=manual_numbers)
            send_message(1, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)


def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
  

if __name__ == "__main__":
    run()

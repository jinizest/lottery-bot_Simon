import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
import time
import requests


def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str, manual_numbers: list = None):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    response = lotto.buy_lotto645(authCtrl, cnt, _mode, manual_numbers=manual_numbers)
    response['balance'] = authCtrl.get_user_balance()
    return response


def check_winning_lotto645(authCtrl: auth.AuthController) -> dict:
    lotto = lotto645.Lotto645()
    item = lotto.check_winning(authCtrl)
    return item


def buy_win720(authCtrl: auth.AuthController, username: str):
    pension = win720.Win720()
    response = pension.buy_Win720(authCtrl, username)
    response['balance'] = authCtrl.get_user_balance()
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


def check_network_connectivity() -> bool:
    targets = [
        "https://www.dhlottery.co.kr/common.do?method=main",
        "https://ol.dhlottery.co.kr/olotto/game/game645.do",
    ]
    ok = True
    for url in targets:
        try:
            print(f"[network] Checking connectivity url={url}")
            res = requests.get(url, timeout=10)
            print(f"[network] OK url={url} status={res.status_code}")
        except requests.RequestException as exc:
            ok = False
            print(f"[network] FAIL url={url} error={exc}")
    return ok


def check():
    load_dotenv()

    usernames = os.environ.get('USERNAME', '').splitlines()
    passwords = os.environ.get('PASSWORD', '').splitlines()
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    if len(usernames) != len(passwords):
        print("USERNAME과 PASSWORD의 개수가 일치하지 않습니다.")
        return

    for username, password in zip(usernames, passwords):
        print(f"Processing for user: {username}")

        globalAuthCtrl = auth.AuthController()
        try:
            if hasattr(globalAuthCtrl, 'http_client') and hasattr(globalAuthCtrl.http_client, 'session'):
                try:
                    globalAuthCtrl.http_client.session.cookies.clear()
                except Exception:
                    pass

            globalAuthCtrl.login(username, password)
        except Exception as e:
            print(f"[controller] 로그인 실패 for user {username}: {e}")
            continue

        response = check_winning_lotto645(globalAuthCtrl)
        send_message(0, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)


        # response = check_winning_win720(globalAuthCtrl)
        # send_message(0, 1, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)


def check_win():
    load_dotenv()

    usernames = os.environ.get('USERNAME', '').splitlines()
    passwords = os.environ.get('PASSWORD', '').splitlines()
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    for username, password in zip(usernames, passwords):
        print(f"Processing for user: {username}")

        globalAuthCtrl = auth.AuthController()
        try:
            if hasattr(globalAuthCtrl, 'http_client') and hasattr(globalAuthCtrl.http_client, 'session'):
                try:
                    globalAuthCtrl.http_client.session.cookies.clear()
                except Exception:
                    pass

            globalAuthCtrl.login(username, password)
        except Exception as e:
            print(f"[controller] 로그인 실패 for user {username}: {e}")
            continue

        response = check_winning_win720(globalAuthCtrl)
        send_message(0, 1, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)

def buy():
    load_dotenv()

    usernames = os.environ.get('USERNAME', '').splitlines()
    passwords = os.environ.get('PASSWORD', '').splitlines()
    auto_count = int(os.environ.get('AUTO_COUNT', 5))
    manual_count = int(os.environ.get('MANUAL_COUNT', 0))
    manual_numbers_raw = os.environ.get('MANUAL_NUMBERS_RAW', '').splitlines()
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    total_count = auto_count + manual_count
    if total_count > 5:
        print("AUTO_COUNT와 MANUAL_COUNT의 합은 최대 5개여야 합니다.")
        return

    manual_numbers = []
    for line in manual_numbers_raw:
        try:
            raw_numbers = [part.strip() for part in line.split(',') if part.strip()]
            if len(raw_numbers) != 6:
                raise ValueError("번호는 6개여야 합니다.")

            formatted_numbers = []
            for raw in raw_numbers:
                num = int(raw)
                if not 1 <= num <= 45:
                    raise ValueError("각 번호는 1~45 사이여야 합니다.")
                formatted_numbers.append(f"{num:02d}")

            manual_numbers.append(formatted_numbers)
        except ValueError as e:
            print(f"수동 번호 처리 중 오류 발생: {e}")
            return

    if len(manual_numbers) != manual_count:
        print("MANUAL_COUNT와 제공된 수동 번호의 개수가 일치하지 않습니다.")
        return

    if not check_network_connectivity():
        print("[controller] 네트워크 연결 실패로 구매를 중단합니다.")
        return

    for username, password in zip(usernames, passwords):
        print(f"Processing for user: {username}")

        globalAuthCtrl = auth.AuthController()
        try:
            if hasattr(globalAuthCtrl, 'http_client') and hasattr(globalAuthCtrl.http_client, 'session'):
                try:
                    globalAuthCtrl.http_client.session.cookies.clear()
                except Exception:
                    pass

            try:
                globalAuthCtrl.login(username, password)
            except Exception as e:
                print(f"[controller] 로그인 실패 for user {username}: {e}")
                continue
        except Exception:
            try:
                globalAuthCtrl.login(username, password)
            except Exception as e:
                print(f"[controller] 로그인 실패 for user {username}: {e}")
                continue

        def _safe_balance() -> str:
            try:
                return globalAuthCtrl.get_user_balance()
            except Exception as exc:
                return f"조회 실패: {exc}"

        if auto_count > 0:
            try:
                response = buy_lotto645(globalAuthCtrl, auto_count, "AUTO")
            except requests.RequestException as exc:
                response = {"result": {"resultMsg": f"NETWORK_ERROR: {exc}"}}
            response['balance'] = _safe_balance()
            send_message(1, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)

        time.sleep(5)

        if manual_count > 0:
            try:
                response = buy_lotto645(globalAuthCtrl, manual_count, "MANUAL", manual_numbers=manual_numbers)
            except requests.RequestException as exc:
                response = {"result": {"resultMsg": f"NETWORK_ERROR: {exc}"}}
            response['balance'] = _safe_balance()
            send_message(1, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)

        time.sleep(10)

        globalAuthCtrl.http_client.session.cookies.clear()
        globalAuthCtrl.login(username, password)

        try:
            response = buy_win720(globalAuthCtrl, username)
            send_message(1, 1, response=response, token=telegram_bot_token, chat_id=telegram_chat_id, userid=username)
        except Exception as e:
            print(f"[controller] 연금복권 구매 실패 for user {username}: {e}")
            continue


def run():
    if len(sys.argv) < 2:
        print("Usage: python controller.py [buy|check]")
        return

    if sys.argv[1] == "buy":
        buy()
    elif sys.argv[1] == "check":
        check()
    elif sys.argv[1] == "check_win":
        check_win()


if __name__ == "__main__":
    run()

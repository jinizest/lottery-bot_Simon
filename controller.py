import os
import sys
from dotenv import load_dotenv

import auth
import lotto645
import win720
import notification
import time


def buy_lotto645(authCtrl: auth.AuthController, cnt: int, mode: str):
    lotto = lotto645.Lotto645()
    _mode = lotto645.Lotto645Mode[mode.upper()]
    response = lotto.buy_lotto645(authCtrl, cnt, _mode)
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

def send_message(mode: int, lottery_type: int, response: dict, token: str, chat_id: str):
    notify = notification.Notification()

    if mode == 0:
        if lottery_type == 0:
            notify.send_lotto_winning_message(response, token, chat_id)
        else:
            notify.send_win720_winning_message(response, token, chat_id)
    elif mode == 1: 
        if lottery_type == 0:
            notify.send_lotto_buying_message(response, token, chat_id)
        else:
            notify.send_win720_buying_message(response, token, chat_id)

def check():
    load_dotenv()

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)
    
    response = check_winning_lotto645(globalAuthCtrl)
    send_message(0, 0, response=response, token=telegram_bot_token, chat_id=telegram_chat_id)

    time.sleep(10)
    
    response = check_winning_win720(globalAuthCtrl)
    send_message(0, 1, response=response, token=telegram_bot_token, chat_id=telegram_chat_id)

def buy(): 
    
    load_dotenv() 

    username = os.environ.get('USERNAME')
    password = os.environ.get('PASSWORD')
    count = int(os.environ.get('COUNT'))
    telegram_bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    telegram_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    mode = "AUTO"

    if not telegram_bot_token or not telegram_chat_id:
        print("Telegram 환경 변수가 설정되지 않았습니다.")
        return

    globalAuthCtrl = auth.AuthController()
    globalAuthCtrl.login(username, password)

    response = buy_lotto645(globalAuthCtrl, count, mode) 
    send_message(1, 0, response=response,  token=telegram_bot_token, chat_id=telegram_chat_id)

    time.sleep(10)

    response = buy_win720(globalAuthCtrl, username) 
    send_message(1, 1, response=response,  token=telegram_bot_token, chat_id=telegram_chat_id)

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

import html
import json
import logging
import re
import requests

import common

common.setup_logging()
logger = logging.getLogger(__name__)

class Notification:
    def send_lotto_buying_message(self, userid: str, body: dict, token: str, chat_id: str) -> None:
        try:
            result = body.get("result", {})
            result_msg = result.get("resultMsg", "FAILURE").upper()
            balance = body.get("balance", "N/A")

            if result_msg != "SUCCESS":
                buy_round = result.get("buyRound", "알 수 없음")
                message = f"{userid}님, {buy_round}회 로또 구매 실패!!! :moneybag: 남은잔액 : {balance}\n사유: {result_msg}"
                self._send_telegram(token, chat_id, message, escape_message=True)
                return

            lotto_number_str = self.make_lotto_number_message(result.get("arrGameChoiceNum", []))
            buy_round = result.get("buyRound", "알 수 없음")
            lotto_block = f"<pre>{html.escape(lotto_number_str)}</pre>"
            message = f"{html.escape(userid + '님, ' + str(buy_round) + '회 로또 구매 완료 :moneybag: 남은잔액 : ' + str(balance))}\n{lotto_block}"
            self._send_telegram(token, chat_id, message)
        except KeyError as e:
            error_message = f"{userid}님, 로또 구매 처리 중 오류 발생: {e}"
            self._send_telegram(token, chat_id, error_message, escape_message=True)

    def make_lotto_number_message(self, lotto_number: list) -> str:
        assert type(lotto_number) == list

        # parse list without last number 3
        lotto_number = [x[:-1] for x in lotto_number]
        
        # remove alphabet and | replace white space  from lotto_number
        lotto_number = [x.replace("|", " ") for x in lotto_number]
        
        # lotto_number to string 
        lotto_number = '\n'.join(x for x in lotto_number)

        return lotto_number

    def send_win720_buying_message(self, userid: str, body: dict, token: str, chat_id: str) -> None:
        try:
            result_code = body.get("resultCode", "UNKNOWN")
            result_msg = body.get("resultMsg", "알 수 없는 오류")
            balance = body.get("balance", "N/A")

            result_msg_text = self._stringify_result_msg(result_msg)

            if result_code != '100':
                win720_round = body.get("round", "알 수 없음")
                if "|" in result_msg_text:
                    parts = result_msg_text.split("|")
                    if len(parts) > 3 and parts[3]:
                        win720_round = parts[3]
                message = f"{userid}님, {win720_round}회 연금복권 구매 실패!!! :moneybag: 남은잔액 : {balance}\n사유: {result_msg_text}"
                self._send_telegram(token, chat_id, message, escape_message=True)
                return

            win720_round = body.get("round", "알 수 없음")
            if "|" in result_msg_text:
                parts = result_msg_text.split("|")
                if len(parts) > 3 and parts[3]:
                    win720_round = parts[3]
            win720_number_str = self.make_win720_number_message(body.get("saleTicket", ""))
            win720_block = f"<pre>{html.escape(win720_number_str)}</pre>"
            message = f"{html.escape(userid + '님, ' + str(win720_round) + '회 연금복권 구매 완료 :moneybag: 남은잔액 : ' + str(balance))}\n{win720_block}"
            self._send_telegram(token, chat_id, message)
        except KeyError as e:
            error_message = f"{userid}님, 연금복권 구매 처리 중 오류 발생: {e}"
            self._send_telegram(token, chat_id, error_message, escape_message=True)

    def make_win720_number_message(self, win720_number: str) -> str:
        if isinstance(win720_number, (list, tuple)):
            win720_number = ",".join(str(value) for value in win720_number)
        elif isinstance(win720_number, dict):
            win720_number = json.dumps(win720_number, ensure_ascii=False)
        elif win720_number is None:
            win720_number = ""

        formatted_numbers = []
        for number in str(win720_number).split(","):
            if not number:
                continue
            formatted_number = f"{number[0]}조 " + " ".join(number[1:])
            formatted_numbers.append(formatted_number)
        return "\n".join(formatted_numbers)

    def _stringify_result_msg(self, result_msg) -> str:
        if isinstance(result_msg, str):
            return result_msg
        if isinstance(result_msg, (dict, list, tuple)):
            try:
                return json.dumps(result_msg, ensure_ascii=False)
            except (TypeError, ValueError):
                return str(result_msg)
        if result_msg is None:
            return "알 수 없는 오류"
        return str(result_msg)

    def send_lotto_winning_message(self, userid: str, winning: dict, token: str, chat_id: str) -> None: 
        assert type(winning) == dict
        assert type(token) == str
        assert type(chat_id) == str

        try:
            lotto_details = winning.get("lotto_details") or []

            if not lotto_details:
                message = html.escape(f"{userid}님, 최근 로또 구매/당첨 이력이 없습니다.")
                self._send_telegram(token, chat_id, message)
                return

            round_val = winning.get("round", "-")
            money = winning.get("money", "-")

            max_label_status_length = max(
                len(f"{line['label']} {line['status']}") for line in lotto_details
            )

            formatted_lines = []
            for line in lotto_details:
                line_label_status = f"{line['label']} {line['status']}".ljust(max_label_status_length)
                line_result = line["result"]

                formatted_nums = []
                for num in line_result:
                    raw_num = re.search(r'\d+', num).group()
                    formatted_num = f"{int(raw_num):02d}"
                    if '✨' in num:
                        formatted_nums.append(f"[{formatted_num}]")
                    else:
                        formatted_nums.append(formatted_num)

                # 더 좁은 폭으로 정렬해 한 줄 내에 표시되도록 한다
                COL_WIDTH = 3
                formatted_nums = [f"{num:>{COL_WIDTH}}" for num in formatted_nums]

                formatted_line = f"{line_label_status} " + " ".join(formatted_nums)
                formatted_lines.append(formatted_line)

            formatted_results = "\n".join(formatted_lines)

            if money != "-":
                winning_message = f"{userid}님, 로또 *{round_val}회* - *{money}* 당첨 되었습니다 🎉"
            else:
                winning_message = f"{userid}님, 로또 *{round_val}회* - 다음 기회에... 🫠"

            # Send formatted results inside an HTML <pre> block and escape content
            results_block = f"<pre>{html.escape(formatted_results)}</pre>"
            # escape winning_message too to avoid accidental HTML injection
            self._send_telegram(token, chat_id, f"{results_block}\n{html.escape(winning_message)}")
        except KeyError:
            return

    def send_win720_winning_message(self, *args, **kwargs) -> None:
        """
        Handle win720 winning messages for different call signatures.

        Supported usages:
        - Telegram flow (used by controller.py in this repo):
            send_win720_winning_message(userid: str, winning: dict, token: str, chat_id: str)

        - Webhook flow (some CI/workflows expect this):
            send_win720_winning_message(winning: dict, webhook_url: str)

        This function uses safe dict access to avoid KeyError and logs
        errors instead of raising, so notification paths don't break the
        main flow.
        """
        try:
            # Telegram style: userid, winning, token, chat_id
            if len(args) == 4:
                userid, winning, token, chat_id = args
                if not isinstance(winning, dict):
                    print("[notify] send_win720_winning_message: winning must be a dict")
                    return

                round_val = winning.get("round", "알 수 없음")
                money = winning.get("money", "-")

                if money != "-":
                    message = f"{userid}님, 연금복권 *{round_val}회* - *{money}* 당첨 되었습니다 🎉"
                else:
                    message = f"{userid}님, 연금복권 - 다음 기회에... 🫠"

                self._send_telegram(token, chat_id, message)
                return

            # Webhook style: winning, webhook_url
            if len(args) == 2 and isinstance(args[0], dict) and isinstance(args[1], str):
                winning, webhook_url = args
                round_val = winning.get("round", "알 수 없음")
                money = winning.get("money", "-")

                if money != "-":
                    message = f"연금복권 *{round_val}회* - *{money}* 당첨 되었습니다 🎉"
                else:
                    message = f"연금복권 - 다음 기회에... 🫠"

                # send to discord webhook helper (no-op if webhook_url empty)
                if hasattr(self, '_send_discord_webhook'):
                    self._send_discord_webhook(webhook_url, message)
                else:
                    print("[notify] Discord webhook helper not available")
                return

            # Try kwargs fallback (explicit names)
            winning = kwargs.get('winning')
            webhook_url = kwargs.get('webhook_url')
            token = kwargs.get('token')
            chat_id = kwargs.get('chat_id')
            userid = kwargs.get('userid')

            if webhook_url and isinstance(winning, dict):
                round_val = winning.get("round", "알 수 없음")
                money = winning.get("money", "-")
                message = f"연금복권 *{round_val}회* - *{money}* 당첨 되었습니다 🎉" if money != "-" else "연금복권 - 다음 기회에... 🫠"
                if hasattr(self, '_send_discord_webhook'):
                    self._send_discord_webhook(webhook_url, message)
                else:
                    logger.info("[notify] Discord webhook helper not available")
                return

            if token and chat_id and userid and isinstance(winning, dict):
                round_val = winning.get("round", "알 수 없음")
                money = winning.get("money", "-")
                message = f"{userid}님, 연금복권 *{round_val}회* - *{money}* 당첨 되었습니다 🎉" if money != "-" else f"{userid}님, 연금복권 - 다음 기회에... 🫠"
                self._send_telegram(token, chat_id, message)
                return

            logger.error("[notify] send_win720_winning_message: unsupported call signature or missing data")
        except Exception as e:
            logger.error(f"[notify] send_win720_winning_message failed: {e}")
            return

    def _send_telegram(self, token: str, chat_id: str, message: str, escape_message: bool = False) -> None:
        if token and chat_id:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                if escape_message:
                    message = html.escape(message)
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                r = requests.post(url, json=payload, timeout=10)
                r.raise_for_status()
                logger.info("[notify] Telegram Noti. Send Complete")
            except requests.RequestException as e:
                response_body = ""
                if e.response is not None:
                    response_body = f" response={e.response.text}"
                logger.error("[notify] Telegram send failed: %s%s", e, response_body)

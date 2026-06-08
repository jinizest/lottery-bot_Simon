import html
import json
import logging
import re
import requests

import common

common.setup_logging()
logger = logging.getLogger(__name__)

class Notification:

    def build_lotto_buying_message(self, title: str, body: dict) -> str:
        result = body.get("result", {}) if isinstance(body, dict) else {}
        result_msg = self._stringify_result_msg(result.get("resultMsg", "FAILURE"))
        balance = body.get("balance", "N/A") if isinstance(body, dict) else "N/A"
        buy_round = result.get("buyRound", "알 수 없음")

        if result_msg.upper() != "SUCCESS":
            header = f"❌ {title} 실패 ({buy_round}회) :moneybag: 남은잔액 : {balance}"
            return f"{html.escape(header)}\n{html.escape('사유: ' + result_msg)}"

        lotto_number_str = self.make_lotto_number_message(result.get("arrGameChoiceNum", []))
        header = f"✅ {title} 완료 ({buy_round}회) :moneybag: 남은잔액 : {balance}"
        if not lotto_number_str:
            return html.escape(header)
        return f"{html.escape(header)}\n<pre>{html.escape(lotto_number_str)}</pre>"

    def build_win720_buying_message(self, title: str, body: dict) -> str:
        result_code = body.get("resultCode", "UNKNOWN") if isinstance(body, dict) else "UNKNOWN"
        result_msg = body.get("resultMsg", "알 수 없는 오류") if isinstance(body, dict) else "알 수 없는 오류"
        balance = body.get("balance", "N/A") if isinstance(body, dict) else "N/A"
        result_msg_text = self._stringify_result_msg(result_msg)

        win720_round = body.get("round", "알 수 없음") if isinstance(body, dict) else "알 수 없음"
        if "|" in result_msg_text:
            parts = result_msg_text.split("|")
            if len(parts) > 3 and parts[3]:
                win720_round = parts[3]

        if result_code != '100':
            header = f"❌ {title} 실패 ({win720_round}회) :moneybag: 남은잔액 : {balance}"
            return f"{html.escape(header)}\n{html.escape('사유: ' + result_msg_text)}"

        win720_number_str = self.make_win720_number_message(body.get("saleTicket", ""))
        header = f"✅ {title} 완료 ({win720_round}회) :moneybag: 남은잔액 : {balance}"
        if not win720_number_str:
            return html.escape(header)
        return f"{html.escape(header)}\n<pre>{html.escape(win720_number_str)}</pre>"

    def send_buying_summary_message(self, userid: str, purchases: list, token: str, chat_id: str) -> None:
        sections = []
        for purchase in purchases:
            lottery_type = purchase.get("lottery_type")
            title = purchase.get("title", "구매")
            body = purchase.get("response", {})
            try:
                if lottery_type == "lotto":
                    sections.append(self.build_lotto_buying_message(title, body))
                elif lottery_type == "win720":
                    sections.append(self.build_win720_buying_message(title, body))
                else:
                    sections.append(html.escape(f"❌ {title} 처리 중 오류 발생: 알 수 없는 복권 유형"))
            except Exception as e:
                sections.append(html.escape(f"❌ {title} 알림 생성 중 오류 발생: {e}"))

        if not sections:
            return

        message = f"{html.escape(userid + '님, 복권 구매 결과입니다.')}\n\n" + "\n\n".join(sections)
        self._send_telegram(token, chat_id, message)

    def send_lotto_buying_message(self, userid: str, body: dict, token: str, chat_id: str) -> None:
        try:
            message = f"{html.escape(userid + '님, 로또 구매 결과입니다.')}\n" + self.build_lotto_buying_message("로또 구매", body)
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
            message = f"{html.escape(userid + '님, 연금복권 구매 결과입니다.')}\n" + self.build_win720_buying_message("연금복권 구매", body)
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

            formatted_prefixes = []
            for line in lotto_details:
                label = line.get("label", "?")
                slot = label.split("-", 1)[-1] if "-" in label else label
                method = line.get("method", "알수없음")
                status = line.get("status", "-")
                prefix = f"{round_val} {slot} {method} ({status})"
                formatted_prefixes.append(prefix)

            formatted_lines = []
            for line, prefix in zip(lotto_details, formatted_prefixes):
                line_result = line["result"]

                formatted_nums = []
                for num in line_result:
                    raw_num = re.search(r'\d+', num).group()
                    formatted_num = f"{int(raw_num):02d}"
                    if '✨' in num:
                        formatted_nums.append(f"[{formatted_num}]")
                    else:
                        formatted_nums.append(f" {formatted_num} ")

                formatted_line = f"{prefix} " + "".join(formatted_nums)
                formatted_lines.append(formatted_line)

            formatted_results = "\n".join(formatted_lines)

            if money != "-" and money != "0 원":
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

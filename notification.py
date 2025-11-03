import re
import os, requests
import html

class Notification:
    def send_lotto_buying_message(self, userid: str, body: dict, token: str, chat_id: str) -> None:
        try:
            result = body.get("result", {})
            result_msg = result.get("resultMsg", "FAILURE").upper()
            balance = body.get("balance", "N/A")

            if result_msg != "SUCCESS":
                buy_round = result.get("buyRound", "알 수 없음")
                message = f"{userid}님, {buy_round}회 로또 구매 실패!!! :moneybag: 남은잔액 : {balance}\n사유: {result_msg}"
                self._send_telegram(token, chat_id, message)
                return

            lotto_number_str = self.make_lotto_number_message(result.get("arrGameChoiceNum", []))
            buy_round = result.get("buyRound", "알 수 없음")
            # Use HTML <pre> for code-style block (Telegram parse_mode=HTML)
            lotto_block = f"<pre>{html.escape(lotto_number_str)}</pre>"
            message = f"{html.escape(userid + '님, ' + str(buy_round) + '회 로또 구매 완료 :moneybag: 남은잔액 : ' + str(balance))}\n{lotto_block}"
            self._send_telegram(token, chat_id, message)
        except KeyError as e:
            error_message = f"{userid}님, 로또 구매 처리 중 오류 발생: {e}"
            self._send_telegram(token, chat_id, error_message)

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

            if result_code != '100':
                win720_round = result_msg.split("|")[3] if "|" in result_msg else "알 수 없음"
                message = f"{userid}님, {win720_round}회 연금복권 구매 실패!!! :moneybag: 남은잔액 : {balance}\n사유: {result_msg}"
                self._send_telegram(token, chat_id, message)
                return

            win720_round = result_msg.split("|")[3]
            win720_number_str = self.make_win720_number_message(body.get("saleTicket", ""))
            # Use HTML <pre> for code-style block (Telegram parse_mode=HTML)
            win720_block = f"<pre>{html.escape(win720_number_str)}</pre>"
            message = f"{html.escape(userid + '님, ' + str(win720_round) + '회 연금복권 구매 완료 :moneybag: 남은잔액 : ' + str(balance))}\n{win720_block}"
            self._send_telegram(token, chat_id, message)
        except KeyError as e:
            error_message = f"{userid}님, 연금복권 구매 처리 중 오류 발생: {e}"
            self._send_telegram(token, chat_id, error_message)

    def make_win720_number_message(self, win720_number: str) -> str:
        formatted_numbers = []
        for number in win720_number.split(","):
            formatted_number = f"{number[0]}조 " + " ".join(number[1:])
            formatted_numbers.append(formatted_number)
        return "\n".join(formatted_numbers)

    def send_lotto_winning_message(self, userid: str, winning: dict, token: str, chat_id: str) -> None: 
        assert type(winning) == dict
        assert type(token) == str
        assert type(chat_id) == str

        try: 
            round = winning["round"]
            money = winning["money"]

            max_label_status_length = max(len(f"{line['label']} {line['status']}") for line in winning["lotto_details"])

            formatted_lines = []
            for line in winning["lotto_details"]:
                line_label_status = f"{line['label']} {line['status']}".ljust(max_label_status_length)
                line_result = line["result"]

                formatted_nums = []
                for num in line_result:
                    raw_num = re.search(r'\d+', num).group()
                    formatted_num = f"{int(raw_num):02d}"
                    if '✨' in num:
                        formatted_nums.append(f"[{formatted_num}]")
                    else:
                        formatted_nums.append(f" {formatted_num} ")

                formatted_nums = [f"{num:>6}" for num in formatted_nums]

                formatted_line = f"{line_label_status} " + " ".join(formatted_nums)
                formatted_lines.append(formatted_line)

            formatted_results = "\n".join(formatted_lines)

            if winning['money'] != "-":
                winning_message = f"{userid}님, 로또 *{winning['round']}회* - *{winning['money']}* 당첨 되었습니다 🎉"
            else:
                winning_message = f"{userid}님, 로또 *{winning['round']}회* - 다음 기회에... 🫠"

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
                    print("[notify] Discord webhook helper not available")
                return

            if token and chat_id and userid and isinstance(winning, dict):
                round_val = winning.get("round", "알 수 없음")
                money = winning.get("money", "-")
                message = f"{userid}님, 연금복권 *{round_val}회* - *{money}* 당첨 되었습니다 🎉" if money != "-" else f"{userid}님, 연금복권 - 다음 기회에... 🫠"
                self._send_telegram(token, chat_id, message)
                return

            print("[notify] send_win720_winning_message: unsupported call signature or missing data")
        except Exception as e:
            print(f"[notify] send_win720_winning_message failed: {e}")
            return

    def _send_telegram(self, token: str, chat_id: str, message: str) -> None:
        """
        Telegram 메시지 전송:
        - TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID가 있으면 Telegram으로 보냄
        """
        if token and chat_id:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                r = requests.post(url, json=payload, timeout=10)
                r.raise_for_status()
            except Exception as e:
                print(f"[notify] Telegram send failed: {e}")

    def _send_discord_webhook(self, webhook_url: str, content: str) -> None:
        """
        Send a simple message to a Discord webhook URL using 'content' field.
        """
        if not webhook_url:
            print("[notify] _send_discord_webhook: webhook_url is empty")
            return

        try:
            payload = {"content": content}
            r = requests.post(webhook_url, json=payload, timeout=10)
            r.raise_for_status()
        except Exception as e:
            print(f"[notify] Discord webhook send failed: {e}")




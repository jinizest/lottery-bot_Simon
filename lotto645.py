import datetime
import json
import re
import time
import requests

from datetime import timedelta
from enum import Enum

from bs4 import BeautifulSoup as BS
from typing import List, Optional

import auth
import common
import logging
from HttpClient import HttpClientSingleton

common.setup_logging()
logger = logging.getLogger(__name__)

class NonJsonResponseError(Exception):
    def __init__(self, message: str, status_code: int, content_type: str, body_preview: str):
        super().__init__(message)
        self.status_code = status_code
        self.content_type = content_type
        self.body_preview = body_preview

class Lotto645Mode(Enum):
    AUTO = 1
    MANUAL = 2
    BUY = 10 
    CHECK = 20

class Lotto645:

    _REQ_HEADERS = {
        "User-Agent": auth.USER_AGENT,
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Origin": "https://ol.dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://ol.dhlottery.co.kr/olotto/game/game645.do",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
    }

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()

    def buy_lotto645(
        self, 
        auth_ctrl: auth.AuthController, 
        cnt: int, 
        mode: Lotto645Mode,
        manual_numbers: Optional[List[List[str]]] = None,
    ) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)
        assert isinstance(cnt, int) and 1 <= cnt <= 5
        assert isinstance(mode, Lotto645Mode)

        headers = self._generate_req_headers(auth_ctrl)
        
        requirements = self._getRequirements(headers)
        
        data = (
            self._generate_body_for_auto_mode(cnt, requirements)
            if mode == Lotto645Mode.AUTO
            else self._generate_body_for_manual(cnt, requirements, manual_numbers)
        )

        body = self._try_buying(headers, data)

        self._show_result(body)
        return body

    def _generate_req_headers(self, auth_ctrl: auth.AuthController) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)
        return auth_ctrl.add_auth_cred_to_headers(self._REQ_HEADERS)

    def _generate_body_for_auto_mode(self, cnt: int, requirements: list) -> dict:
        assert isinstance(cnt, int) and 1 <= cnt <= 5

        return {
            "round": requirements[3],
            "direct": requirements[0], 
            "nBuyAmount": str(1000 * cnt),
            "param": json.dumps(
                [
                    {"genType": "0", "arrGameChoiceNum": None, "alpabet": slot}
                    for slot in common.SLOTS[:cnt]
                ]
            ),
            'ROUND_DRAW_DATE' : requirements[1],
            'WAMT_PAY_TLMT_END_DT' : requirements[2],
            "gameCnt": cnt,
            "saleMdaDcd": "10"
        }

    def _generate_body_for_manual(self, cnt: int, requirements: list, manual_numbers: Optional[List[List[str]]]) -> dict:
        assert isinstance(cnt, int) and 1 <= cnt <= 5
        if not manual_numbers:
            raise ValueError("manual_numbers are required for manual mode.")

        if len(manual_numbers) != cnt:
            raise ValueError("manual_numbers count must match cnt.")

        normalized_numbers = []
        for entry in manual_numbers:
            if len(entry) != 6:
                raise ValueError("Each manual entry must contain 6 numbers.")
            normalized_entry = [f"{int(num):02d}" for num in entry]
            normalized_numbers.append(normalized_entry)

        return {
            "round": requirements[3],
            "direct": requirements[0],
            "nBuyAmount": str(1000 * cnt),
            "param": json.dumps(
                [
                    {
                        "genType": "1",
                        "arrGameChoiceNum": numbers,
                        "alpabet": slot,
                    }
                    for slot, numbers in zip(common.SLOTS[:cnt], normalized_numbers)
                ]
            ),
            "ROUND_DRAW_DATE": requirements[1],
            "WAMT_PAY_TLMT_END_DT": requirements[2],
            "gameCnt": cnt,
            "saleMdaDcd": "10",
        }

    def _getRequirements(self, headers: dict) -> list:
        headers["Referer"] = "https://ol.dhlottery.co.kr/olotto/game/game645.do"
        headers["Origin"] = "https://ol.dhlottery.co.kr"
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Sec-Fetch-Site"] = "same-origin"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Dest"] = "empty"

        logger.info("[lotto645] Fetching purchase requirements (ready socket)")
        res = self.http_client.post(
            url="https://ol.dhlottery.co.kr/olotto/game/egovUserReadySocket.json",
            headers=headers
        )

        logger.info("[lotto645] Ready socket response received")
        direct = json.loads(res.text)["ready_ip"]
        
        html_headers = self._REQ_HEADERS.copy()
        html_headers.pop("Origin", None)
        html_headers.pop("Content-Type", None)
        html_headers["Referer"] = "https://dhlottery.co.kr/common.do?method=main"
        
        if headers.get("Cookie"):
            html_headers["Cookie"] = headers.get("Cookie")
            
        logger.info("[lotto645] Fetching game page for draw dates")
        res = self.http_client.get(
            url="https://ol.dhlottery.co.kr/olotto/game/game645.do",
            headers=html_headers
        )
        logger.info("[lotto645] Game page response received")
        html = res.text
        soup = BS(html, "html5lib")
        
        try:
            draw_date = self._extract_date_value(
                soup,
                html,
                key="ROUND_DRAW_DATE",
            )
            tlmt_date = self._extract_date_value(
                soup,
                html,
                key="WAMT_PAY_TLMT_END_DT",
            )
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"[Error] Date extraction failed: {e}")
            today = datetime.datetime.today()
            days_ahead = (5 - today.weekday()) % 7
            next_saturday = today + datetime.timedelta(days=days_ahead)
            draw_date = next_saturday.strftime("%Y-%m-%d")

            limit_date = next_saturday + datetime.timedelta(days=366)
            tlmt_date = limit_date.strftime("%Y-%m-%d")

        
        cur_round_input = soup.find("input", id="curRound")
        if cur_round_input:
            current_round = cur_round_input.get('value')
        else:
            current_round = self._get_round()

        return [direct, draw_date, tlmt_date, current_round]

    def _extract_date_value(self, soup: BS, html: str, key: str) -> str:
        candidates = [
            soup.find("input", id=key),
            soup.find("input", attrs={"name": key}),
            soup.select_one(f"input#{key}"),
            soup.select_one(f"input[name='{key}']"),
        ]
        for candidate in candidates:
            if candidate:
                value = candidate.get("value")
                if value:
                    return value

        pattern = re.compile(rf"{re.escape(key)}\\s*[:=]\\s*['\"]([^'\"]+)['\"]")
        match = pattern.search(html)
        if match:
            return match.group(1)

        raise ValueError(f"{key} not found in HTML")

    def _get_round(self) -> str:
        try:
            res = self.http_client.get(
                "https://dhlottery.co.kr/common.do?method=main",
                headers=self._REQ_HEADERS
            )
            html = res.text
            soup = BS(html, "html5lib")
            found = soup.find("strong", id="lottoDrwNo")
            if found:
                last_drawn_round = int(found.text)
                return str(last_drawn_round + 1)
            else:
                 raise ValueError("lottoDrwNo not found")
        except Exception as e:
            base_date = datetime.datetime(2024, 12, 28)
            base_round = 1152
            
            today = datetime.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            
            days_ahead = (5 - today.weekday()) % 7
            next_saturday = today + datetime.timedelta(days=days_ahead)
            
            weeks = (next_saturday - base_date).days // 7
            return str(base_round + weeks)




        
    def _try_buying(self, headers: dict, data: dict) -> dict:
        assert isinstance(headers, dict)
        assert isinstance(data, dict)

        headers["Content-Type"]  = "application/x-www-form-urlencoded; charset=UTF-8"

        attempts = 5
        for attempt in range(1, attempts + 1):
            try:
                res = self.http_client.post(
                    "https://ol.dhlottery.co.kr/olotto/game/execBuy.do",
                    headers=headers,
                    data=data,
                )
                if res.encoding == 'ISO-8859-1':
                    res.encoding = 'euc-kr'

                content_type = res.headers.get("Content-Type", "")
                body_text = res.text.strip()
                if "text/html" in content_type or body_text.startswith("<"):
                    raise NonJsonResponseError(
                        "HTML response received from execBuy.do",
                        res.status_code,
                        content_type,
                        body_text[:200],
                    )

                try:
                    return json.loads(res.text)
                except UnicodeDecodeError:
                    res.encoding = 'euc-kr'
                    return json.loads(res.text)
                except json.JSONDecodeError:
                    if attempt == attempts:
                        body_preview = res.text.strip()[:200]
                        raise NonJsonResponseError(
                            "Non-JSON response received from execBuy.do",
                            res.status_code,
                            res.headers.get("Content-Type", ""),
                            body_preview,
                        )
                    logger.warning(
                        "[lotto645] Non-JSON response received "
                        f"(attempt {attempt}/{attempts}): status={res.status_code}, "
                        f"content_type={res.headers.get('Content-Type')}, "
                        f"length={len(res.text)}. Retrying in {2 ** (attempt - 1)}s."
                    )
            except requests.RequestException as exc:
                if attempt == attempts:
                    raise
                wait_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "[lotto645] Buy request failed "
                    f"(attempt {attempt}/{attempts}): {exc}. "
                    f"Retrying in {wait_seconds}s"
                )
            time.sleep(min(2, 2 ** (attempt - 1)))

    def check_winning(self, auth_ctrl: auth.AuthController) -> dict:
        assert isinstance(auth_ctrl, auth.AuthController)

        headers = self._REQ_HEADERS.copy()
        headers["Referer"] = "https://www.dhlottery.co.kr/mypage/mylotteryledger"
        headers.pop("Content-Type", None)
        headers.pop("Origin", None)

        parameters = common.get_search_date_range()

        try:
            self.http_client.get("https://www.dhlottery.co.kr/common.do?method=main", headers=headers)
        except requests.RequestException as e:
            logger.warning("[Warning] Warm-up request failed: %s", e)

        result_data = {
            "data": "no winning data"
        }

        try:
            api_url = "https://www.dhlottery.co.kr/mypage/selectMyLotteryledger.do"
            params = {
                "srchStrDt": parameters["searchStartDate"],
                "srchEndDt": parameters["searchEndDate"],
                "ltGdsCd": "LO40",
                "pageNum": 1,
                "recordCountPerPage": 10
            }

            res = self.http_client.get(api_url, params=params, headers=headers)
            
            if res.status_code != 200:
                logger.debug("DEBUG: API Status %s", res.status_code)
                pass
            
            try:
                data = res.json()
                data = data.get("data", {})
                if "list" not in data:
                    logger.debug("DEBUG_DATA_LIST_MISSING_IN_DATA")
            except (json.JSONDecodeError, AttributeError, KeyError) as e:
                logger.error(f"[Error] API JSON Parse Failed: {e}")
                data = {}

            if not data.get("list"):
                return {"data": "no winning data (empty list or API fail)"}

            latest_round = None
            latest_round_items = []
            for item in data["list"]:
                try:
                    round_value = int(item.get("ltEpsd"))
                except (TypeError, ValueError):
                    continue
                if latest_round is None or round_value > latest_round:
                    latest_round = round_value
                    latest_round_items = [item]
                elif round_value == latest_round:
                    latest_round_items.append(item)

            if not latest_round_items:
                return {"data": "no winning data (latest round missing)"}

            purchased_dates = [item.get("eltOrdrDt") for item in latest_round_items if item.get("eltOrdrDt")]
            purchased_date = max(purchased_dates) if purchased_dates else "-"
            winning_date = latest_round_items[0].get("epsdRflDt", "-")

            total_prize = 0
            for item in latest_round_items:
                amount = item.get("ltWnAmt", 0)
                try:
                    total_prize += int(amount)
                except (TypeError, ValueError):
                    continue

            money = "0 원" if total_prize == 0 else f"{total_prize:,} 원"

            result_data = {
                "round": str(latest_round),
                "money": money,
                "purchased_date": purchased_date,
                "winning_date": winning_date,
                "lotto_details": []
            }

            detail_url = "https://www.dhlottery.co.kr/mypage/lotto645TicketDetail.do"
            lotto_details = []

            for ticket_index, item in enumerate(latest_round_items, start=1):
                detail_params = {
                    "ltGdsCd": item.get("ltGdsCd"),
                    "ltEpsd": item.get("ltEpsd"),
                    "barcd": item.get("gmInfo"),
                    "ntslOrdrNo": item.get("ntslOrdrNo"),
                    "srchStrDt": params["srchStrDt"],
                    "srchEndDt": params["srchEndDt"]
                }

                try:
                    res_detail = self.http_client.get(detail_url, params=detail_params, headers=headers)
                    detail_data = res_detail.json()
                    detail_data = detail_data.get("data", detail_data)

                    ticket = detail_data.get("ticket", {})
                    if not ticket and "data" in detail_data:
                        ticket = detail_data["data"].get("ticket", {})

                    game_dtl = ticket.get("game_dtl", [])
                    win_num = ticket.get("win_num", [])

                    for i, game in enumerate(game_dtl):
                        slot_label = common.SLOTS[i] if i < len(common.SLOTS) else "?"
                        label = f"{ticket_index}-{slot_label}"

                        rank = game.get("rank", "0")
                        status = "0등" if rank == "0" else f"{rank}등"

                        method = self._determine_method(game, ticket, i)

                        nums = game.get("num", [])
                        formatted_nums = []
                        for num in nums:
                            if num in win_num:
                                formatted_nums.append(f"✨{num}")
                            else:
                                formatted_nums.append(str(num))

                        lotto_details.append({
                            "label": label,
                            "status": status,
                            "method": method,
                            "result": formatted_nums
                        })

                except (requests.RequestException, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                    logger.error(f"[Error] Detail parse error (url={detail_url}, params={detail_params}): {e}")

            result_data["lotto_details"] = lotto_details

                            
        except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
            logger.error(f"[Error] Lotto check error: {e}")
        except Exception as e:
            logger.error(f"[Error] Unexpected Lotto check error: {e}")
            raise

        return result_data

    def _determine_method(self, game: dict, ticket: dict, game_index: Optional[int] = None) -> str:
        method = self._extract_method_from_mapping(game)
        if method:
            return method

        method = self._extract_method_from_mapping(ticket)
        if method:
            return method

        method = self._extract_method_from_ticket_games(ticket, game_index)
        if method:
            return method

        return "알수없음"

    def _extract_method_from_mapping(self, source: dict) -> Optional[str]:
        if not isinstance(source, dict):
            return None

        candidate_keys = (
            "genType",
            "gen_type",
            "gen_type_cd",
            "genTypeCd",
            "genTypeCD",
            "genTyCd",
            "gnType",
            "status",
            "autoYn",
            "auto_yn",
            "auto",
            "autoType",
            "auto_type",
            "buyType",
            "buy_type",
            "buyTypeCd",
            "buy_type_cd",
            "selType",
            "sel_type",
        )

        for key in candidate_keys:
            if key in source:
                method = self._normalize_method_value(source.get(key))
                if method:
                    return method

        keyword_candidates = ("auto", "manual", "gen", "buy", "sel", "type", "yn", "status")
        for key, value in source.items():
            lower_key = str(key).lower()
            if any(keyword in lower_key for keyword in keyword_candidates):
                method = self._normalize_method_value(value)
                if method:
                    return method

        return None

    def _extract_method_from_ticket_games(self, ticket: dict, game_index: Optional[int]) -> Optional[str]:
        if not isinstance(ticket, dict):
            return None

        game_sources = (
            "game",
            "games",
            "gameList",
            "game_list",
            "gameParam",
            "game_param",
            "param",
        )

        for key in game_sources:
            if key not in ticket:
                continue
            raw_value = ticket.get(key)
            parsed_value = self._coerce_to_json(raw_value)
            if isinstance(parsed_value, list):
                if game_index is not None and 0 <= game_index < len(parsed_value):
                    method = self._normalize_method_value(parsed_value[game_index])
                    if method:
                        return method
                    if isinstance(parsed_value[game_index], dict):
                        method = self._extract_method_from_mapping(parsed_value[game_index])
                        if method:
                            return method
                for entry in parsed_value:
                    if isinstance(entry, dict):
                        method = self._extract_method_from_mapping(entry)
                        if method:
                            return method
                    else:
                        method = self._normalize_method_value(entry)
                        if method:
                            return method
            elif isinstance(parsed_value, dict):
                method = self._extract_method_from_mapping(parsed_value)
                if method:
                    return method
            else:
                method = self._normalize_method_value(parsed_value)
                if method:
                    return method

        return None

    def _coerce_to_json(self, value: object) -> object:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return value
        if not (text.startswith("{") or text.startswith("[")):
            return value
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value

    def _normalize_method_value(self, value: object) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            for inner_value in value.values():
                method = self._normalize_method_value(inner_value)
                if method:
                    return method
            for inner_key in value.keys():
                method = self._normalize_method_value(inner_key)
                if method:
                    return method
            return None
        if isinstance(value, (list, tuple, set)):
            for inner_value in value:
                method = self._normalize_method_value(inner_value)
                if method:
                    return method
            return None
        text = str(value).strip()
        if not text:
            return None
        upper = text.upper()

        auto_values = {"0", "A", "AUTO", "Y", "YES", "TRUE", "T", "자동"}
        manual_values = {"1", "M", "MANUAL", "N", "NO", "FALSE", "F", "수동"}
        semi_values = {"2", "S", "SEMI", "SEMI-AUTO", "SEMI AUTO", "SA", "SM", "반자동"}

        if upper in auto_values:
            return "자동"
        if upper in manual_values:
            return "수동"
        if upper in semi_values:
            return "반자동"

        if "AUTO" in upper or "자동" in text:
            return "자동"
        if "MANUAL" in upper or "수동" in text:
            return "수동"
        if "SEMI" in upper or "반자동" in text:
            return "반자동"
        return None
    

    def _show_result(self, body: dict) -> None:
        assert isinstance(body, dict)

        if body.get("loginYn") != "Y":
            return

        result = body.get("result", {})
        if result.get("resultMsg", "FAILURE").upper() != "SUCCESS":    
            return

import sys
from types import ModuleType, SimpleNamespace

requests_module = ModuleType("requests")
requests_module.RequestException = Exception
sys.modules.setdefault("requests", requests_module)

bs4_module = ModuleType("bs4")
bs4_module.BeautifulSoup = lambda *args, **kwargs: None
sys.modules.setdefault("bs4", bs4_module)

auth_module = ModuleType("auth")
auth_module.USER_AGENT = "test-agent"
auth_module.AuthController = object
sys.modules.setdefault("auth", auth_module)

common_module = ModuleType("common")
common_module.SLOTS = ["A", "B", "C", "D", "E"]
common_module.setup_logging = lambda: None
sys.modules.setdefault("common", common_module)

http_client_module = ModuleType("HttpClient")
http_client_module.HttpClientSingleton = SimpleNamespace(get_instance=lambda: SimpleNamespace())
sys.modules.setdefault("HttpClient", http_client_module)

sys.modules.pop("lotto645", None)
sys.modules.pop("notification", None)

from lotto645 import Lotto645
from notification import Notification


def test_bonus_number_does_not_count_as_fifth_rank_three_match():
    lotto = Lotto645.__new__(Lotto645)

    status = lotto._calculate_lotto645_status(
        ["01", "02", "03", "07", "08", "09"],
        ["01", "02", "04", "05", "06", "10"],
        "03",
    )

    assert status == "0등"


def test_bonus_number_only_creates_second_rank_with_five_main_matches():
    lotto = Lotto645.__new__(Lotto645)

    assert lotto._calculate_lotto645_status(
        ["01", "02", "03", "04", "05", "07"],
        ["01", "02", "03", "04", "05", "06"],
        "07",
    ) == "2등"
    assert lotto._calculate_lotto645_status(
        ["01", "02", "03", "04", "05", "08"],
        ["01", "02", "03", "04", "05", "06"],
        "07",
    ) == "3등"


def test_lotto_winning_message_formats_bonus_separately_from_main_matches():
    notification = Notification()
    sent_messages = []
    notification._send_telegram = lambda token, chat_id, message, escape_message=False: sent_messages.append(message)

    notification.send_lotto_winning_message("tester", {
        "round": "1234",
        "money": "0 원",
        "lotto_details": [{
            "label": "1-A",
            "method": "자동",
            "status": "0등",
            "result": ["✨01", "✨02", "⭐03", "07", "08", "09"],
        }],
    }, "token", "chat")

    assert "<b>[01]</b><b>[02]</b>[03]" in sent_messages[0]
    assert "보너스 <b>03</b>" not in sent_messages[0]

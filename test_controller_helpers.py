import sys
from types import ModuleType, SimpleNamespace


def _stub_module(name):
    module = ModuleType(name)
    sys.modules.setdefault(name, module)
    return sys.modules[name]


requests_module = _stub_module("requests")
requests_module.RequestException = Exception

for module_name in ("dotenv", "auth", "lotto645", "win720", "notification", "common"):
    _stub_module(module_name)

sys.modules["dotenv"].load_dotenv = lambda: None
sys.modules["common"].setup_logging = lambda: None
sys.modules["auth"].AuthController = object
sys.modules["auth"].SessionValidationError = type("SessionValidationError", (Exception,), {})
sys.modules["lotto645"].NonJsonResponseError = type("NonJsonResponseError", (Exception,), {})
sys.modules["lotto645"].Lotto645 = lambda: SimpleNamespace()
sys.modules["lotto645"].Lotto645Mode = {}
sys.modules["win720"].Win720 = lambda: SimpleNamespace()
sys.modules["notification"].Notification = lambda: SimpleNamespace()

http_client_module = _stub_module("HttpClient")
http_client_module.HttpClientSingleton = SimpleNamespace(get_instance=lambda: SimpleNamespace())

from controller import _estimate_win720_balance, _sanitize_purchase_results_for_log


def test_estimate_win720_balance_from_previous_balance_and_sale_count():
    response = {"resultCode": "100", "saleCnt": "5"}

    assert _estimate_win720_balance(response, "37,000원") == "32,000원 (추정)"


def test_estimate_win720_balance_skips_failed_purchase():
    response = {"resultCode": "ERROR", "saleCnt": "5"}

    assert _estimate_win720_balance(response, "37,000원") is None


def test_sanitize_purchase_results_masks_sensitive_values():
    purchases = [{
        "response": {
            "result": {
                "oltInetUserId": "002353497",
                "barCode1": "65395",
                "arrGameChoiceNum": ["A|01|05|09|23|29|413"],
            },
            "saleTicket": "1488896,2488896",
            "resultMsg": {"data": {"prchsLtNoInfoLstCn": "secret"}},
        }
    }]

    sanitized = _sanitize_purchase_results_for_log(purchases)

    assert sanitized[0]["response"]["result"]["oltInetUserId"] == "***"
    assert sanitized[0]["response"]["result"]["barCode1"] == "***"
    assert sanitized[0]["response"]["result"]["arrGameChoiceNum"] == ["A|***"]
    assert sanitized[0]["response"]["saleTicket"] == "***"
    assert sanitized[0]["response"]["resultMsg"]["data"]["prchsLtNoInfoLstCn"] == "***"

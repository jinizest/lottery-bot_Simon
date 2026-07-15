import sys
from types import ModuleType, SimpleNamespace


requests_module = ModuleType("requests")
requests_module.Response = object
requests_module.RequestException = Exception
sys.modules.setdefault("requests", requests_module)

crypto_module = ModuleType("Crypto")
public_key_module = ModuleType("Crypto.PublicKey")
rsa_module = ModuleType("Crypto.PublicKey.RSA")
rsa_module.construct = lambda *args, **kwargs: None
cipher_module = ModuleType("Crypto.Cipher")
pkcs_module = ModuleType("Crypto.Cipher.PKCS1_v1_5")
pkcs_module.new = lambda *args, **kwargs: None
sys.modules.setdefault("Crypto", crypto_module)
sys.modules.setdefault("Crypto.PublicKey", public_key_module)
sys.modules.setdefault("Crypto.PublicKey.RSA", rsa_module)
sys.modules.setdefault("Crypto.Cipher", cipher_module)
sys.modules.setdefault("Crypto.Cipher.PKCS1_v1_5", pkcs_module)

http_client_module = ModuleType("HttpClient")
http_client_module.HttpClientSingleton = SimpleNamespace(get_instance=lambda: SimpleNamespace())
sys.modules.setdefault("HttpClient", http_client_module)

from auth import AuthController


def make_response(url="https://www.dhlottery.co.kr/mypage/home", text=""):
    return SimpleNamespace(url=url, text=text)


def test_action_required_ignores_generic_authenticated_page_terms():
    controller = AuthController.__new__(AuthController)
    response = make_response(text="""
        <html>
          <body>
            <a>로그아웃</a>
            <footer>이용약관 개인정보처리방침 본인확인 안내</footer>
          </body>
        </html>
    """)

    assert controller._is_action_required_response(response) is False


def test_action_required_detects_specific_password_notice():
    controller = AuthController.__new__(AuthController)
    response = make_response(
        url="https://www.dhlottery.co.kr/userSsl.do?method=ExpryPswdNoti",
        text="비밀번호 변경 안내",
    )

    assert controller._is_action_required_response(response) is True


def test_action_required_ignores_authenticated_page_with_specific_footer_terms():
    controller = AuthController.__new__(AuthController)
    response = make_response(text="""
        <html>
          <body>
            <a href="/userSsl.do?method=logout">로그아웃</a>
            <section>약관 동의 이력과 비밀번호를 변경해 주세요 안내 링크</section>
          </body>
        </html>
    """)

    assert controller._is_action_required_response(response) is False

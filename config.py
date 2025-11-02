# config.py
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional

try:
    # 로컬 개발 시 .env 자동 로드 (배포/HA Add-on에서는 옵션)
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass

def _getenv(name: str, default: Optional[str] = None, required: bool = False) -> str:
    val = os.getenv(name, default)
    if required and (val is None or str(val).strip() == ""):
        raise RuntimeError(f"[config] Missing required environment variable: {name}")
    return "" if val is None else str(val)

@dataclass
class Settings:
    # === 여기에 .env.sample의 키를 옮겨 적으세요 ===
    # 예시(실제 키 이름은 .env.sample을 그대로 사용):
    # 인증/계정
    DHL_ID: str = field(default_factory=lambda: _getenv("DHL_ID", required=True))
    DHL_PW: str = field(default_factory=lambda: _getenv("DHL_PW", required=True))

    # 텔레그램/알림
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: _getenv("TELEGRAM_BOT_TOKEN", required=True))
    TELEGRAM_CHAT_ID: str   = field(default_factory=lambda: _getenv("TELEGRAM_CHAT_ID", required=True))

    # 동작 옵션(예시)
    DRY_RUN: str = field(default_factory=lambda: _getenv("DRY_RUN", "false"))
    TZ: str      = field(default_factory=lambda: _getenv("TZ", "Asia/Seoul"))

    # 필요 시 자유 확장: .env.sample에 존재하는 나머지 키들 추가
    # e.g. AUTO_BUY_645, AUTO_BUY_720, BUY_AMOUNT_645, BUY_AMOUNT_720, CRON 등

    # 참고: 알 수 없는 키도 받아서 함께 보관하고 싶다면 아래 사용
    extras: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, extra_keys: Iterable[str] = ()) -> "Settings":
        cfg = cls()
        cfg.extras = {k: os.getenv(k) for k in extra_keys if os.getenv(k) is not None}
        return cfg

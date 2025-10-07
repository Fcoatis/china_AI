"""Static configuration related to portfolio assets and currencies."""
from __future__ import annotations

from .models import Company, CurrencyPairConfig

DEFAULT_COMPANIES = (
    Company("Baidu", "BIDU", target_weight=15, currency="USD"),
    Company("Alibaba", "BABA", target_weight=15, currency="USD"),
    Company("Tencent", "0700.HK", target_weight=10, currency="HKD"),
    Company("SenseTime", "0020.HK", target_weight=8, currency="HKD"),
    Company("iFlytek", "002230.SZ", target_weight=7, currency="CNY"),
    Company("SMIC", "0981.HK", target_weight=12, currency="HKD"),
    Company("Cambricon", "688256.SS", target_weight=8, currency="CNY"),
    Company("Estun Automation", "002747.SZ", target_weight=10, currency="CNY"),
    Company("Siasun Robot", "300024.SZ", target_weight=7, currency="CNY"),
    Company("Hygon", "688041.SS", target_weight=8, currency="CNY"),
)

CURRENCY_TO_PAIR = {
    "USD": CurrencyPairConfig(currency="USD", symbol=None, invert=False),
    "HKD": CurrencyPairConfig(currency="HKD", symbol="USDHKD=X", invert=True),
    "CNY": CurrencyPairConfig(currency="CNY", symbol="USDCNY=X", invert=True),
}

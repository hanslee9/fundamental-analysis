"""
데이터 소스 레지스트리.

추후 유료 API를 추가할 때:
  1. data_sources/xxx_paid.py 에 DataSourceAdapter 상속 클래스 작성
  2. 아래 DATA_SOURCE_REGISTRY 에 등록만 하면 끝
     (상위 로직은 어댑터 인터페이스만 바라보므로 수정 불필요)
"""

from data_sources.kr_source import KrFreeSourceAdapter
from data_sources.us_source import UsFreeSourceAdapter

DATA_SOURCE_REGISTRY = {
    "KR": {
        "default": "kr_free",
        "adapters": {
            "kr_free": KrFreeSourceAdapter(),
            # "kr_paid_xxx": KrPaidAdapter(api_key=...),  # 추후 추가
        },
    },
    "US": {
        "default": "us_free",
        "adapters": {
            "us_free": UsFreeSourceAdapter(),
            # "us_paid_xxx": UsPaidAdapter(api_key=...),  # 추후 추가
        },
    },
}


def get_adapter(market: str, source_key: str = None):
    """시장 코드로 어댑터 인스턴스 반환. source_key 미지정 시 기본 어댑터 사용."""
    market_cfg = DATA_SOURCE_REGISTRY[market]
    key = source_key or market_cfg["default"]
    return market_cfg["adapters"][key]

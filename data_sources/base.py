"""
DataSourceAdapter — 모든 데이터 소스가 구현해야 하는 공통 인터페이스.

확장 방법 (§8-4 "추후 API 기능 추가"):
  1. 이 클래스를 상속하는 새 어댑터 작성 (예: PaidApiAdapter)
  2. 아래 5개 메서드만 구현하면 상위 로직(지표계산/리포트) 수정 없이 즉시 사용 가능
  3. config.py 의 DATA_SOURCE_REGISTRY 에 등록하면 UI에서 소스 선택 가능

주의: 어댑터는 항상 schema.py 의 표준 dataclass 로 반환해야 함
(pykrx/네이버/yfinance 등 원본 포맷 차이를 어댑터 내부에서 흡수).
"""

from abc import ABC, abstractmethod
from typing import List
from .schema import Entity, ValuationSnapshot, QuarterlyFinancials, PriceSeries


class DataSourceAdapter(ABC):
    """데이터 소스 어댑터 추상 베이스 클래스"""

    name: str = "base"          # 어댑터 식별자 (예: "kr_free", "us_free", "kr_paid_xxx")
    supported_markets: list = []

    @abstractmethod
    def search_entity(self, query: str, market: str) -> List[Entity]:
        """종목명/코드로 Entity 검색"""
        raise NotImplementedError

    @abstractmethod
    def get_valuation_snapshot(self, entity: Entity, as_of: str = None) -> ValuationSnapshot:
        """정적 분석용 스냅샷 지표 조회 (§1)"""
        raise NotImplementedError

    @abstractmethod
    def get_quarterly_financials(self, entity: Entity, n_quarters: int = 8) -> List[QuarterlyFinancials]:
        """동일분기 YoY Rolling용 분기 재무 시계열 조회 (§2)"""
        raise NotImplementedError

    @abstractmethod
    def get_price_series(self, entity: Entity, months: int = 12) -> PriceSeries:
        """MoM 가격성 데이터 조회 (§2)"""
        raise NotImplementedError

    @abstractmethod
    def get_peer_sector(self, entity: Entity) -> Entity:
        """동종 섹터 평균값을 나타내는 Entity(SECTOR) 반환 (§3 벤치마크)"""
        raise NotImplementedError

"""
KrFreeSourceAdapter — pykrx 기반 한국 시장 무료 데이터 소스.

구현 범위 (1차):
  - search_entity, get_valuation_snapshot(PER/PBR/배당수익률), get_price_series
  - pykrx는 시세 기반 지표(PER/PBR/DIV)는 제공하지만 재무제표 세부항목
    (ROE/ROA/영업이익률/부채비율 등)은 제공하지 않음
  - get_quarterly_financials 는 네이버금융 크롤링이 필요 → 2차 작업으로 별도 구현 예정
    (지금은 NotImplementedError로 명시하여 상위 로직에서 누락을 인지할 수 있게 함)
"""

from datetime import datetime, timedelta
from typing import List
import pandas as pd

from .base import DataSourceAdapter
from .schema import Entity, EntityType, Market, ValuationSnapshot, QuarterlyFinancials, PriceSeries

try:
    from pykrx import stock as pykrx_stock
except ImportError:
    pykrx_stock = None


def _latest_business_day() -> str:
    """pykrx 조회용 최근 영업일(YYYYMMDD) 추정. 주말이면 직전 금요일로 보정."""
    d = datetime.now()
    while d.weekday() >= 5:  # 5=토, 6=일
        d -= timedelta(days=1)
    return d.strftime("%Y%m%d")


class KrFreeSourceAdapter(DataSourceAdapter):
    name = "kr_free"
    supported_markets = [Market.KR]

    def search_entity(self, query: str, market: str = "KR") -> List[Entity]:
        if pykrx_stock is None:
            raise RuntimeError("pykrx가 설치되어 있지 않습니다.")

        results = []
        for mkt in ["KOSPI", "KOSDAQ"]:
            tickers = pykrx_stock.get_market_ticker_list(market=mkt)
            for t in tickers:
                nm = pykrx_stock.get_market_ticker_name(t)
                if query in nm or query == t:
                    results.append(
                        Entity(
                            code=t,
                            name=nm,
                            entity_type=EntityType.STOCK,
                            market=Market.KR,
                            currency="KRW",
                        )
                    )
        return results[:20]  # 과도한 매칭 방지

    def get_valuation_snapshot(self, entity: Entity, as_of: str = None) -> ValuationSnapshot:
        if pykrx_stock is None:
            raise RuntimeError("pykrx가 설치되어 있지 않습니다.")

        date_str = as_of.replace("-", "") if as_of else _latest_business_day()
        df = pykrx_stock.get_market_fundamental(date_str, date_str, entity.code)

        snap = ValuationSnapshot(entity=entity, as_of=date_str)
        if df is None or df.empty:
            snap.flags["_source"] = "N/A(데이터 없음)"
            return snap

        row = df.iloc[-1]
        # pykrx 컬럼: BPS, PER, PBR, EPS, DIV, DPS
        snap.per = float(row.get("PER")) if row.get("PER", 0) else None
        snap.pbr = float(row.get("PBR")) if row.get("PBR", 0) else None
        snap.dividend_yield = float(row.get("DIV")) if row.get("DIV", 0) else None

        if snap.per is None or snap.per <= 0:
            snap.flags["per"] = "N/A(적자 또는 데이터없음)"

        # ROE/ROA/영업이익률 등은 재무제표 크롤링 필요 → 2차 구현
        snap.flags["_pending"] = "ROE/ROA/영업이익률/부채비율 등은 네이버금융 연동 후 채워짐"
        return snap

    def get_quarterly_financials(self, entity: Entity, n_quarters: int = 8) -> List[QuarterlyFinancials]:
        # TODO(2차): 네이버금융 재무제표 크롤링으로 구현 예정
        raise NotImplementedError(
            "분기 재무 시계열은 아직 미구현입니다 (네이버금융 연동 2차 작업)."
        )

    def get_price_series(self, entity: Entity, months: int = 12) -> PriceSeries:
        if pykrx_stock is None:
            raise RuntimeError("pykrx가 설치되어 있지 않습니다.")

        end = datetime.now()
        start = end - timedelta(days=months * 31)
        df = pykrx_stock.get_market_ohlcv(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), entity.code
        )
        df = df.rename(
            columns={"종가": "close", "거래량": "volume", "거래대금": "trading_value"}
        )
        return PriceSeries(entity=entity, df=df)

    def get_peer_sector(self, entity: Entity) -> Entity:
        # TODO(2차): WICS 업종 조회 → GICS 매핑 테이블 적용 (§8-2)
        raise NotImplementedError("섹터 매핑은 GICS 매핑 테이블 확정 후 구현 예정 (§8-2).")

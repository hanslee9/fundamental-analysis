"""
UsFreeSourceAdapter — yfinance 기반 미국 시장 무료 데이터 소스.

yfinance는 .info / .quarterly_financials 등에서 PER/PBR/ROE/영업이익률/
분기 매출·이익까지 비교적 폭넓게 제공 → 1차에서 한국보다 구현 범위가 넓음.
"""

from typing import List
import pandas as pd

from .base import DataSourceAdapter
from .schema import Entity, EntityType, Market, ValuationSnapshot, QuarterlyFinancials, PriceSeries

try:
    import yfinance as yf
except ImportError:
    yf = None


class UsFreeSourceAdapter(DataSourceAdapter):
    name = "us_free"
    supported_markets = [Market.US]

    def search_entity(self, query: str, market: str = "US") -> List[Entity]:
        # yfinance 자체 검색 API가 불안정하여, 티커를 직접 입력받는 것을 기본 흐름으로 가정.
        # (UI 단에서 "티커 직접 입력 + 자동완성"은 2차 개선 과제)
        ticker = query.upper().strip()
        if yf is None:
            raise RuntimeError("yfinance가 설치되어 있지 않습니다.")
        info = yf.Ticker(ticker).info
        if not info or info.get("longName") is None:
            return []
        return [
            Entity(
                code=ticker,
                name=info.get("longName", ticker),
                entity_type=EntityType.STOCK,
                market=Market.US,
                currency=info.get("currency", "USD"),
                raw_sector=info.get("sector"),
            )
        ]

    def get_valuation_snapshot(self, entity: Entity, as_of: str = None) -> ValuationSnapshot:
        if yf is None:
            raise RuntimeError("yfinance가 설치되어 있지 않습니다.")

        t = yf.Ticker(entity.code)
        info = t.info

        snap = ValuationSnapshot(entity=entity, as_of=as_of or "latest")
        snap.per = info.get("trailingPE")
        snap.pbr = info.get("priceToBook")
        snap.psr = info.get("priceToSalesTrailing12Months")
        snap.dividend_yield = info.get("dividendYield")
        snap.roe = info.get("returnOnEquity")
        snap.roa = info.get("returnOnAssets")
        snap.operating_margin = info.get("operatingMargins")
        snap.net_margin = info.get("profitMargins")
        snap.debt_ratio = info.get("debtToEquity")
        snap.current_ratio = info.get("currentRatio")

        if snap.per is None or (snap.per is not None and snap.per <= 0):
            snap.flags["per"] = "N/A(적자 또는 데이터없음)"

        snap.flags["_pending"] = "EV/EBITDA, FCF/FCF Yield, 이자보상배율은 2차 계산 로직 필요"
        return snap

    def get_quarterly_financials(self, entity: Entity, n_quarters: int = 8) -> List[QuarterlyFinancials]:
        if yf is None:
            raise RuntimeError("yfinance가 설치되어 있지 않습니다.")

        t = yf.Ticker(entity.code)
        q_fin = t.quarterly_financials  # columns: 분기말일, index: 계정과목
        q_eps = None
        try:
            q_eps = t.quarterly_earnings  # 구버전 호환용, 없으면 skip
        except Exception:
            pass

        results = []
        if q_fin is None or q_fin.empty:
            return results

        for col in list(q_fin.columns)[:n_quarters]:
            quarter_label = pd.Timestamp(col).strftime("%YQ%q") if hasattr(pd.Timestamp(col), "strftime") else str(col)
            revenue = q_fin.loc["Total Revenue", col] if "Total Revenue" in q_fin.index else None
            op_income = q_fin.loc["Operating Income", col] if "Operating Income" in q_fin.index else None
            net_income = q_fin.loc["Net Income", col] if "Net Income" in q_fin.index else None

            results.append(
                QuarterlyFinancials(
                    entity=entity,
                    quarter=str(col.date()) if hasattr(col, "date") else str(col),
                    revenue=float(revenue) if revenue is not None else None,
                    operating_income=float(op_income) if op_income is not None else None,
                    net_income=float(net_income) if net_income is not None else None,
                )
            )
        return results

    def get_price_series(self, entity: Entity, months: int = 12) -> PriceSeries:
        if yf is None:
            raise RuntimeError("yfinance가 설치되어 있지 않습니다.")

        df = yf.Ticker(entity.code).history(period=f"{months}mo")
        df = df.rename(columns={"Close": "close", "Volume": "volume"})
        return PriceSeries(entity=entity, df=df[["close", "volume"]])

    def get_peer_sector(self, entity: Entity) -> Entity:
        # yfinance info의 sector는 GICS 유사 체계 → §8-2 매핑 테이블에서 표준화 예정
        raise NotImplementedError("섹터 평균 산출 로직은 GICS 매핑 확정 후 구현 예정 (§8-2).")

"""
공통 Entity / 지표 스키마 정의 (스펙 §4 Entity 통일 스키마 대응)

- Entity 4종: STOCK, SECTOR, INDEX, ETF 를 동일한 자료구조로 표현
- 모든 어댑터(pykrx, yfinance, 추후 유료 API 등)는 이 스키마로 결과를 반환해야 함
  → 상위 로직(지표계산/리포트)은 어댑터가 무엇이든 동일하게 동작
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import pandas as pd


class EntityType(str, Enum):
    STOCK = "STOCK"
    SECTOR = "SECTOR"
    INDEX = "INDEX"
    ETF = "ETF"


class Market(str, Enum):
    KR = "KR"   # 코스피/코스닥
    US = "US"


@dataclass
class Entity:
    """비교 대상 하나를 표현하는 통일 객체"""
    code: str                 # 종목코드/티커/지수코드 등 (예: "005930", "AAPL", "^GSPC")
    name: str                 # 표시명 (예: "삼성전자")
    entity_type: EntityType
    market: Market
    currency: str              # "KRW" / "USD"
    gics_sector: Optional[str] = None   # GICS 표준 섹터 (매핑 완료 후 채움, §8-2)
    raw_sector: Optional[str] = None    # 원본 섹터명 (WICS 등 매핑 전 원본 보존)


@dataclass
class ValuationSnapshot:
    """정적 분석용 스냅샷 지표 (스펙 §1)"""
    entity: Entity
    as_of: str  # 기준일 YYYY-MM-DD

    # 밸류에이션
    per: Optional[float] = None
    pbr: Optional[float] = None
    psr: Optional[float] = None
    ev_ebitda: Optional[float] = None
    dividend_yield: Optional[float] = None

    # 수익성
    roe: Optional[float] = None
    roa: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None

    # 건전성
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    interest_coverage: Optional[float] = None

    # 현금흐름
    fcf: Optional[float] = None
    fcf_yield: Optional[float] = None

    # 성장성 (연간 기준 YoY, §8-1)
    revenue_yoy: Optional[float] = None
    operating_income_yoy: Optional[float] = None
    eps_yoy: Optional[float] = None

    # 결측/이상치 플래그 (§8-7) — 키: 지표명, 값: "N/A(적자)" 등 라벨
    flags: dict = field(default_factory=dict)


@dataclass
class QuarterlyFinancials:
    """동적 분석용 분기 재무 시계열 (스펙 §2 동일분기 YoY Rolling)"""
    entity: Entity
    quarter: str          # 예: "2025Q2"
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    dividend: Optional[float] = None


@dataclass
class PriceSeries:
    """MoM(월간) 가격성 데이터 전용 (스펙 §2)"""
    entity: Entity
    df: pd.DataFrame  # index: date, columns: [close, volume, trading_value, ...]

"""
KrFreeSourceAdapter — 네이버금융 직접 크롤링 기반 한국 시장 무료 데이터 소스.

배경: pykrx가 의존하는 KRX 웹사이트 구조 변경으로 pykrx 핵심 함수들이
(get_market_ticker_list/name, get_market_ohlcv_by_date, get_market_fundamental_by_date)
'index -1 is out of bounds for axis 0 with size 0' 에러를 반환하는 미해결 이슈가 있어
(GitHub sharebook-kr/pykrx#164, #193) pykrx 대신 네이버금융을 직접 크롤링하는 방식으로 전환.

구현 범위 (1차):
  - search_entity: 네이버 종목 자동완성 API 사용 (종목코드 6자리 직접 입력도 지원)
  - get_valuation_snapshot: 네이버금융 종목 메인 페이지에서 PER/PBR 등 파싱
  - get_price_series: 네이버금융 시세 JSON API 사용
  - get_quarterly_financials: 2차 구현 예정 (재무제표 페이지 파싱 필요, 복잡도 높음)
"""

import re
import json
from datetime import datetime, timedelta
from typing import List

import requests
import pandas as pd
from bs4 import BeautifulSoup

from .base import DataSourceAdapter
from .schema import Entity, EntityType, Market, ValuationSnapshot, QuarterlyFinancials, PriceSeries

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


class KrFreeSourceAdapter(DataSourceAdapter):
    name = "kr_free"
    supported_markets = [Market.KR]

    def search_entity(self, query: str, market: str = "KR") -> List[Entity]:
        query = query.strip()

        # 종목코드(숫자 6자리)를 그대로 입력한 경우: 자동완성 없이 바로 조회
        if re.fullmatch(r"\d{6}", query):
            name = self._get_name_by_code(query)
            if name:
                return [
                    Entity(
                        code=query, name=name, entity_type=EntityType.STOCK,
                        market=Market.KR, currency="KRW",
                    )
                ]
            return []

        # 종목명 검색: 네이버 자동완성 API
        try:
            url = "https://ac.stock.naver.com/ac"
            params = {"q": query, "target": "stock", "st": "111", "r_lt": "111"}
            resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
            data = resp.json()
        except Exception:
            return []  # 자동완성 실패 시 빈 결과 (사용자에게는 코드 직접 입력 안내)

        results = []
        for group in data.get("items", []):
            for item in group:
                try:
                    code = item[0]
                    name = item[1]
                except (IndexError, TypeError):
                    continue
                if re.fullmatch(r"\d{6}", str(code)):
                    results.append(
                        Entity(
                            code=code, name=name, entity_type=EntityType.STOCK,
                            market=Market.KR, currency="KRW",
                        )
                    )
        return results[:20]

    def _get_name_by_code(self, code: str) -> str:
        try:
            url = f"https://finance.naver.com/item/main.naver?code={code}"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.select_one(".wrap_company h2 a")
            return title.text.strip() if title else code
        except Exception:
            return code

    def get_valuation_snapshot(self, entity: Entity, as_of: str = None) -> ValuationSnapshot:
        snap = ValuationSnapshot(entity=entity, as_of=as_of or datetime.now().strftime("%Y-%m-%d"))

        try:
            url = f"https://finance.naver.com/item/main.naver?code={entity.code}"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            snap.flags["_source"] = f"N/A(네트워크 오류: {e})"
            return snap

        def _parse_float(text: str):
            if not text:
                return None
            text = text.replace(",", "").strip()
            try:
                return float(text)
            except ValueError:
                return None

        per_tag = soup.select_one("#_per")
        pbr_tag = soup.select_one("#_pbr")
        snap.per = _parse_float(per_tag.text if per_tag else None)
        snap.pbr = _parse_float(pbr_tag.text if pbr_tag else None)

        # 배당수익률: 라벨 텍스트로 셀 위치 탐색 (구조 변경에 상대적으로 안전)
        div_label = soup.find(string=re.compile("배당수익률"))
        if div_label:
            parent = div_label.find_parent("tr")
            if parent:
                em = parent.find("em")
                snap.dividend_yield = _parse_float(em.text if em else None)

        if snap.per is None:
            snap.flags["per"] = "N/A(적자 또는 파싱 실패)"

        snap.flags["_pending"] = (
            "ROE/ROA/영업이익률/부채비율/EV-EBITDA/FCF 등은 재무제표 페이지 연동 후 채워짐 (2차 작업)"
        )
        return snap

    def get_quarterly_financials(self, entity: Entity, n_quarters: int = 8) -> List[QuarterlyFinancials]:
        # TODO(2차): 네이버금융 '재무제표' 탭(coinfo.naver) 파싱으로 구현 예정
        raise NotImplementedError(
            "분기 재무 시계열은 아직 미구현입니다 (네이버금융 재무제표 연동 2차 작업)."
        )

    def get_price_series(self, entity: Entity, months: int = 12) -> PriceSeries:
        end = datetime.now()
        start = end - timedelta(days=months * 31)

        try:
            url = "https://api.finance.naver.com/siseJson.naver"
            params = {
                "symbol": entity.code,
                "requestType": "1",
                "startTime": start.strftime("%Y%m%d"),
                "endTime": end.strftime("%Y%m%d"),
                "timeframe": "day",
            }
            resp = requests.get(url, params=params, headers=HEADERS, timeout=8)
            text = resp.text.strip()
            # 응답이 JS 배열 리터럴 형태([['날짜','시가',...], [...]) 이므로 정리 후 파싱
            text = text.replace("'", '"')
            rows = json.loads(text)
        except Exception:
            return PriceSeries(entity=entity, df=pd.DataFrame())

        if not rows or len(rows) < 2:
            return PriceSeries(entity=entity, df=pd.DataFrame())

        header = [h.strip() for h in rows[0]]
        data_rows = rows[1:]
        df = pd.DataFrame(data_rows, columns=header)

        col_map = {}
        for c in df.columns:
            if "날짜" in c:
                col_map[c] = "date"
            elif c == "종가":
                col_map[c] = "close"
            elif c == "거래량":
                col_map[c] = "volume"
        df = df.rename(columns=col_map)

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
            df = df.set_index("date")
        for col in ["close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return PriceSeries(entity=entity, df=df)

    def get_peer_sector(self, entity: Entity) -> Entity:
        # TODO(2차): WICS 업종 조회 → GICS 매핑 테이블 적용 (§8-2)
        raise NotImplementedError("섹터 매핑은 GICS 매핑 테이블 확정 후 구현 예정 (§8-2).")

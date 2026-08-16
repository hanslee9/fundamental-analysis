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
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            title = soup.select_one(".wrap_company h2 a")
            return title.text.strip() if title else code
        except Exception:
            return code

    def _parse_market_cap_eok(self, soup) -> float:
        """
        네이버금융 시가총액은 "374조 5,633억원"처럼 조/억이 나뉘어 표시되는 경우가 많아
        전체 텍스트에서 조/억 숫자를 각각 추출해 억원 단위로 환산 합산한다.
        (1조 = 10,000억)

        페이지 안에 "시가총액"이라는 글자가 여러 곳(동일업종 비교표 등)에 나올 수 있어,
        우선 고유 id(#_market_sum)로 먼저 찾고, 실패하면 텍스트 검색으로 대체한다.
        """
        target = soup.select_one("#_market_sum")
        if target is None:
            label = soup.find(string=re.compile("시가총액"))
            if label:
                parent = label.find_parent("tr") or label.find_parent("td")
                target = parent

        if target is None:
            return None

        text = target.get_text()

        jo_match = re.search(r"([\d,]+)\s*조", text)
        eok_match = re.search(r"조?\s*([\d,]+)\s*억", text)

        jo_val = float(jo_match.group(1).replace(",", "")) if jo_match else 0
        eok_val = float(eok_match.group(1).replace(",", "")) if eok_match else 0

        total = jo_val * 10000 + eok_val
        return total if total > 0 else None

    def _fetch_financial_ratio_table(self, code: str):
        """
        네이버금융 안정성비율(유동비율/이자보상배율 등) 표 파싱.
        WiseReport 기반 페이지라 main.naver와 별도 요청 필요.
        TODO(실데이터 검증): URL/구조가 실제와 다르면 라이브 테스트 후 조정 필요.
        반환: (table 또는 None, 디버그 메시지)
        """
        try:
            url = "https://navercomp.wisereport.co.kr/v2/company/c1030001.aspx"
            params = {"cmp_cd": code, "fin_typ": "0", "freq_typ": "Y"}
            resp = requests.get(url, params=params, headers=HEADERS, timeout=8)
            resp.encoding = "utf-8"
            status = resp.status_code
        except Exception as e:
            return None, f"요청 실패: {e}"

        if status != 200:
            return None, f"HTTP {status}"

        try:
            from io import StringIO
            tables = pd.read_html(StringIO(resp.text))
        except Exception as e:
            return None, f"표 파싱 실패(read_html): {e} (응답길이={len(resp.text)})"

        if not tables:
            return None, f"페이지에 표 자체가 없음 (응답길이={len(resp.text)})"

        for t in tables:
            try:
                first_col = t.iloc[:, 0].astype(str).tolist()
            except Exception:
                continue
            if any("유동비율" in str(x) for x in first_col):
                return t, f"성공 (표 {len(tables)}개 중 매칭됨)"

        return None, f"표 {len(tables)}개 중 '유동비율' 포함 표 없음"

    def get_valuation_snapshot(self, entity: Entity, as_of: str = None) -> ValuationSnapshot:
        snap = ValuationSnapshot(entity=entity, as_of=as_of or datetime.now().strftime("%Y-%m-%d"))

        try:
            url = f"https://finance.naver.com/item/main.naver?code={entity.code}"
            resp = requests.get(url, headers=HEADERS, timeout=5)
            resp.encoding = "utf-8"
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

        # ── "기업실적분석" 표에서 ROE/영업이익률/순이익률/부채비율 파싱 ──
        # 이 표는 pandas.read_html로 바로 DataFrame화 가능한 표준 HTML 테이블
        try:
            from io import StringIO
            tables = pd.read_html(StringIO(resp.text))
        except Exception:
            tables = []

        perf_table = None
        for t in tables:
            try:
                first_col = t.iloc[:, 0].astype(str).tolist()
            except Exception:
                continue
            if any("ROE" in str(x) for x in first_col) and any("부채비율" in str(x) for x in first_col):
                perf_table = t
                break

        if perf_table is not None:
            try:
                # 컬럼 중 "연간" 실적을 우선 선택 (분기 컬럼을 쓰면 매출 등 절대값 지표가
                # 실제보다 축소되어 PSR 등 비율 계산이 왜곡됨 — 예: 분기매출로 PSR 계산 시 약 4배 과다)
                def _col_str(c):
                    return " ".join(str(x) for x in c) if isinstance(c, tuple) else str(c)

                data_cols = [c for c in perf_table.columns if c != perf_table.columns[0]]
                actual_cols = [c for c in data_cols if "(E)" not in _col_str(c)]
                annual_actual_cols = [c for c in actual_cols if "연간" in _col_str(c)]

                if annual_actual_cols:
                    target_col = annual_actual_cols[-1]
                elif actual_cols:
                    target_col = actual_cols[-1]
                else:
                    target_col = data_cols[-1] if data_cols else None

                # 직전 연간 컬럼 (YoY 계산용) — annual_actual_cols에서 target_col 바로 이전 것
                prev_annual_col = annual_actual_cols[-2] if len(annual_actual_cols) >= 2 else None

                def _row_value(label_keyword: str, col=None):
                    col = col or target_col
                    row = perf_table[perf_table.iloc[:, 0].astype(str).str.contains(label_keyword, na=False)]
                    if row.empty or col is None:
                        return None
                    return _parse_float(str(row.iloc[0][col]))

                def _yoy(label_keyword: str):
                    """직전 연간 대비 증가율(%) 계산. 데이터 부족하면 None"""
                    if prev_annual_col is None:
                        return None
                    cur = _row_value(label_keyword, target_col)
                    prev = _row_value(label_keyword, prev_annual_col)
                    if cur is None or prev is None or prev == 0:
                        return None
                    return round((cur - prev) / abs(prev) * 100, 1)

                snap.roe = _row_value("ROE")
                snap.roa = _row_value("ROA")
                snap.operating_margin = _row_value("영업이익률")
                snap.net_margin = _row_value("순이익률")
                snap.debt_ratio = _row_value("부채비율")

                # 성장성 (§8-1) — 연간 vs 직전 연간 비교
                snap.revenue_yoy = _yoy("매출액")
                snap.operating_income_yoy = _yoy("영업이익")
                snap.eps_yoy = _yoy("EPS")

                # PSR = 시가총액 / 매출액 (매출액은 억원 단위, 시가총액도 억원 단위로 환산해서 계산)
                revenue = _row_value("매출액")
                market_cap = self._parse_market_cap_eok(soup)
                if revenue and market_cap and revenue != 0:
                    snap.psr = round(market_cap / revenue, 2)
            except Exception:
                pass  # 표 구조가 예상과 다르면 해당 필드는 N/A로 남김

        # ── 안정성비율(유동비율/이자보상배율) 파싱 ──────────
        try:
            ratio_table, ratio_debug = self._fetch_financial_ratio_table(entity.code)
            snap.flags["ratio_debug"] = ratio_debug
            if ratio_table is not None:
                def _rt_col_str(c):
                    return " ".join(str(x) for x in c) if isinstance(c, tuple) else str(c)

                rt_cols = [c for c in ratio_table.columns if c != ratio_table.columns[0]]
                rt_actual = [c for c in rt_cols if "(E)" not in _rt_col_str(c)]
                rt_annual = [c for c in rt_actual if "연간" in _rt_col_str(c)]
                rt_target = rt_annual[-1] if rt_annual else (rt_actual[-1] if rt_actual else (rt_cols[-1] if rt_cols else None))

                def _rt_value(keyword):
                    row = ratio_table[ratio_table.iloc[:, 0].astype(str).str.contains(keyword, na=False)]
                    if row.empty or rt_target is None:
                        return None
                    return _parse_float(str(row.iloc[0][rt_target]))

                snap.current_ratio = _rt_value("유동비율")
                snap.interest_coverage = _rt_value("이자보상배율")
        except Exception as e:
            snap.flags["ratio_debug"] = f"예외 발생: {e}"

        pending_items = []
        if snap.psr is None:
            pending_items.append("PSR")
        if snap.ev_ebitda is None:
            pending_items.append("EV/EBITDA")
        if snap.current_ratio is None:
            pending_items.append("유동비율")
        if snap.interest_coverage is None:
            pending_items.append("이자보상배율")
        if snap.fcf is None:
            pending_items.append("FCF/FCF Yield")
        if pending_items:
            snap.flags["_pending"] = f"{', '.join(pending_items)} 등은 2차 작업(재무제표 상세) 이후 채워짐"

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

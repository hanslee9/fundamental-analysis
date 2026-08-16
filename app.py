"""
app.py — Streamlit 진입점

1차 범위 (N=1 단일 종목 조회):
  - 시장(한국/미국) 선택 → 종목 검색 → 정적 밸류에이션 스냅샷 표시
  - 가격 추이 차트 (MoM 데이터)
  - 분기 재무 시계열(§2 YoY Rolling)은 구현된 소스(미국)만 표시,
    미구현 소스(한국)는 안내 메시지로 대체

다음 버전에서 추가 예정: 섹터/지수 벤치마크(§3), N=2 비교 모드(§6)
"""

import streamlit as st
import pandas as pd

from config import get_adapter
from data_sources.schema import EntityType, Market

#st.set_page_config(page_title="종목(지수) 펀더멘털 분석/비교", layout="wide")
#st.title("종목(지수) 펀더멘털 분석/비교")
#st.caption("N=1 단일 종목 조회 — 1차 버전 (섹터·지수 벤치마크는 추후 추가)")

st.set_page_config(page_title="종목(지수) 펀더멘털 분석/비교", layout="wide")


def check_password() -> bool:
    if st.session_state.get("authenticated", False):
        return True

    st.title("종목(지수) 펀더멘털 분석/비교")
    pw_input = st.text_input("비밀번호를 입력하세요", type="password")

    if pw_input:
        correct_pw = st.secrets.get("password", None)
        if correct_pw is None:
            st.error("SL Cloud의 Secrets에 password가 설정되지 않았습니다. (Settings → Secrets)")
            return False
        if pw_input == correct_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


if not check_password():
    st.stop()


st.title("종목(지수) 펀더멘털 분석/비교")
st.caption("N=1 단일 종목 조회 — 1차 버전 (섹터·지수 벤치마크는 추후 추가)")

# ── 사이드바: 시장 선택 & 검색 ──────────────────────────────
with st.sidebar:
    st.header("검색")
    market = st.radio("시장", options=["KR", "US"], format_func=lambda m: "한국" if m == "KR" else "미국")
    query = st.text_input(
        "종목명 또는 코드",
        placeholder="예: 삼성전자 / 005930" if market == "KR" else "예: AAPL",
    )
    search_clicked = st.button("검색", type="primary")

if "results" not in st.session_state:
    st.session_state.results = []

adapter = get_adapter(market)

if search_clicked and query:
    with st.spinner("검색 중..."):
        try:
            st.session_state.results = adapter.search_entity(query, market)
        except Exception as e:
            st.session_state.results = []
            st.error(f"검색 중 오류가 발생했습니다: {e}")

if not st.session_state.results:
    st.info("왼쪽에서 시장을 선택하고 종목명/코드를 검색하세요.")
    st.stop()

# ── 검색 결과 중 종목 선택 ─────────────────────────────────
name_options = {f"{e.name} ({e.code})": e for e in st.session_state.results}
selected_label = st.selectbox("조회할 종목", options=list(name_options.keys()))
entity = name_options[selected_label]

st.divider()
st.subheader(f"{entity.name} ({entity.code}) — 정적 분석")

# ── 정적 밸류에이션 스냅샷 ─────────────────────────────────
with st.spinner("지표 조회 중..."):
    try:
        snap = adapter.get_valuation_snapshot(entity)
    except Exception as e:
        snap = None
        st.error(f"지표 조회 중 오류가 발생했습니다: {e}")

if snap:
    metric_rows = [
        ("PER", snap.per, "flag_per"),
        ("PBR", snap.pbr, None),
        ("PSR", snap.psr, None),
        ("EV/EBITDA", snap.ev_ebitda, None),
        ("배당수익률(%)", snap.dividend_yield, None),
        ("ROE(%)", snap.roe, None),
        ("ROA(%)", snap.roa, None),
        ("영업이익률(%)", snap.operating_margin, None),
        ("순이익률(%)", snap.net_margin, None),
        ("부채비율", snap.debt_ratio, None),
        ("유동비율", snap.current_ratio, None),
    ]

    cols = st.columns(4)
    for i, (label, value, _) in enumerate(metric_rows):
        with cols[i % 4]:
            if value is None:
                display = snap.flags.get(label.split("(")[0].lower(), "N/A")
                st.metric(label, "N/A")
            else:
                st.metric(label, f"{value:.2f}")

    pending = snap.flags.get("_pending")
    if pending:
        st.caption(f"⚠ {pending}")

st.divider()

# ── 가격 추이 (MoM) ────────────────────────────────────────
st.subheader("가격 추이 (최근 12개월)")
with st.spinner("가격 데이터 조회 중..."):
    try:
        price = adapter.get_price_series(entity, months=12)
        if price.df is not None and not price.df.empty and "close" in price.df.columns:
            st.line_chart(price.df["close"])
        else:
            st.info("가격 데이터가 없습니다.")
    except Exception as e:
        st.error(f"가격 데이터 조회 중 오류가 발생했습니다: {e}")

st.divider()

# ── 분기 재무 시계열 (§2 동일분기 YoY Rolling, 구현된 소스만) ──
st.subheader("분기 재무 시계열 (동일분기 YoY)")
try:
    financials = adapter.get_quarterly_financials(entity, n_quarters=8)
    if financials:
        df = pd.DataFrame(
            [
                {
                    "분기": f.quarter,
                    "매출": f.revenue,
                    "영업이익": f.operating_income,
                    "순이익": f.net_income,
                }
                for f in financials
            ]
        )
        st.dataframe(df, use_container_width=True)
    else:
        st.info("분기 재무 데이터가 없습니다.")
except NotImplementedError as e:
    st.info(f"이 시장은 아직 분기 재무 데이터를 지원하지 않습니다. ({e})")
except Exception as e:
    st.error(f"분기 재무 조회 중 오류가 발생했습니다: {e}")

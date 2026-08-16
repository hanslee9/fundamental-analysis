"""
app.py — Streamlit 진입점

모드:
  - N=1 단일 종목: 정적 스냅샷(실데이터) + 정적/동적 벤치마크 비교(§3, 목업) + 가격추이 + 분기재무
  - N=2 비교(A vs B): §6 설계 그대로 — 정적비교/동적비교(Gap)/PER프리미엄 동행성/종합판정
    (비교 섹션은 전부 목업 데이터 — report_mock.py 의 TODO 지점을 실제 로직으로 교체 예정)
"""

import streamlit as st
import pandas as pd

from config import get_adapter
from data_sources.schema import EntityType, Market
import report_mock as mock

st.set_page_config(page_title="종목(지수) 펀더멘털 분석/비교", layout="wide")


def render_title():
    st.markdown(
        "<h1 style='font-size:1.4rem; font-weight:700; margin-bottom:0.3rem;'>"
        "종목(지수) 펀더멘털 분석/비교</h1>",
        unsafe_allow_html=True,
    )


def render_section_header(text: str):
    """중제목(주제목보다 작게)"""
    st.markdown(
        f"<h2 style='font-size:1.05rem; font-weight:700; margin:0.8rem 0 0.3rem 0;'>{text}</h2>",
        unsafe_allow_html=True,
    )


def render_subsection_header(text: str):
    """소제목(중제목보다 더 작게)"""
    st.markdown(
        f"<h3 style='font-size:0.92rem; font-weight:700; margin:0.6rem 0 0.2rem 0;'>{text}</h3>",
        unsafe_allow_html=True,
    )


# 전반적인 폰트 크기 축소 (표/메트릭/본문 텍스트)
st.markdown(
    """
    <style>
        .block-container { font-size: 0.92rem; }
        div[data-testid="stMetricValue"] { font-size: 1.05rem !important; }
        div[data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
        .stCaption, [data-testid="stCaptionContainer"] { font-size: 0.78rem !important; }
        div[data-testid="stDataFrame"] { font-size: 0.85rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


render_title()

# ── 사이드바: 모드 / 시장 / 검색 ─────────────────────────────
with st.sidebar:
    st.header("검색")
    mode = st.radio("모드", options=["N=1 단일 종목", "N=2 비교(A vs B)"])

    if mode == "N=1 단일 종목":
        market = st.radio("시장", options=["KR", "US"], format_func=lambda m: "한국" if m == "KR" else "미국")
        query = st.text_input("종목명 또는 코드", placeholder="예: 삼성전자 / 005930" if market == "KR" else "예: AAPL")
        search_clicked = st.button("검색", type="primary")
    else:
        st.caption("종목 A, B는 서로 다른 시장이어도 됩니다 (예: 한국 vs 미국)")
        st.markdown("**종목 A**")
        market_a = st.radio("시장 A", options=["KR", "US"], format_func=lambda m: "한국" if m == "KR" else "미국", key="market_a")
        query_a = st.text_input("종목 A 명 또는 코드", placeholder="예: 삼성전자 / 005930" if market_a == "KR" else "예: AAPL", key="query_a")

        st.markdown("**종목 B**")
        market_b = st.radio("시장 B", options=["KR", "US"], format_func=lambda m: "한국" if m == "KR" else "미국", key="market_b")
        query_b = st.text_input("종목 B 명 또는 코드", placeholder="예: SK하이닉스 / 000660" if market_b == "KR" else "예: MSFT", key="query_b")

        search_clicked = st.button("비교 조회", type="primary")

if mode == "N=1 단일 종목":
    adapter = get_adapter(market)


def search_one(q: str, mkt: str):
    """지정된 시장의 어댑터로 종목 하나를 검색"""
    a = get_adapter(mkt)
    try:
        results = a.search_entity(q, mkt)
        return (results[0], a) if results else (None, a)
    except Exception as e:
        st.error(f"'{q}' 검색 중 오류: {e}")
        return None, a


# ══════════════════════════════════════════════════════════════
# N=1 모드
# ══════════════════════════════════════════════════════════════
if mode == "N=1 단일 종목":
    st.caption("N=1 단일 종목 조회 — 정적/동적 벤치마크 비교(§3)는 샘플 데이터")

    if "n1_results" not in st.session_state:
        st.session_state.n1_results = []

    if search_clicked and query:
        with st.spinner("검색 중..."):
            try:
                st.session_state.n1_results = adapter.search_entity(query, market)
            except Exception as e:
                st.session_state.n1_results = []
                st.error(f"검색 중 오류가 발생했습니다: {e}")

    if not st.session_state.n1_results:
        st.info("왼쪽에서 시장을 선택하고 종목명/코드를 검색하세요.")
        st.stop()

    name_options = {f"{e.name} ({e.code})": e for e in st.session_state.n1_results}
    selected_label = st.selectbox("조회할 종목", options=list(name_options.keys()))
    entity = name_options[selected_label]

    st.divider()
    render_section_header(f"{entity.name} ({entity.code}) — 정적 분석")

    with st.spinner("지표 조회 중..."):
        try:
            snap = adapter.get_valuation_snapshot(entity)
        except Exception as e:
            snap = None
            st.error(f"지표 조회 중 오류가 발생했습니다: {e}")

    if snap:
        metric_rows = [
            ("PER", snap.per), ("PBR", snap.pbr), ("PSR", snap.psr), ("EV/EBITDA", snap.ev_ebitda),
            ("배당수익률(%)", snap.dividend_yield), ("ROE(%)", snap.roe), ("ROA(%)", snap.roa),
            ("영업이익률(%)", snap.operating_margin), ("순이익률(%)", snap.net_margin),
            ("부채비율", snap.debt_ratio), ("유동비율", snap.current_ratio),
        ]
        cols = st.columns(4)
        for i, (label, value) in enumerate(metric_rows):
            with cols[i % 4]:
                st.metric(label, f"{value:.2f}" if value is not None else "N/A")
        if snap.flags.get("_pending"):
            st.caption(f"⚠ {snap.flags['_pending']}")

    st.divider()

    # ── §3 벤치마크 3단 구조 (정적) — 목업 ──────────────────
    render_section_header("정적 벤치마크 비교 (종목 vs 섹터 vs 지수)")
    st.caption("⚠ 샘플 데이터 — 실제 섹터/지수 연동 전 레이아웃 검증용")
    static_bench = mock.get_static_benchmark_table(entity.name)
    st.dataframe(pd.DataFrame(static_bench), use_container_width=True, hide_index=True)

    st.divider()

    # ── §3 벤치마크 3단 구조 (동적) — 목업 ──────────────────
    render_section_header("동적 벤치마크 비교 (동일분기 YoY Rolling)")
    st.caption("⚠ 샘플 데이터 — 실제 섹터/지수 연동 전 레이아웃 검증용")
    dynamic_bench = mock.get_dynamic_benchmark_table(entity.name)
    st.dataframe(pd.DataFrame(dynamic_bench), use_container_width=True, hide_index=True)

    st.divider()

    # ── 가격 추이 (실데이터) ─────────────────────────────
    render_section_header("가격 추이 (최근 12개월)")
    with st.spinner("가격 데이터 조회 중..."):
        try:
            price = adapter.get_price_series(entity, months=12)
            if price.df is not None and not price.df.empty and "close" in price.df.columns:
                st.line_chart(price.df["close"].rename(entity.name))
            else:
                st.info("가격 데이터가 없습니다.")
        except Exception as e:
            st.error(f"가격 데이터 조회 중 오류가 발생했습니다: {e}")

    st.divider()

    # ── 분기 재무 시계열 (실데이터, 구현된 소스만) ────────
    render_section_header("분기 재무 시계열 (실데이터, 구현된 시장만)")
    try:
        financials = adapter.get_quarterly_financials(entity, n_quarters=8)
        if financials:
            df = pd.DataFrame([
                {"분기": f.quarter, "매출": f.revenue, "영업이익": f.operating_income, "순이익": f.net_income}
                for f in financials
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("분기 재무 데이터가 없습니다.")
    except NotImplementedError as e:
        st.info(f"이 시장은 아직 분기 재무 데이터를 지원하지 않습니다. ({e})")
    except Exception as e:
        st.error(f"분기 재무 조회 중 오류가 발생했습니다: {e}")


# ══════════════════════════════════════════════════════════════
# N=2 모드 (§6 설계)
# ══════════════════════════════════════════════════════════════
else:
    st.caption("N=2 비교(A vs B) — §6 설계 구조, 비교 데이터는 전부 샘플")

    if not (search_clicked and query_a and query_b):
        st.info("왼쪽에서 종목 A, B를 입력하고 '비교 조회'를 눌러주세요.")
        st.stop()

    with st.spinner("종목 A/B 조회 중..."):
        entity_a, adapter_a = search_one(query_a, market_a)
        entity_b, adapter_b = search_one(query_b, market_b)

    if not entity_a or not entity_b:
        st.error("종목 A 또는 B를 찾을 수 없습니다. 검색어를 확인해주세요.")
        st.stop()

    name_a, name_b = entity_a.name, entity_b.name
    render_section_header(f"{name_a} ({entity_a.code}) vs {name_b} ({entity_b.code})")

    # ── §6-1 정적 지표 비교 (17개 지표, 목업) ─────────────
    render_subsection_header("정적 지표 비교")
    st.caption("⚠ 샘플 데이터")
    static_df = pd.DataFrame(mock.get_n2_static_table(name_a, name_b))
    st.dataframe(static_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── §6-2 동적 비교: PER 시계열 (표 → 그래프 순서, 목업) ──
    render_subsection_header("동적 비교 (PER 시계열)")
    st.caption("⚠ 샘플 데이터")
    per_quarters, a_per, b_per = mock.generate_per_trend()
    per_trend_df = pd.DataFrame(mock.get_n2_per_trend_table(name_a, name_b, per_quarters, a_per, b_per))
    st.dataframe(per_trend_df, use_container_width=True, hide_index=True)

    # 표 아래에 그래프 배치: A/B PER을 서로 다른 색 선으로 표시
    chart_df = pd.DataFrame({
        f"{name_a} PER": a_per,
        f"{name_b} PER": b_per,
    })
    chart_df.index = per_quarters
    st.line_chart(chart_df)
    st.caption(f"**{name_a} PER / {name_b} PER**: 분기별 PER(배) 추이 비교")

    st.divider()

    # ── §6-3 PER 프리미엄 — 시계열 동행성 (목업) ──────────
    render_subsection_header("멀티플(PER) 프리미엄 — 시계열 동행성 참고")
    st.caption("⚠ 샘플 데이터 — 인과관계 단정 아님, 동행/디커플링 관찰용")
    earn_quarters, a_yoy, b_yoy = mock.generate_earnings_yoy()
    per_df = pd.DataFrame(mock.get_n2_per_premium_table(name_a, name_b, earn_quarters, a_yoy, b_yoy))
    st.dataframe(per_df, use_container_width=True, hide_index=True)

    st.divider()

    # ── §6-4 종합 판정 (목업) ─────────────────────────────
    render_subsection_header("종합 판정 — 투자판단 참고 프레임")
    st.caption("⚠ 샘플 데이터 — 추천이 아닌 판단재료 제공 목적")

    st.markdown("**1. 포지션 유형 분류**")
    st.dataframe(pd.DataFrame(mock.get_n2_position_types(name_a, name_b)), use_container_width=True, hide_index=True)

    st.markdown("**2. 시나리오별 시사점**")
    st.dataframe(pd.DataFrame(mock.get_n2_scenarios()), use_container_width=True, hide_index=True)

    st.markdown("**3. 판단 시 함께 볼 요인 (이 리포트 범위 밖)**")
    factors = mock.get_n2_out_of_scope_factors()
    st.markdown(" · ".join(factors))

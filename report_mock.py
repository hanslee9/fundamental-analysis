"""
report_mock.py — 리포트 출력 형식(§3/§5/§6) 검증용 목업 데이터.

실제 지표 계산 로직이 완성되기 전까지, 화면 레이아웃과 표 구조를 먼저
검증하기 위한 샘플 데이터. 각 함수 상단에 TODO로 실제 데이터 연동 지점을 표시.

지표 스키마: §8-1에서 확정한 17개 지표(카테고리 5개)를 그대로 사용.
  밸류에이션: PER, PBR, PSR, EV/EBITDA, 배당수익률
  수익성: ROE, ROA, 영업이익률, 순이익률
  건전성: 부채비율, 유동비율, 이자보상배율
  성장성: 매출YoY, 영업이익YoY, EPS YoY
  현금흐름: FCF, FCF Yield

주의: §6-2(동적 비교)는 PER 시계열, §6-3(PER 프리미엄 동행성)은 영업이익 YoY를
각각 별도 기준으로 사용한다.
"""

import random

# ── 전체 지표 스키마 (§8-1, 17개) — N=1 단일 종목 분석에 사용 ──
# 시장별로 확보 가능한 지표가 달라 값이 없으면 N/A로 표시됨.
FULL_METRIC_SCHEMA = [
    ("밸류에이션", "PER", "배"),
    ("밸류에이션", "PBR", "배"),
    ("밸류에이션", "PSR", "배"),
    ("밸류에이션", "EV/EBITDA", "배"),
    ("밸류에이션", "배당수익률", "%"),
    ("수익성", "ROE", "%"),
    ("수익성", "ROA", "%"),
    ("수익성", "영업이익률", "%"),
    ("수익성", "순이익률", "%"),
    ("건전성", "부채비율", "%"),
    ("건전성", "유보율", "%"),
    ("건전성", "유동비율", "%"),
    ("건전성", "이자보상배율", "배"),
    ("성장성", "매출YoY", "%"),
    ("성장성", "영업이익YoY", "%"),
    ("성장성", "EPS YoY", "%"),
    ("현금흐름", "FCF", ""),
    ("현금흐름", "FCF Yield", "%"),
]

# ── 공통 지표 스키마 (한국·미국 양쪽 다 실데이터 가능한 11개) — N=2 비교에 사용 ──
# ROA, EV/EBITDA, 유동비율, 이자보상배율, FCF, FCF Yield, 유보율은
# 한쪽 시장에서만 확보 가능해 N=2 크로스마켓 비교 공정성을 위해 제외.
# (더 좋은 데이터 소스를 찾으면 추후 전체 지표로 확장 예정)
COMMON_METRIC_SCHEMA = [
    ("밸류에이션", "PER", "배"),
    ("밸류에이션", "PBR", "배"),
    ("밸류에이션", "PSR", "배"),
    ("밸류에이션", "배당수익률", "%"),
    ("수익성", "ROE", "%"),
    ("수익성", "영업이익률", "%"),
    ("수익성", "순이익률", "%"),
    ("건전성", "부채비율", "%"),
    ("성장성", "매출YoY", "%"),
    ("성장성", "영업이익YoY", "%"),
    ("성장성", "EPS YoY", "%"),
]

# 이전 버전과의 호환을 위한 별칭 (다른 코드에서 METRIC_SCHEMA를 참조하는 경우 대비)
METRIC_SCHEMA = COMMON_METRIC_SCHEMA


def fmt_num(value, unit: str = "") -> str:
    """
    지표 값 표기 공통 규칙:
      - None → "N/A" (단위 없음)
      - 그 외 → 소수점 2자리 + 천단위 콤마 + 단위(%,배 등) 접미사
    """
    if value is None:
        return "N/A"
    return f"{value:,.2f}{unit}"




# ── N=1 정적 분석: 종목 vs 섹터 vs 지수 (§3) ────────────────────
def get_static_benchmark_table(entity_name: str, real_values: dict) -> list[dict]:
    """
    TODO(실데이터): 섹터평균/지수평균만 실제 계산으로 교체 (종목값은 이미 실데이터 사용 중)
    카테고리 | 지표 | 종목값(실데이터) | 섹터평균(샘플) | 지수평균(샘플) | 괴리율(vs섹터) | 괴리율(vs지수)

    real_values: {"PER": 14.4, "PBR": 12.6, ...} 형태. 값이 없는 지표는 None으로 전달하면 N/A 처리.
    위쪽 "정적 분석" 카드와 반드시 같은 종목값을 써야 두 표가 일관됨 — 절대 여기서 새로 난수 생성하지 않음.
    17개 지표 전체 사용 (N=1은 단일 종목이라 시장별로 없는 값만 N/A 처리).
    """
    result = []
    for category, name, unit in FULL_METRIC_SCHEMA:
        val = real_values.get(name)
        if val is None:
            continue  # 결측치 지표는 표에서 생략
        # 섹터/지수 평균은 아직 실제 데이터가 없어 샘플로 생성 (TODO 대상)
        sector = val * random.uniform(0.8, 1.2)
        index = val * random.uniform(0.7, 1.3)
        gap_sector = (val - sector) / sector * 100 if sector else 0
        gap_index = (val - index) / index * 100 if index else 0
        result.append({
            "카테고리": category,
            "지표": name,
            f"{entity_name}": fmt_num(val, unit),
            "섹터평균": fmt_num(sector, unit) + "(샘플)",
            "지수평균": fmt_num(index, unit) + "(샘플)",
            "괴리율(vs섹터)": f"{gap_sector:+,.2f}%",
            "괴리율(vs지수)": f"{gap_index:+,.2f}%",
        })
    return result


# ── N=1 동적 분석: 동일분기 YoY Rolling (영업이익 YoY 기준) ──────
def get_dynamic_benchmark_table(entity_name: str, n_quarters: int = 8) -> list[dict]:
    """
    TODO(실데이터): 종목/섹터/지수의 영업이익 YoY 실제 계산으로 교체
    분기 | 종목 영업이익YoY | 섹터 영업이익YoY | 지수 영업이익YoY | 상대강도
    """
    result = []
    for i in range(n_quarters, 0, -1):
        q = f"{2026 - (i // 4)}Q{4 - (i % 4) if i % 4 != 0 else 4}"
        entity_yoy = round(random.uniform(-10, 25), 1)
        sector_yoy = round(random.uniform(-8, 20), 1)
        index_yoy = round(random.uniform(-5, 15), 1)
        rel_strength = round(entity_yoy - sector_yoy, 1)
        result.append({
            "분기": q,
            f"{entity_name} 영업이익YoY": f"{entity_yoy:+,.2f}%",
            "섹터 영업이익YoY": f"{sector_yoy:+,.2f}%",
            "지수 영업이익YoY": f"{index_yoy:+,.2f}%",
            "상대강도(vs섹터)": f"{rel_strength:+,.2f}%p",
        })
    return result


# ── N=2 §6-1 정적 비교 테이블 (한국·미국 공통 11개 지표, 실데이터 사용) ──
def get_n2_static_table(name_a: str, name_b: str, real_values_a: dict, real_values_b: dict) -> list[dict]:
    """
    A/B 모두 실제 스냅샷 값을 전달받아 사용. 여기서 새로 난수 생성하지 않음.
    양쪽 시장이 공통으로 실데이터를 확보한 11개 지표만 비교 (COMMON_METRIC_SCHEMA).
    """
    result = []
    for category, name, unit in COMMON_METRIC_SCHEMA:
        a_val = real_values_a.get(name)
        b_val = real_values_b.get(name)
        if a_val is None or b_val is None:
            result.append({
                "카테고리": category, "지표": name,
                f"{name_a}": fmt_num(a_val, unit),
                f"{name_b}": fmt_num(b_val, unit),
                "차이(A-B)": "N/A", "배수(A/B)": "N/A", "우위": "N/A",
            })
            continue
        diff = a_val - b_val
        ratio = a_val / b_val if b_val else None
        winner = name_a if a_val > b_val else name_b
        result.append({
            "카테고리": category,
            "지표": name,
            f"{name_a}": fmt_num(a_val, unit),
            f"{name_b}": fmt_num(b_val, unit),
            "차이(A-B)": f"{diff:+,.2f}",
            "배수(A/B)": f"{ratio:,.2f}" if ratio is not None else "N/A",
            "우위": winner,
        })
    return result


# ── N=2 §6-2 동적 비교: PER 시계열 (분기별 PER 값 자체 비교) ──────
def generate_per_trend(n_quarters: int = 8):
    """
    TODO(실데이터): 분기별 실제 PER 값 계산으로 교체.
    반환: (quarters, a_per_list, b_per_list) — 전부 과거→최근 순서
    """
    quarters, a_list, b_list = [], [], []
    for i in range(n_quarters, 0, -1):
        q = f"{2026 - (i // 4)}Q{4 - (i % 4) if i % 4 != 0 else 4}"
        quarters.append(q)
        a_list.append(round(random.uniform(5, 30), 1))
        b_list.append(round(random.uniform(5, 30), 1))
    return quarters, a_list, b_list


def get_n2_per_trend_table(name_a: str, name_b: str, quarters, a_per, b_per) -> list[dict]:
    """TODO(실데이터): generate_per_trend를 실제 분기별 PER 계산으로 교체"""
    result = []
    for q, a, b in zip(quarters, a_per, b_per):
        gap = round(a - b, 1)
        result.append({
            "분기": q,
            f"{name_a} PER(배)": a,
            f"{name_b} PER(배)": b,
            "Gap(A-B, 배)": f"{gap:+,.2f}",
        })
    return result


# ── N=2 §6-3 PER 프리미엄 — 시계열 동행성 (영업이익 YoY 별도 생성) ──
def generate_earnings_yoy(n_quarters: int = 8):
    """TODO(실데이터): 실제 영업이익 YoY 계산으로 교체. 반환: (quarters, a_yoy, b_yoy)"""
    quarters, a_list, b_list = [], [], []
    for i in range(n_quarters, 0, -1):
        q = f"{2026 - (i // 4)}Q{4 - (i % 4) if i % 4 != 0 else 4}"
        quarters.append(q)
        a_list.append(round(random.uniform(-10, 25), 1))
        b_list.append(round(random.uniform(-10, 25), 1))
    return quarters, a_list, b_list


def get_n2_per_premium_table(name_a: str, name_b: str, quarters, a_yoy, b_yoy) -> list[dict]:
    """TODO(실데이터): PER 밴드 위치는 실제 밸류에이션 밴드 계산으로 교체."""
    bands = ["매우저평가", "저평가", "평균", "비싼 편", "매우비쌈"]
    result = []
    for q, a, b in zip(quarters, a_yoy, b_yoy):
        a_band = random.choice(bands)
        b_band = random.choice(bands)
        same_direction = (a > 0) == (b > 0)
        note = "동행" if same_direction else "디커플링"
        result.append({
            "분기": q,
            f"{name_a} PER밴드": a_band,
            f"{name_a} 영업이익YoY": f"{a:+,.2f}%",
            f"{name_b} PER밴드": b_band,
            f"{name_b} 영업이익YoY": f"{b:+,.2f}%",
            "비고(동행성)": note,
        })
    return result


# ── N=2 §6-4 종합 판정 ────────────────────────────────────────
def get_n2_position_types(name_a: str, name_b: str) -> list[dict]:
    """TODO(실데이터): 실제 지표 기반 유형 분류 로직으로 교체"""
    return [
        {"종목": name_a, "유형": "가치형", "강점": "저평가 구간, 안정적 배당", "유의점": "성장률 둔화 가능성"},
        {"종목": name_b, "유형": "품질/프리미엄형", "강점": "높은 ROE, 이익 성장 지속", "유의점": "밸류에이션 부담"},
    ]


def get_n2_scenarios() -> list[dict]:
    """TODO(실데이터): Gap 추세 등 실제 조건 기반으로 시나리오 문구 생성"""
    return [
        {"조건": "Gap 축소 지속 시", "시사점": "두 종목 간 펀더멘털 수렴 가능성 — 밸류에이션 격차 축소 관찰 필요"},
        {"조건": "Gap 확대 지속 시", "시사점": "펀더멘털 차별화 심화 — 프리미엄/디스카운트 정당성 재검토 필요"},
        {"조건": "디커플링 해소 시", "시사점": "PER과 이익 성장의 동행성 회복 — 밸류에이션 정상화 국면 가능"},
    ]


def get_n2_out_of_scope_factors() -> list[str]:
    """스펙 §6-4에 명시된 '리포트 범위 밖' 고정 안내 항목"""
    return ["환율 전망", "금리/통화정책", "지수 내 편중도", "지정학 리스크"]

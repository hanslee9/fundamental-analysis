"""
report_mock.py — 리포트 출력 형식(§3/§5/§6) 검증용 목업 데이터.

실제 지표 계산 로직(밸류에이션 밴드, YoY Rolling, 섹터/지수 벤치마크 등)이
완성되기 전까지, 화면 레이아웃과 표 구조를 먼저 검증하기 위한 샘플 데이터.

각 함수 상단에 TODO로 실제 데이터 연동 지점을 표시해둠.
나중에 이 파일의 함수들을 실제 계산 로직으로 교체하면 됨(UI 코드는 수정 불필요).
"""

import random


# ── N=1 정적 분석: 종목 vs 섹터 vs 지수 (§3) ────────────────────
def get_static_benchmark_table(entity_name: str) -> list[dict]:
    """
    TODO(실데이터): 종목 스냅샷 + 섹터평균 + 지수평균 실제 계산으로 교체
    지표 | 종목값 | 섹터평균 | 지수평균 | 괴리율(vs섹터) | 괴리율(vs지수)
    """
    rows = [
        {"지표": "PER", "unit": "배"},
        {"지표": "PBR", "unit": "배"},
        {"지표": "ROE", "unit": "%"},
        {"지표": "영업이익률", "unit": "%"},
        {"지표": "부채비율", "unit": "%"},
    ]
    result = []
    for r in rows:
        val = round(random.uniform(5, 30), 1)
        sector = round(val * random.uniform(0.8, 1.2), 1)
        index = round(val * random.uniform(0.7, 1.3), 1)
        gap_sector = round((val - sector) / sector * 100, 1)
        gap_index = round((val - index) / index * 100, 1)
        result.append({
            "지표": r["지표"],
            f"{entity_name}": f"{val}{r['unit']}",
            "섹터평균": f"{sector}{r['unit']}",
            "지수평균": f"{index}{r['unit']}",
            "괴리율(vs섹터)": f"{gap_sector:+.1f}%",
            "괴리율(vs지수)": f"{gap_index:+.1f}%",
        })
    return result


# ── N=1 동적 분석: 동일분기 YoY Rolling (§2) ────────────────────
def get_dynamic_benchmark_table(entity_name: str, n_quarters: int = 8) -> list[dict]:
    """
    TODO(실데이터): 종목/섹터/지수의 동일분기 YoY 실제 계산으로 교체
    분기 | 종목변화 | 섹터변화 | 지수변화 | 상대강도
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
            f"{entity_name} YoY": f"{entity_yoy:+.1f}%",
            "섹터 YoY": f"{sector_yoy:+.1f}%",
            "지수 YoY": f"{index_yoy:+.1f}%",
            "상대강도(vs섹터)": f"{rel_strength:+.1f}%p",
        })
    return result


# ── N=2 §6-1 정적 비교 테이블 ────────────────────────────────
def get_n2_static_table(name_a: str, name_b: str) -> list[dict]:
    """TODO(실데이터): A/B 실제 스냅샷 비교로 교체"""
    metrics = ["PER(배)", "PBR(배)", "ROE(%)", "영업이익률(%)", "배당수익률(%)"]
    result = []
    for m in metrics:
        a_val = round(random.uniform(5, 30), 1)
        b_val = round(random.uniform(5, 30), 1)
        diff = round(a_val - b_val, 1)
        ratio = round(a_val / b_val, 2) if b_val else None
        winner = name_a if a_val > b_val else name_b
        result.append({
            "지표": m,
            f"{name_a}": a_val,
            f"{name_b}": b_val,
            "차이(A-B)": f"{diff:+.1f}",
            "배수(A/B)": ratio,
            "우위": winner,
        })
    return result


# ── N=2 §6-2 동적 비교 테이블 (YoY Rolling + Gap) ────────────────
def get_n2_dynamic_table(name_a: str, name_b: str, n_quarters: int = 8) -> list[dict]:
    """TODO(실데이터): A/B 동일분기 YoY 실제 계산으로 교체"""
    result = []
    for i in range(n_quarters, 0, -1):
        q = f"{2026 - (i // 4)}Q{4 - (i % 4) if i % 4 != 0 else 4}"
        a_yoy = round(random.uniform(-10, 25), 1)
        b_yoy = round(random.uniform(-10, 25), 1)
        gap = round(a_yoy - b_yoy, 1)
        result.append({
            "분기": q,
            f"{name_a} YoY": f"{a_yoy:+.1f}%",
            f"{name_b} YoY": f"{b_yoy:+.1f}%",
            "Gap(A-B)": f"{gap:+.1f}%p",
        })
    return result


# ── N=2 §6-3 PER 프리미엄 — 시계열 동행성 ─────────────────────
def get_n2_per_premium_table(name_a: str, name_b: str, n_quarters: int = 8) -> list[dict]:
    """TODO(실데이터): PER 밴드 위치 + 이익 YoY 실제 계산으로 교체"""
    bands = ["매우저평가", "저평가", "평균", "비싼 편", "매우비쌈"]
    result = []
    for i in range(n_quarters, 0, -1):
        q = f"{2026 - (i // 4)}Q{4 - (i % 4) if i % 4 != 0 else 4}"
        a_band = random.choice(bands)
        b_band = random.choice(bands)
        a_earn = round(random.uniform(-10, 25), 1)
        b_earn = round(random.uniform(-10, 25), 1)
        same_direction = (a_earn > 0) == (b_earn > 0)
        note = "동행" if same_direction else "디커플링"
        result.append({
            "분기": q,
            f"{name_a} PER밴드": a_band,
            f"{name_a} 이익YoY": f"{a_earn:+.1f}%",
            f"{name_b} PER밴드": b_band,
            f"{name_b} 이익YoY": f"{b_earn:+.1f}%",
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

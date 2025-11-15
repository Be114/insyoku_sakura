from __future__ import annotations

import difflib
import unicodedata
from collections import Counter, deque
from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from .models import AnalysisResponse, AnalysisSignals, AnalyzeRequest, FraudKeywordCount, PlaceData, PlaceReview

FRAUD_KEYWORDS = [
    "詐欺",
    "ぼったくり",
    "騙された",
    "騙し",
    "不正請求",
    "法外",
    "高すぎる",
    "scam",
    "rip-off",
    "rip off",
    "fraud",
]
BUSINESS_SUFFIXES = ["株式会社", "（株）", "(株)", "有限会社", "合同会社", "inc", "co.,ltd", "co., ltd", "llc"]


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def analyze_place(place: PlaceData, request: AnalyzeRequest) -> AnalysisResponse:
    reviews = place.reviews
    total_reviews = len(reviews)

    short_5_ratio = _calc_short_5_ratio(reviews, total_reviews)
    burst_7day_ratio = _calc_burst_ratio(reviews, total_reviews)
    rating_diff = _calc_rating_diff(place.rating, request.tabelog_rating)
    tabelog_missing = request.tabelog_rating is None and request.tabelog_review_count is None
    name_similarity = _calc_name_similarity(place.name, request.tabelog_name)
    low_star_ratio = _calc_low_star_ratio(reviews, total_reviews)
    fraud_keyword_ratio, fraud_keyword_detail = _calc_fraud_stats(reviews, total_reviews)

    signals = AnalysisSignals(
        total_reviews=total_reviews,
        short_5_ratio=short_5_ratio,
        burst_7day_ratio=burst_7day_ratio,
        rating_diff_google_minus_tabelog=rating_diff,
        tabelog_missing=tabelog_missing,
        name_similarity_google_vs_tabelog=name_similarity,
        low_star_ratio=low_star_ratio,
        fraud_keyword_ratio=fraud_keyword_ratio,
    )

    sakura_score = _calc_sakura_score(
        short_5_ratio,
        burst_7day_ratio,
        rating_diff,
        tabelog_missing,
        name_similarity,
        low_star_ratio,
        total_reviews,
    )
    fraud_score = _calc_fraud_score(fraud_keyword_ratio, low_star_ratio, total_reviews)
    risk_label = _calc_risk_label(sakura_score, fraud_score)
    comments = _build_comments(short_5_ratio, burst_7day_ratio, rating_diff, tabelog_missing, fraud_keyword_ratio)

    return AnalysisResponse(
        sakura_score=sakura_score,
        fraud_score=fraud_score,
        risk_label=risk_label,
        signals=signals,
        fraud_keywords=[FraudKeywordCount(keyword=k, count=c) for k, c in fraud_keyword_detail.items() if c > 0],
        comments_ja=comments,
    )


def _normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "").strip()


def _calc_short_5_ratio(reviews: Sequence[PlaceReview], total: int) -> float:
    if total == 0:
        return 0.0
    short_count = 0
    for review in reviews:
        if review.rating == 5:
            normalized = _normalize_text(review.text)
            if len(normalized) <= 15:
                short_count += 1
    return short_count / total


def _calc_burst_ratio(reviews: Sequence[PlaceReview], total: int) -> float:
    if total < 5:
        return 0.0
    times = sorted((review.created_at for review in reviews if isinstance(review.created_at, datetime)))
    if not times:
        return 0.0
    window = deque()
    max_in_window = 0
    for ts in times:
        window.append(ts)
        cutoff = ts - timedelta(days=7)
        while window and window[0] < cutoff:
            window.popleft()
        max_in_window = max(max_in_window, len(window))
    return max_in_window / total if total else 0.0


def _calc_rating_diff(google_rating: Optional[float], tabelog_rating: Optional[float]) -> Optional[float]:
    if google_rating is None or tabelog_rating is None:
        return None
    return google_rating - tabelog_rating


def _calc_name_similarity(google_name: str, tabelog_name: Optional[str]) -> Optional[float]:
    if not tabelog_name:
        return None
    g_norm = _normalize_name(google_name)
    t_norm = _normalize_name(tabelog_name)
    if not g_norm or not t_norm:
        return None
    return difflib.SequenceMatcher(a=g_norm, b=t_norm).ratio()


def _normalize_name(name: str) -> str:
    text = _normalize_text(name).lower()
    for suffix in BUSINESS_SUFFIXES:
        text = text.replace(suffix, "")
    return text.replace(" ", "")


def _calc_low_star_ratio(reviews: Sequence[PlaceReview], total: int) -> float:
    if total == 0:
        return 0.0
    low = sum(1 for review in reviews if review.rating in (1, 2))
    return low / total


def _calc_fraud_stats(reviews: Sequence[PlaceReview], total: int) -> tuple[float, Counter[str]]:
    if total == 0:
        return 0.0, Counter()
    keyword_counts: Counter[str] = Counter()
    hit_reviews = 0
    for review in reviews:
        normalized = _normalize_text(review.text).lower()
        matched_any = False
        for keyword in FRAUD_KEYWORDS:
            if keyword.lower() in normalized:
                keyword_counts[keyword] += 1
                matched_any = True
        if matched_any:
            hit_reviews += 1
    return hit_reviews / total, keyword_counts


def _calc_sakura_score(
    short_5_ratio: float,
    burst_7day_ratio: float,
    rating_diff: Optional[float],
    tabelog_missing: bool,
    name_similarity: Optional[float],
    low_star_ratio: float,
    total_reviews: int,
) -> int:
    sakura = 0.0
    sakura += clamp(short_5_ratio * 100, 0, 40)
    sakura += clamp(burst_7day_ratio * 100, 0, 25)
    if rating_diff is not None and rating_diff > 0:
        sakura += clamp(rating_diff * 15, 0, 20)
    if tabelog_missing:
        sakura += 5
    if name_similarity is not None:
        sakura += clamp((1.0 - name_similarity) * 20, 0, 15)
    if total_reviews >= 20 and low_star_ratio < 0.1:
        sakura += 10
    return int(min(100, round(sakura)))


def _calc_fraud_score(fraud_keyword_ratio: float, low_star_ratio: float, total_reviews: int) -> int:
    fraud = 0.0
    fraud += clamp(fraud_keyword_ratio * 200, 0, 90)
    if total_reviews >= 10 and low_star_ratio >= 0.3:
        fraud += 10
    return int(min(100, round(fraud)))


def _calc_risk_label(sakura_score: int, fraud_score: int) -> str:
    if sakura_score >= 70 or fraud_score >= 70:
        return "high"
    if sakura_score >= 40 or fraud_score >= 40:
        return "medium"
    return "low"


def _build_comments(
    short_5_ratio: float,
    burst_7day_ratio: float,
    rating_diff: Optional[float],
    tabelog_missing: bool,
    fraud_keyword_ratio: float,
) -> List[str]:
    comments: List[str] = []
    if short_5_ratio >= 0.4:
        comments.append(f"短文または無言の★5口コミが全体の{int(short_5_ratio * 100)}%を占めています。")
    if burst_7day_ratio >= 0.4:
        comments.append("短期間に口コミが集中して投稿されており、不自然な増え方です。")
    if rating_diff is not None and rating_diff >= 0.5:
        comments.append("Googleと食べログの評価差が大きく、Google側の評価が高めに出ています。")
    if tabelog_missing:
        comments.append("食べログに情報がほとんどなく、Googleのみ口コミが集まっています。")
    if fraud_keyword_ratio > 0:
        comments.append("『詐欺』『ぼったくり』などのネガティブなキーワードを含む口コミが複数見つかりました。")
    return comments

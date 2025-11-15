from datetime import datetime, timedelta, timezone

from app.models import AnalyzeRequest, PlaceData, PlaceReview
from app.scoring import analyze_place

BASE_URL = "https://www.google.com/maps/place/foo?query_place_id=ChIJ12345"


def _make_review(rating: int, days_ago: int, text: str = "レビュー") -> PlaceReview:
    return PlaceReview(
        rating=rating,
        text=text,
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


def test_low_risk_store():
    reviews = [
        _make_review(5, 120, "雰囲気が良くスタッフも丁寧でまた行きたいです"),
        _make_review(4, 90, "また来たい"),
        _make_review(3, 60, "普通"),
        _make_review(2, 30, "少し高い"),
        _make_review(1, 15, "残念"),
    ]
    place = PlaceData(place_id="ChIJlow", name="居酒屋サンプル", rating=3.6, user_ratings_total=5, reviews=reviews)
    request = AnalyzeRequest(
        google_maps_url=BASE_URL,
        tabelog_rating=3.5,
        tabelog_review_count=10,
        tabelog_name="居酒屋サンプル",
    )
    result = analyze_place(place, request)
    assert 0 <= result.sakura_score <= 100
    assert 0 <= result.fraud_score <= 100
    assert result.risk_label == "low"


def test_sakura_like_store_triggers_high_risk():
    reviews = []
    for i in range(25):
        reviews.append(_make_review(5, i // 5, "最高"))
    place = PlaceData(place_id="ChIJsakura", name="焼肉きらびやか", rating=4.8, user_ratings_total=25, reviews=reviews)
    request = AnalyzeRequest(
        google_maps_url=BASE_URL,
        tabelog_rating=3.2,
        tabelog_review_count=30,
        tabelog_name="焼肉きらびやか",
    )
    result = analyze_place(place, request)
    assert result.sakura_score >= 70
    assert result.risk_label in {"medium", "high"}


def test_fraud_like_store_triggers_high_fraud():
    reviews = []
    for i in range(15):
        text = "詐欺に近いぼったくりでした" if i % 2 == 0 else "rip-off experience"
        reviews.append(_make_review(1 if i % 2 == 0 else 2, days_ago=i, text=text))
    place = PlaceData(place_id="ChIJfraud", name="ラーメンXYZ", rating=2.1, user_ratings_total=15, reviews=reviews)
    request = AnalyzeRequest(
        google_maps_url=BASE_URL,
        tabelog_rating=2.0,
        tabelog_review_count=2,
        tabelog_name="ラーメンxyz",
    )
    result = analyze_place(place, request)
    assert result.fraud_score >= 70
    assert result.risk_label == "high"

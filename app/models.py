from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    google_maps_url: HttpUrl
    tabelog_rating: Optional[float] = Field(default=None, ge=0, le=5)
    tabelog_review_count: Optional[int] = Field(default=None, ge=0)
    tabelog_name: Optional[str] = None


class PlaceReview(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: str = ""
    created_at: datetime


class PlaceData(BaseModel):
    place_id: str
    name: str
    rating: Optional[float]
    user_ratings_total: Optional[int]
    reviews: List[PlaceReview] = Field(default_factory=list)


class FraudKeywordCount(BaseModel):
    keyword: str
    count: int


class AnalysisSignals(BaseModel):
    total_reviews: int
    short_5_ratio: float
    burst_7day_ratio: float
    rating_diff_google_minus_tabelog: Optional[float]
    tabelog_missing: bool
    name_similarity_google_vs_tabelog: Optional[float]
    low_star_ratio: float
    fraud_keyword_ratio: float


class AnalysisResponse(BaseModel):
    sakura_score: int = Field(ge=0, le=100)
    fraud_score: int = Field(ge=0, le=100)
    risk_label: str
    signals: AnalysisSignals
    fraud_keywords: List[FraudKeywordCount]
    comments_ja: List[str]

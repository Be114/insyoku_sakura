from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .models import PlaceData, PlaceReview

GOOGLE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GOOGLE_V1_BASE = "https://places.googleapis.com/v1"
PLACE_ID_PATTERN = re.compile(r"!1s([^!]+)!")


def parse_place_id(url: str) -> Optional[str]:
    """Extract place_id from various Google Maps URLs."""

    def _extract(parsed_url) -> Optional[str]:
        query = parse_qs(parsed_url.query)
        for key in ("query_place_id", "place_id", "placeid"):
            if key in query and query[key]:
                return query[key][0]
        link_param = query.get("link")
        if link_param:
            try:
                inner = urlparse(link_param[0])
                pid = _extract(inner)
                if pid:
                    return pid
            except ValueError:
                pass
        if "/maps/place/" in parsed_url.path:
            candidate_source = parsed_url.path + parsed_url.fragment
            match = PLACE_ID_PATTERN.search(candidate_source)
            if match:
                possible = unquote(match.group(1))
                if possible:
                    return possible
        return None

    try:
        parsed = urlparse(url)
    except ValueError:
        return None

    place_id = _extract(parsed)
    if place_id:
        return unicodedata.normalize("NFKC", place_id)
    return None


class GooglePlacesClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0) -> None:
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY is not set")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def fetch_place(self, place_id: str, max_reviews: int = 100) -> PlaceData:
        details = await self._fetch_details(place_id)
        reviews = await self._fetch_reviews(place_id, max_reviews)
        if not reviews and details.get("reviews"):
            reviews = [self._convert_details_review(r) for r in details["reviews"] if r]
        return PlaceData(
            place_id=place_id,
            name=details.get("name", ""),
            rating=details.get("rating"),
            user_ratings_total=details.get("user_ratings_total"),
            reviews=[r for r in reviews if r is not None],
        )

    async def _fetch_details(self, place_id: str) -> dict:
        params = {
            "place_id": place_id,
            "key": self.api_key,
            "fields": "place_id,name,rating,user_ratings_total,reviews",
            "reviews_no_translations": "true",
            "reviews_sort": "newest",
        }
        resp = await self._client.get(GOOGLE_DETAILS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            message = data.get("error_message", data.get("status", "UNKNOWN_ERROR"))
            raise RuntimeError(f"Google Places Details error: {message}")
        return data.get("result", {})

    async def _fetch_reviews(self, place_id: str, max_reviews: int) -> List[PlaceReview]:
        collected: List[PlaceReview] = []
        if max_reviews <= 0:
            return collected
        url = f"{GOOGLE_V1_BASE}/places/{place_id}/reviews"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "reviews.rating,reviews.text,reviews.originalText,reviews.publishTime",
        }
        params = {
            "pageSize": 10,
            "orderBy": "NEWEST",
        }
        next_page_token: Optional[str] = None
        while len(collected) < max_reviews:
            if next_page_token:
                params["pageToken"] = next_page_token
            resp = await self._client.get(url, headers=headers, params=params)
            if resp.status_code == 404:
                break
            resp.raise_for_status()
            payload = resp.json()
            reviews = payload.get("reviews", [])
            for review in reviews:
                converted = self._convert_v1_review(review)
                if converted:
                    collected.append(converted)
                    if len(collected) >= max_reviews:
                        break
            next_page_token = payload.get("nextPageToken")
            if not next_page_token:
                break
        return collected

    def _convert_v1_review(self, review: dict) -> Optional[PlaceReview]:
        rating = review.get("rating")
        if rating is None:
            return None
        text = (
            (review.get("originalText") or {}).get("text")
            or (review.get("text") or {}).get("text")
            or ""
        )
        publish_time = review.get("publishTime")
        created_at = datetime.now(timezone.utc)
        if publish_time:
            try:
                created_at = datetime.fromisoformat(publish_time.replace("Z", "+00:00"))
            except ValueError:
                pass
        return PlaceReview(rating=int(rating), text=text, created_at=created_at)

    def _convert_details_review(self, review: dict) -> Optional[PlaceReview]:
        rating = review.get("rating")
        if rating is None:
            return None
        text = review.get("text", "")
        timestamp = review.get("time")
        created_at = datetime.now(timezone.utc)
        if timestamp:
            try:
                created_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            except (ValueError, TypeError):
                pass
        return PlaceReview(rating=int(rating), text=text, created_at=created_at)

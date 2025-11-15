from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException

from .google_client import GooglePlacesClient, parse_place_id
from .models import AnalysisResponse, AnalyzeRequest
from .scoring import analyze_place

logger = logging.getLogger(__name__)
_client: Optional[GooglePlacesClient] = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _client
    try:
        _client = GooglePlacesClient()
    except ValueError as exc:
        logger.error("Google client initialization failed: %s", exc)
        raise
    try:
        yield
    finally:
        if _client is not None:
            await _client.close()
            _client = None


app = FastAPI(title="SagiCheck API", version="0.1.0", lifespan=lifespan)


def get_google_client() -> GooglePlacesClient:
    if _client is None:
        raise HTTPException(status_code=500, detail="Google Places クライアントが初期化されていません。")
    return _client


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalyzeRequest, client: GooglePlacesClient = Depends(get_google_client)) -> AnalysisResponse:
    place_id = parse_place_id(str(request.google_maps_url))
    if not place_id:
        raise HTTPException(status_code=400, detail="Google Maps URLからplace_idを抽出できませんでした。")

    try:
        place = await client.fetch_place(place_id)
    except httpx.HTTPStatusError as exc:
        logger.warning("Google API status error: %s", exc)
        raise HTTPException(status_code=502, detail="Google Places APIへのリクエストに失敗しました。")
    except Exception as exc:
        logger.exception("Google API error: %s", exc)
        raise HTTPException(status_code=502, detail="Google Places APIの処理中にエラーが発生しました。")

    return analyze_place(place, request)

from __future__ import annotations

import logging
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException

from .google_client import GooglePlacesClient, parse_place_id
from .models import AnalysisResponse, AnalyzeRequest
from .scoring import analyze_place

logger = logging.getLogger(__name__)
app = FastAPI(title="SagiCheck API", version="0.1.0")
_client: Optional[GooglePlacesClient] = None


def get_google_client() -> GooglePlacesClient:
    global _client
    if _client is None:
        try:
            _client = GooglePlacesClient()
        except ValueError as exc:
            logger.error("Google client initialization failed: %s", exc)
            raise HTTPException(status_code=500, detail=str(exc))
    return _client


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _client is not None:
        await _client.close()


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

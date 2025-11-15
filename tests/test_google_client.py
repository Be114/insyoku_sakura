from urllib.parse import quote

from app.google_client import parse_place_id


def test_parse_place_id_with_standard_url():
    url = "https://www.google.com/maps/place/?q=place_id:ChIJ123&query_place_id=ChIJ123"
    assert parse_place_id(url) == "ChIJ123"


def test_parse_place_id_with_link_param():
    inner = "https://www.google.com/maps/place/foo/data=!3m1!1sChIJ987"
    url = f"https://maps.app.goo.gl/?link={quote(inner, safe='')}"
    assert parse_place_id(url) == "ChIJ987"


def test_parse_place_id_without_id_returns_none():
    url = "https://www.google.com/maps/place/東京都庁"
    assert parse_place_id(url) is None


def test_parse_place_id_with_empty_or_none_returns_none():
    assert parse_place_id("") is None
    assert parse_place_id(None) is None

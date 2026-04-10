from tools.video.stock_sources import all_sources
from tools.video.stock_sources.unsplash import _build_download_url, _orientation_for_unsplash
from tools.video.stock_sources.wikimedia import _build_search_query, _kind_from_mime, _meta_value


def test_stock_source_autodiscovery_includes_new_sources():
    names = {source.name for source in all_sources()}
    assert "wikimedia" in names
    assert "unsplash" in names


def test_wikimedia_search_query_respects_kind():
    assert _build_search_query("rain city", "video").startswith("filetype:video")
    assert _build_search_query("rain city", "image").startswith("filetype:image")
    assert _build_search_query("rain city", "any") == "rain city"


def test_wikimedia_kind_and_metadata_helpers():
    assert _kind_from_mime("video/webm", "File:foo.webm") == "video"
    assert _kind_from_mime("image/jpeg", "File:foo.jpg") == "image"
    assert _meta_value({"Artist": {"value": "<a href='/wiki/User:Test'>Test User</a>"}}, "Artist") == "Test User"


def test_unsplash_helpers_preserve_query_params():
    assert _orientation_for_unsplash("square") == "squarish"
    url = _build_download_url("https://images.unsplash.com/photo-123?ixid=abc", 1920)
    assert "ixid=abc" in url
    assert "w=1920" in url
    assert "fm=jpg" in url

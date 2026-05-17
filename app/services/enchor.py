import asyncio
import httpx
from app.config import settings
from app.models.schemas import SearchResult, TrackInfo
from app.services import matcher

_API_URL = "https://api.enchor.us"
_FILES_URL = "https://files.enchor.us"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.enchor.us",
    "Referer": "https://www.enchor.us/",
}

_DIFF_FIELDS = {
    "diff_guitar": "Guitar",
    "diff_guitar_coop": "Co-op Guitar",
    "diff_rhythm": "Rhythm",
    "diff_bass": "Bass",
    "diff_drums": "Drums",
    "diff_keys": "Keys",
    "diff_vocals": "Vocals",
    "diff_guitarghl": "Guitar (GHL)",
    "diff_bassghl": "Bass (GHL)",
}


def _parse_instruments(song: dict) -> list[str]:
    return [label for field, label in _DIFF_FIELDS.items() if (song.get(field) or 0) >= 0]


async def search_song(track: TrackInfo) -> list[SearchResult]:
    query = f"{track.artist} {track.name}"
    body = {
        "search": query,
        "page": 1,
        "instrument": None,
        "difficulty": None,
        "drumType": None,
        "drumsReviewed": False,
        "source": "website",
    }
    results: list[SearchResult] = []

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5, read=10, write=5, pool=5)) as client:
            resp = await client.post(f"{_API_URL}/search", json=body, headers=_HEADERS)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 5))
                await asyncio.sleep(retry_after)
                resp = await client.post(f"{_API_URL}/search", json=body, headers=_HEADERS)
            # API devuelve 201 para resultados exitosos
            if resp.status_code not in (200, 201):
                return results
            data = resp.json()
    except Exception:
        return results

    for song in data.get("data", []):
        name = song.get("name", "")
        artist = song.get("artist", "")
        md5 = song.get("md5", "")
        charter = song.get("charter", "")

        score = matcher.score_match(track.artist, track.name, artist, name)
        if score < settings.fuzzy_match_threshold:
            continue

        download_url = f"{_FILES_URL}/{md5}.sng" if md5 else None

        results.append(
            SearchResult(
                track=track,
                found=True,
                source="enchor",
                chart_name=name,
                charter=charter,
                download_url=download_url,
                file_type="sng" if download_url else None,
                instruments=_parse_instruments(song),
                match_score=score,
                youtube_only=False,
            )
        )

    results.sort(key=lambda r: r.match_score, reverse=True)
    return results[: settings.max_results_per_song]


async def search_songs(tracks: list[TrackInfo]):
    """Generador async: yield el mejor SearchResult por canción con rate limit."""
    for track in tracks:
        results = await search_song(track)
        if results:
            yield results[0]
        else:
            yield SearchResult(track=track, found=False)
        await asyncio.sleep(settings.enchor_rate_limit_delay)

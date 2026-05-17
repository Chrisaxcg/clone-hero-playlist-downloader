import asyncio
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from app.config import settings
from app.models.schemas import SearchResult, TrackInfo
from app.services import matcher

_BASE = "https://rhythmverse.co/songfiles/game/clonehero"


async def search_song(track: TrackInfo) -> SearchResult | None:
    query = urllib.parse.quote(f"{track.artist} {track.name}")
    url = f"{_BASE}?search={query}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5, read=10, write=5, pool=5), follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text
    except Exception:
        return None

    try:
        soup = BeautifulSoup(html, "html.parser")
        # Buscar tarjetas de canciones — la estructura puede cambiar
        cards = (
            soup.select(".song-card")
            or soup.select(".songfile-card")
            or soup.select("[class*='song']")
        )

        best: SearchResult | None = None
        best_score = settings.fuzzy_match_threshold - 1

        for card in cards[:10]:
            title_el = card.select_one(".song-title, .title, h3, h4")
            artist_el = card.select_one(".song-artist, .artist, .subtitle")
            link_el = card.select_one("a[href*='download'], a[href*='.zip'], a[href*='.sng']")

            if not title_el:
                continue

            r_title = title_el.get_text(strip=True)
            r_artist = artist_el.get_text(strip=True) if artist_el else ""
            download_url = link_el["href"] if link_el else None

            score = matcher.score_match(track.artist, track.name, r_artist, r_title)
            if score > best_score:
                best_score = score
                file_type = None
                if download_url:
                    file_type = "sng" if ".sng" in download_url else "zip"
                best = SearchResult(
                    track=track,
                    found=True,
                    source="rhythmverse",
                    chart_name=r_title,
                    charter=None,
                    download_url=download_url,
                    file_type=file_type,
                    match_score=score,
                )

        return best
    except Exception:
        return None


async def search_songs(tracks: list[TrackInfo]):
    for track in tracks:
        result = await search_song(track)
        yield result
        await asyncio.sleep(settings.rhythmverse_rate_limit_delay)

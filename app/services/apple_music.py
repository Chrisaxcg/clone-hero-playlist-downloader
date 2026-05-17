import json
import re
import httpx
# html.parser is stdlib; no lxml needed
from app.config import settings
from app.models.schemas import TrackInfo

_EMBED_BASE = "https://embed.music.apple.com"
_API_BASE = "https://api.music.apple.com/v1"


def _extract_playlist_id(url: str) -> tuple[str, str]:
    """Retorna (storefront, playlist_id) desde un link de Apple Music."""
    match = re.search(r"music\.apple\.com/([a-z]{2})/playlist/[^/]+/(pl\.[^?#]+)", url)
    if not match:
        raise ValueError(f"URL de Apple Music no válida: {url}")
    return match.group(1), match.group(2)


async def _scrape_embed(storefront: str, playlist_id: str) -> tuple[str, list[TrackInfo]]:
    embed_url = f"{_EMBED_BASE}/{storefront}/playlist/{playlist_id}"
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(embed_url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text

    # Buscar JSON-LD embebido
    ld_match = re.search(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not ld_match:
        raise ValueError("No se encontró JSON-LD en el embed de Apple Music.")

    data = json.loads(ld_match.group(1))
    playlist_name = data.get("name", "Playlist")
    raw_tracks = data.get("track", [])

    tracks: list[TrackInfo] = []
    for t in raw_tracks:
        name = t.get("name", "")
        artist = t.get("byArtist", {}).get("name", "Desconocido")
        if name:
            tracks.append(TrackInfo(name=name, artist=artist))

    return playlist_name, tracks


async def _api_fetch(storefront: str, playlist_id: str) -> tuple[str, list[TrackInfo]]:
    token = settings.apple_music_developer_token
    headers = {"Authorization": f"Bearer {token}", "Music-User-Token": ""}
    tracks: list[TrackInfo] = []
    playlist_name = ""

    async with httpx.AsyncClient(timeout=20) as client:
        url = f"{_API_BASE}/catalog/{storefront}/playlists/{playlist_id}"
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        attrs = data.get("data", [{}])[0].get("attributes", {})
        playlist_name = attrs.get("name", "Playlist")

        tracks_url = f"{_API_BASE}/catalog/{storefront}/playlists/{playlist_id}/tracks"
        while tracks_url:
            r = await client.get(tracks_url, headers=headers, params={"limit": 100})
            r.raise_for_status()
            d = r.json()
            for item in d.get("data", []):
                a = item.get("attributes", {})
                tracks.append(TrackInfo(name=a.get("name", ""), artist=a.get("artistName", "")))
            tracks_url = d.get("next")

    return playlist_name, tracks


async def get_playlist_tracks(url: str) -> tuple[str, list[TrackInfo]]:
    storefront, playlist_id = _extract_playlist_id(url)

    if settings.apple_music_developer_token:
        return await _api_fetch(storefront, playlist_id)

    # Fallback: scraping del embed público (no requiere credenciales)
    return await _scrape_embed(storefront, playlist_id)

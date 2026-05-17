import json
import re
import httpx
from bs4 import BeautifulSoup
from app.models.schemas import TrackInfo

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _extract_playlist_id(url: str) -> str:
    match = re.search(r"spotify\.com/(?:[a-z]{2}/)?playlist/([A-Za-z0-9]+)", url)
    if not match:
        raise ValueError(f"URL de Spotify no válida: {url}")
    return match.group(1)


async def _fetch_embed_data(playlist_id: str) -> tuple[str, list[TrackInfo], str | None]:
    """
    Lee el embed de Spotify y extrae: nombre de playlist, tracks iniciales (hasta 100)
    y el accessToken anónimo para paginar si hay más canciones.
    """
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(embed_url, headers=_HEADERS)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})

    if not script_tag:
        raise ValueError(
            "No se pudo leer la playlist de Spotify. "
            "Asegúrate de que sea pública y que el link sea válido."
        )

    data = json.loads(script_tag.string)
    entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    playlist_name = entity.get("name") or entity.get("title") or "Playlist"

    tracks: list[TrackInfo] = []
    for item in entity.get("trackList", []):
        title = item.get("title", "").strip()
        subtitle = item.get("subtitle", "").strip()
        if title:
            artist = subtitle.split(",")[0].strip() if subtitle else "Desconocido"
            tracks.append(TrackInfo(name=title, artist=artist))

    # Token anónimo para paginación via API
    access_token: str | None = (
        data["props"]["pageProps"]["state"]
        .get("settings", {})
        .get("session", {})
        .get("accessToken")
    )

    return playlist_name, tracks, access_token


async def _fetch_remaining_tracks(
    playlist_id: str, access_token: str, offset: int
) -> list[TrackInfo]:
    """Pagina el resto de tracks usando el token anónimo del embed."""
    tracks: list[TrackInfo] = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    params = {
        "fields": "next,items(track(name,artists,type))",
        "limit": 100,
        "offset": offset,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        while url:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code in (400, 401, 403, 429):
                break  # token anónimo sin permisos; detener paginación silenciosamente
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                track = item.get("track")
                if not track or track.get("type") == "episode":
                    continue
                artists = track.get("artists", [])
                artist = artists[0]["name"] if artists else "Desconocido"
                tracks.append(TrackInfo(name=track["name"], artist=artist))

            url = data.get("next")
            params = {}  # la URL 'next' ya incluye parámetros

    return tracks


async def get_playlist_tracks(url: str) -> tuple[str, list[TrackInfo]]:
    playlist_id = _extract_playlist_id(url)

    name, tracks, token = await _fetch_embed_data(playlist_id)

    if not tracks:
        raise ValueError(
            "No se encontraron canciones. Verifica que la playlist sea pública y tenga canciones."
        )

    # Si hay token y puede haber más de 100 tracks, paginar el resto
    if token and len(tracks) == 100:
        extra = await _fetch_remaining_tracks(playlist_id, token, offset=100)
        tracks.extend(extra)

    return name, tracks

import asyncio
import io
import os
import re
import zipfile
import httpx
from app.models.schemas import SearchResult

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')
_MAX_CONCURRENT = asyncio.Semaphore(4)   # max 4 ZIPs simultáneos


def _safe_name(name: str) -> str:
    return _UNSAFE_CHARS.sub("_", name).strip()[:80]


async def build_zip(
    results: list[SearchResult],
    on_progress=None,          # callback(done, total, song_label)
) -> bytes:
    """
    Descarga los .sng seleccionados y los empaqueta en un ZIP en memoria.
    Retorna los bytes del ZIP.
    """
    downloadable = [r for r in results if r.found and r.download_url]
    total = len(downloadable)
    buf = io.BytesIO()

    async with _MAX_CONCURRENT:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                for i, result in enumerate(downloadable, 1):
                    artist = _safe_name(result.track.artist)
                    song = _safe_name(result.track.name)
                    arcname = f"{artist}/{song}.sng"

                    try:
                        resp = await client.get(result.download_url)
                        resp.raise_for_status()
                        zf.writestr(arcname, resp.content)
                    except Exception as exc:
                        # Añadir un archivo de texto de error en lugar del .sng
                        zf.writestr(
                            f"{artist}/{song}_ERROR.txt",
                            f"Error al descargar: {exc}\nURL: {result.download_url}",
                        )

                    if on_progress:
                        await on_progress(i, total, f"{result.track.artist} - {result.track.name}")

    buf.seek(0)
    return buf.read()

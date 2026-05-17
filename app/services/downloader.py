import re
import httpx
import zipstream

from app.models.schemas import SearchResult

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')


def _safe_name(name: str) -> str:
    return _UNSAFE_CHARS.sub("_", name).strip()[:80]


def _download_source(url: str):
    """
    Generador SÍNCRONO: descarga un archivo .sng y lo cede en un chunk.
    zipstream lo llama de forma lazy — solo cuando toca ese archivo en el ZIP.
    Así el pico de RAM es ~1 archivo a la vez (~20 MB) sin importar el tamaño
    de la playlist.
    """
    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=5, read=30, write=5, pool=5),
            follow_redirects=True,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            yield resp.content
    except Exception:
        return  # Archivo omitido en silencio si falla la descarga


def build_zip_stream(results: list[SearchResult]):
    """
    Generador SÍNCRONO que produce el ZIP en streaming byte a byte.

    Ventajas frente al enfoque anterior (BytesIO):
      - Sin acumular todo en RAM — pico de ~20 MB sin importar cuántas canciones.
      - El browser empieza a recibir datos inmediatamente.
      - FastAPI/Starlette corre generadores síncronos en un threadpool,
        por lo que no bloquea el event loop de asyncio.

    Estructura del ZIP:
      Artista/
        Cancion.sng   ← Clone Hero los lee nativamente, sin extraer nada
    """
    downloadable = [r for r in results if r.found and r.download_url]

    zs = zipstream.ZipStream(compress_type=zipstream.ZIP_STORED)

    for result in downloadable:
        artist  = _safe_name(result.track.artist)
        song    = _safe_name(result.track.name)
        arcname = f"{artist}/{song}.sng"
        zs.add(_download_source(result.download_url), arcname)

    yield from zs

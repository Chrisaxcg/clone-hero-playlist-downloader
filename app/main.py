import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.models.schemas import DownloadRequest, PlaylistResponse, SearchResult
from app.services import apple_music, enchor, rhythmverse, spotify
from app.services.downloader import build_zip_stream

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Rate limiter (por IP)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Clone Hero Playlist Downloader", docs_url=None, redoc_url=None)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ---- Playlist ---------------------------------------------------------------

class PlaylistRequest(BaseModel):
    url: str


@app.post("/api/playlist", response_model=PlaylistResponse)
@limiter.limit("30/minute")
async def read_playlist(req: PlaylistRequest, request: Request):
    url = req.url.strip()
    try:
        if "spotify.com" in url:
            name, tracks = await spotify.get_playlist_tracks(url)
            source = "spotify"
        elif "music.apple.com" in url:
            name, tracks = await apple_music.get_playlist_tracks(url)
            source = "apple_music"
        else:
            raise HTTPException(
                status_code=400,
                detail="URL no reconocida. Usa un link de Spotify o Apple Music.",
            )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer la playlist: {e}")

    return PlaylistResponse(
        tracks=tracks, playlist_name=name, total=len(tracks), source=source
    )


# ---- Search (NDJSON streaming) -----------------------------------------------

class SearchRequest(BaseModel):
    tracks: list[dict]


@app.post("/api/search")
@limiter.limit("20/minute")
async def search_tracks(req: SearchRequest, request: Request):
    from app.models.schemas import TrackInfo

    tracks = [TrackInfo(**t) for t in req.tracks]

    async def generate():
        async for result in enchor.search_songs(tracks):
            if not result.found:
                rv = await rhythmverse.search_song(result.track)
                if rv:
                    result = rv
            yield json.dumps(result.model_dump()) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ---- Download (ZIP streaming al browser) ------------------------------------

@app.post("/api/download")
@limiter.limit("6/minute")
async def download_zip(req: DownloadRequest, request: Request):
    downloadable = [r for r in req.results if r.found and r.download_url]
    if not downloadable:
        raise HTTPException(status_code=400, detail="No hay canciones con link de descarga.")
    if len(downloadable) > 60:
        raise HTTPException(
            status_code=400,
            detail="Máximo 60 canciones por descarga. Selecciona menos canciones.",
        )

    return StreamingResponse(
        build_zip_stream(downloadable),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="clone_hero_songs.zip"'},
    )

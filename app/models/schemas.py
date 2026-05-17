from pydantic import BaseModel


class TrackInfo(BaseModel):
    name: str
    artist: str
    album: str | None = None


class SearchResult(BaseModel):
    track: TrackInfo
    found: bool
    source: str | None = None          # "enchor" | "rhythmverse" | None
    chart_name: str | None = None
    charter: str | None = None
    download_url: str | None = None
    file_type: str | None = None       # "zip" | "sng"
    has_video: bool = False
    instruments: list[str] = []
    match_score: int = 0
    youtube_only: bool = False         # no se puede descargar automáticamente


class PlaylistResponse(BaseModel):
    tracks: list[TrackInfo]
    playlist_name: str
    total: int
    source: str                        # "spotify" | "apple_music"


class DownloadRequest(BaseModel):
    results: list[SearchResult]


class DownloadSession(BaseModel):
    session_id: str


class WSMessage(BaseModel):
    type: str                          # "progress" | "complete" | "error" | "log" | "done"
    song: str | None = None
    percent: int | None = None
    message: str | None = None
    bytes_downloaded: int | None = None
    total_bytes: int | None = None

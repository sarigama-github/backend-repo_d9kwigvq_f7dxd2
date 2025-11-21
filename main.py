import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
from urllib.parse import quote

from database import db, create_document, get_documents

app = FastAPI(title="Trending Lyrics ID API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Models
# -------------------------------
class SongOut(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    cover: Optional[str] = None
    apple_url: Optional[str] = None
    preview_url: Optional[str] = None
    lyrics_available: bool = False
    rank: Optional[int] = None

class LyricsOut(BaseModel):
    title: str
    artist: str
    lyrics: Optional[str]
    source: Optional[str] = None


# -------------------------------
# Helpers
# -------------------------------

def _normalize_song_key(title: str, artist: str) -> Dict[str, str]:
    key = {
        "title": title.strip(),
        "artist": artist.strip(),
    }
    return key


def _upsert_song(doc: Dict[str, Any]):
    if db is None:
        return
    key = {"title": doc.get("title"), "artist": doc.get("artist")}
    db["song"].update_one(key, {"$set": {**doc}}, upsert=True)


def _get_song_from_db(title: str, artist: str) -> Optional[Dict[str, Any]]:
    if db is None:
        return None
    return db["song"].find_one(_normalize_song_key(title, artist))


# Lyrics provider chain

def fetch_lyrics_from_providers(artist: str, title: str) -> (Optional[str], Optional[str]):
    # 1) Lyrist (community API)
    try:
        url = f"https://lyrist.vercel.app/api/{quote(artist)}/{quote(title)}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            lyr = data.get("lyrics") or data.get("lyric")
            if lyr:
                return lyr, "lyrist"
    except Exception:
        pass

    # 2) lyrics.ovh
    try:
        url = f"https://api.lyrics.ovh/v1/{quote(artist)}/{quote(title)}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            lyr = data.get("lyrics")
            if lyr:
                return lyr, "lyrics.ovh"
    except Exception:
        pass

    # 3) Some Random API by title (may return different artist)
    try:
        url = f"https://some-random-api.com/lyrics?title={quote(artist + ' ' + title)}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            lyr = data.get("lyrics")
            if lyr:
                return lyr, "some-random-api"
    except Exception:
        pass

    return None, None


# -------------------------------
# Routes
# -------------------------------
@app.get("/")
def read_root():
    return {"message": "Trending Lyrics Indonesia API ready"}


@app.get("/api/trending", response_model=List[SongOut])
def get_trending(country: str = Query("id", description="ISO country code"), limit: int = Query(20, ge=1, le=100)):
    """Fetch top songs from Apple iTunes RSS for given country (default Indonesia)"""
    rss_url = f"https://itunes.apple.com/{country}/rss/topsongs/limit={limit}/json"
    try:
        res = requests.get(rss_url, timeout=12)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gagal mengambil chart: {str(e)}")

    entries = data.get("feed", {}).get("entry", [])
    out: List[SongOut] = []

    for idx, e in enumerate(entries, start=1):
        title = (e.get("im:name", {}) or {}).get("label")
        artist = (e.get("im:artist", {}) or {}).get("label")
        album = (e.get("im:collection", {}).get("im:name", {}) or {}).get("label") if e.get("im:collection") else None
        images = e.get("im:image", [])
        cover = images[-1]["label"] if images else None
        # Apple URL
        link = e.get("link")
        apple_url = None
        if isinstance(link, list):
            for l in link:
                if isinstance(l, dict) and l.get("attributes", {}).get("href"):
                    apple_url = l["attributes"]["href"]
                    break
        elif isinstance(link, dict):
            apple_url = link.get("attributes", {}).get("href")

        # Preview (if available)
        preview_url = None
        if "link" in e and isinstance(e["link"], list):
            for l in e["link"]:
                attrs = l.get("attributes", {})
                if attrs.get("type", "").startswith("audio/") and attrs.get("href"):
                    preview_url = attrs.get("href")
                    break

        # Persist/update DB
        doc = {
            "title": title,
            "artist": artist,
            "album": album,
            "cover": cover,
            "apple_url": apple_url,
            "preview_url": preview_url,
            "rank": idx,
            "country": country,
            "tags": ["trending"],
        }
        _upsert_song(doc)

        # check if lyrics available in DB
        lyr_available = False
        if db is not None:
            existing = _get_song_from_db(title, artist)
            if existing and (existing.get("lyrics") and len(existing.get("lyrics")) > 30):
                lyr_available = True

        out.append(SongOut(
            title=title,
            artist=artist,
            album=album,
            cover=cover,
            apple_url=apple_url,
            preview_url=preview_url,
            lyrics_available=lyr_available,
            rank=idx
        ))

    return out


@app.get("/api/lyrics", response_model=LyricsOut)
def get_lyrics(artist: str = Query(...), title: str = Query(...)):
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist dan judul wajib diisi")

    # If cached in DB, return
    doc = _get_song_from_db(title, artist)
    if doc and doc.get("lyrics"):
        return LyricsOut(title=title, artist=artist, lyrics=doc.get("lyrics"), source=doc.get("lyrics_source"))

    lyrics, source = fetch_lyrics_from_providers(artist, title)
    if not lyrics:
        raise HTTPException(status_code=404, detail="Lirik tidak ditemukan secara otomatis")

    # update DB cache
    if db is not None:
        _upsert_song({
            "title": title,
            "artist": artist,
            "lyrics": lyrics,
            "lyrics_source": source,
        })

    return LyricsOut(title=title, artist=artist, lyrics=lyrics, source=source)


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db as _db
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = _db.name if hasattr(_db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = _db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

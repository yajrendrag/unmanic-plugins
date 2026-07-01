"""
Look up a video file's original language(s) via the TMDB API.

Filenames are parsed with parse-torrent-title (PTN) == 2.8.2.

pip install parse-torrent-title==2.8.2 requests
"""

import re
import unicodedata

import requests
import PTN
import logging

TMDB_BASE = "https://api.themoviedb.org/3"
logger = logging.getLogger("Unmanic.Plugin.keep_stream_by_language.tmdb_lib")

def _normalize(text):
    """Casefold + strip accents + collapse non-alphanumerics for comparison."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def _result_titles(result, media_type):
    """All comparable title strings TMDB returns for a search result."""
    if media_type == "movie":
        return [result.get("title"), result.get("original_title")]
    return [result.get("name"), result.get("original_name")]


def _result_year(result, media_type):
    """Release/first-air year of a TMDB search result, or None."""
    date = result.get("release_date") if media_type == "movie" else result.get("first_air_date")
    if date and len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return None


def get_original_language(filename, tmdb_api_key, tmdb_read_access_token, media_type=None):
    """
    Return the original language(s) of a movie/TV video file as a list of
    ISO 639-1 codes (e.g. ["ko"]), or [] if it can't be determined.

    Parameters
    ----------
    filename : str
        Video file name (release-style names work best, e.g.
        "Parasite.2019.KOREAN.1080p.BluRay.x264-GROUP.mkv").
    tmdb_api_key : str
        TMDB v3 API key. Used as a fallback if no read-access token is given.
    tmdb_read_access_token : str
        TMDB v4 read-access token (Bearer). Preferred when provided.
    media_type : {"movie", "tv", None}, optional
        Force the search type. If None, it is inferred from the filename
        (presence of a season/episode => "tv", otherwise "movie").

    Returns
    -------
    list[str]
        A list of original-language codes (normally one element), or an empty
        list on any failure. On failure a short reason is printed.
    """
    # --- 1. Parse the filename -------------------------------------------------
    info = PTN.parse(filename)
    title = info.get("title")
    if not title:
        logger.info(f"[original-language] could not parse a title from: {filename!r}")
        return []
    year = info.get("year")

    # --- 2. Decide movie vs. tv -----------------------------------------------
    if media_type is None:
        media_type = "tv" if ("season" in info or "episode" in info) else "movie"
    media_type = media_type.lower()
    if media_type not in ("movie", "tv"):
        logger.info(f"[original-language] unknown media_type {media_type!r} (expected 'movie' or 'tv')")
        return []

    # --- 3. Build auth (Bearer token preferred, api_key as fallback) ----------
    headers = {"accept": "application/json"}
    params = {"query": title, "include_adult": "false"}
    if tmdb_read_access_token:
        headers["Authorization"] = f"Bearer {tmdb_read_access_token}"
    elif tmdb_api_key:
        params["api_key"] = tmdb_api_key
    else:
        logger.info("[original-language] no TMDB credentials supplied")
        return []

    if year:
        params["primary_release_year" if media_type == "movie" else "first_air_date_year"] = year

    # --- 4. Search TMDB --------------------------------------------------------
    try:
        resp = requests.get(
            f"{TMDB_BASE}/search/{media_type}",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except requests.RequestException as exc:
        logger.info(f"[original-language] TMDB request failed: {exc}")
        return []
    except ValueError:
        logger.info("[original-language] TMDB returned a non-JSON response")
        return []

    if not results:
        logger.info(f"[original-language] video title not found on TMDB: {title!r} ({media_type})")
        return []

    # --- 5. Keep only exact title matches -------------------------------------
    wanted = _normalize(title)
    exact = [
        r for r in results
        if any(_normalize(t) == wanted for t in _result_titles(r, media_type))
    ]

    # If a year is available and we still have several, disambiguate by year.
    if year and len(exact) > 1:
        by_year = [r for r in exact if _result_year(r, media_type) == year]
        if by_year:
            exact = by_year

    if not exact:
        logger.info(f"[original-language] no exact title match for {title!r} ({media_type})")
        return []
    if len(exact) > 1:
        logger.info(
            f"[original-language] can't find a unique match for {title!r} "
            f"({media_type}); {len(exact)} titles matched exactly"
        )
        return []

    # --- 6. Extract original_language -----------------------------------------
    lang = exact[0].get("original_language")
    if not lang:
        logger.info(f"[original-language] no original language identified for {title!r}")
        return []

    return [lang]

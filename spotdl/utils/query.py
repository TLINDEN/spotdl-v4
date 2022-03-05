import json
import concurrent.futures

from typing import List

from spotdl.types import Song, Playlist, Album, Artist, Saved
from spotdl.types.song import SongList
from spotdl.utils.formatter import create_empty_song


class QueryError(Exception):
    """
    Base class for all exceptions related to query.
    """


def parse_query(query: List[str], threads: int = 1) -> List[Song]:
    urls: List[str] = []
    songs: List[Song] = []
    for request in query:
        if (
            "youtube.com/watch?v=" in request
            or "youtu.be/" in request
            and "open.spotify.com" in request
            and "track" in request
            and "|" in request
        ):
            split_urls = request.split("|")
            if (
                len(split_urls) <= 1
                or "youtube" not in split_urls[0]
                and "youtu.be" not in split_urls[0]
                or "spotify" not in split_urls[1]
            ):
                raise QueryError(
                    "Incorrect format used, please use YouTubeURL|SpotifyURL"
                )

            songs.append(
                Song.from_dict(
                    {
                        **Song.from_url(split_urls[1]).json,
                        "download_url": split_urls[0],
                    }
                )
            )
        elif "open.spotify.com" in request and "track" in request:
            urls.append(request)
        elif "open.spotify.com" in request and "playlist" in request:
            urls.extend(Playlist.get_urls(request))
        elif "open.spotify.com" in request and "album" in request:
            urls.extend(Album.get_urls(request))
        elif "open.spotify.com" in request and "artist" in request:
            for album_url in Artist.get_albums(request):
                urls.extend(Album.get_urls(album_url))
        elif request == "saved":
            urls.extend(Saved.get_urls())
        elif request.endswith(".spotdl"):
            with open(request, "r", encoding="utf-8") as m3u_file:
                for track in json.load(m3u_file):
                    # Append to songs
                    songs.append(Song.from_dict(track))
        else:
            songs.append(Song.from_search_term(request))

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        for song in executor.map(Song.from_url, urls):
            songs.append(song)

    return songs


def get_simple_songs(
    query: List[str],
) -> List[Song]:
    """
    Parse query and return list containing simple song objects
    """

    songs: List[Song] = []
    lists: List[SongList] = []
    for request in query:
        if (
            "youtube.com/watch?v=" in request
            or "youtu.be/" in request
            and "open.spotify.com" in request
            and "track" in request
            and "|" in request
        ):
            split_urls = request.split("|")
            if (
                len(split_urls) <= 1
                or "youtube" not in split_urls[0]
                and "youtu.be" not in split_urls[0]
                or "spotify" not in split_urls[1]
            ):
                raise QueryError(
                    "Incorrect format used, please use YouTubeURL|SpotifyURL"
                )

            songs.append(
                Song.from_dict(
                    {
                        "url": split_urls[1],
                        "download_url": split_urls[0],
                    }
                )
            )
        elif "open.spotify.com" in request and "track" in request:
            songs.append(Song(url=request))  # type: ignore
        elif "open.spotify.com" in request and "playlist" in request:
            lists.append(Playlist.create_basic_list(request))
        elif "open.spotify.com" in request and "album" in request:
            lists.append(Album.create_basic_list(request))
        elif "open.spotify.com" in request and "artist" in request:
            lists.append(Artist.create_basic_list(request))
        elif request == "saved":
            lists.append(Saved.create_basic_list())
        elif request.endswith(".spotdl"):
            with open(request, "r", encoding="utf-8") as save_file:
                for track in json.load(save_file):
                    # Append to songs
                    songs.append(Song.from_dict(track))
        else:
            songs.append(Song.from_search_term(request))

    for song_list in lists:
        songs.extend([create_empty_song(url=url, song_list=song_list) for url in song_list.urls])  # type: ignore

    return songs

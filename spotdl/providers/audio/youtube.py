from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from pytube import YouTube as PyTube, Search
from yt_dlp import YoutubeDL

from spotdl.utils.formatter import create_song_title, create_search_query, slugify
from spotdl.utils.providers import match_percentage
from spotdl.providers.audio.base import AudioProvider
from spotdl.types import Song


class YTDLLogger:
    def debug(self, msg):  # pylint: disable=R0201
        """
        YTDL uses this to print debug messages.
        """
        pass  # pylint: disable=W0107

    def warning(self, msg):  # pylint: disable=R0201
        """
        YTDL uses this to print warnings.
        """
        pass  # pylint: disable=W0107

    def error(self, msg):  # pylint: disable=R0201
        """
        YTDL uses this to print errors.
        """
        raise Exception(msg)


class YouTube(AudioProvider):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize YouTube provider
        """

        self.name = "youtube"
        super().__init__(*args, **kwargs)

        if self.output_format == "m4a":
            ytdl_format = "bestaudio[ext=m4a]/bestaudio/best"
        elif self.output_format == "opus":
            ytdl_format = "bestaudio[ext=webm]/bestaudio/best"
        else:
            ytdl_format = "bestaudio"

        self.audio_handler = YoutubeDL(
            {
                "format": ytdl_format,
                "outtmpl": f"{str(self.output_directory)}/%(id)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "encoding": "UTF-8",
                "logger": YTDLLogger(),
                "cookiefile": self.cookie_file,
            }
        )

    def perform_audio_download(self, url: str) -> Optional[Path]:
        """
        Download a song from YouTube Music and save it to the output directory.
        """

        data = self.audio_handler.extract_info(url)

        if data:
            return Path(self.output_directory / f"{data['id']}.{data['ext']}")

        return None

    def search(self, song: Song) -> Optional[str]:
        """
        Search for a video on YouTube.
        Return the link to the song if found.
        Or return None if not found.
        """

        if self.search_query:
            search_query = create_search_query(
                song, self.search_query, False, None, True
            )
        else:
            # if isrc is not None then we try to find song with it
            if song.isrc:
                isrc_results = self.get_results(song.isrc)

                if isrc_results and len(isrc_results) == 1:
                    isrc_result = isrc_results[0]

                    if isrc_result and isrc_result.watch_url is not None:
                        return isrc_result.watch_url

            search_query = create_song_title(song.name, song.artists).lower()

        # Query YTM by songs only first, this way if we get correct result on the first try
        # we don't have to make another request to ytmusic api that could result in us
        # getting rate limited sooner
        results = self.get_results(search_query)

        if results is None:
            return None

        if self.filter_results:
            ordered_results = {results[0].watch_url: 100}
        else:
            # Order results
            ordered_results = self.order_results(results, song)

        # No matches found
        if len(ordered_results) == 0:
            return None

        result_items = list(ordered_results.items())

        # Sort results by highest score
        sorted_results = sorted(result_items, key=lambda x: x[1], reverse=True)

        # Return the first result
        return sorted_results[0][0]

    @staticmethod
    def get_results(search_term: str, **_) -> Optional[List[PyTube]]:
        """
        Get results from YouTube
        """
        return Search(search_term).results

    def order_results(self, results: List[PyTube], song: Song) -> Dict[str, Any]:
        """
        Filter results based on the song's metadata.
        """

        # Assign an overall avg match value to each result
        links_with_match_value = {}

        # Slugify song title
        slug_song_name = slugify(song.name)
        slug_song_title = slugify(
            create_song_title(song.name, song.artists)
            if not self.search_query
            else create_search_query(song, self.search_query, False, None, True)
        )

        for result in results:
            # Skip results without id
            if result.video_id is None:
                continue

            # Slugify some variables
            slug_result_name = slugify(result.title)
            sentence_words = slug_song_name.replace("-", " ").split(" ")

            # Check for common words in result name
            common_word = any(
                word != "" and word in slug_result_name for word in sentence_words
            )

            # skip results that have no common words in their name
            if not common_word:
                continue

            # Find artist match
            artist_match_number = 0.0

            # Calculate artist match for each artist
            # in the song's artist list
            for artist in song.artists:
                artist_match_number += match_percentage(
                    slugify(artist), slug_result_name
                )

            # skip results with artist match lower than 70%
            artist_match = artist_match_number / len(song.artists)
            if artist_match < 70:
                continue

            # Calculate name match
            name_match = match_percentage(slug_result_name, slug_song_title)

            # Drop results with name match lower than 50%
            if name_match < 50:
                continue

            # Calculate time match
            time_match = (
                100 - (result.length - song.duration**2) / song.duration * 100
            )

            average_match = (artist_match + name_match + time_match) / 3

            # the results along with the avg Match
            links_with_match_value[result.watch_url] = average_match

        return links_with_match_value

    def add_progress_hook(self, hook: Callable) -> None:
        """
        Add a progress hook to the yt-dlp.
        """

        super().add_progress_hook(hook)

        for progress_hook in self.progress_hooks:
            self.audio_handler.add_progress_hook(progress_hook)

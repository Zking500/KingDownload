import pytest
from ZkingDownload import limpiar_url_video

@pytest.mark.parametrize("input_url,expected", [
    # Standard YouTube URL
    ("https://www.youtube.com/watch?v=abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Shortened URL
    ("https://youtu.be/abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Shorts URL
    ("https://www.youtube.com/shorts/abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Music URL
    ("https://music.youtube.com/watch?v=abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Already clean
    ("https://www.youtube.com/watch?v=abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    # With extra parameters
    ("https://www.youtube.com/watch?v=abcdefghijk&ab_channel=Test", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Embedded URL
    ("https://www.youtube.com/embed/abcdefghijk", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Playlist URL (should extract video ID)
    ("https://www.youtube.com/watch?v=abcdefghijk&list=PL1234567890", "https://www.youtube.com/watch?v=abcdefghijk"),
    # Garbage URL (should return as is)
    ("https://www.notyoutube.com/", "https://www.notyoutube.com/"),
    # Not a URL at all
    ("abcdefghijk", "abcdefghijk"),
])
def test_limpiar_url_video(input_url, expected):
    assert limpiar_url_video(input_url) == expected
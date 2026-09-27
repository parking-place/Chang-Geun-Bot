import pytest

from changgeun.domain.models import DomainError
from changgeun.providers.media import ApprovedAudioResolver, youtube_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=ABCDEFGHIJK",
        "https://youtu.be/ABCDEFGHIJK",
        "https://www.youtube.com/shorts/ABCDEFGHIJK",
        "youtube.com/watch?v=ABCDEFGHIJK",
        "www.youtube.com/watch?v=ABCDEFGHIJK&list=example&t=10",
        "m.youtube.com/watch?v=ABCDEFGHIJK",
        "youtu.be/ABCDEFGHIJK",
        "youtube.com/shorts/ABCDEFGHIJK",
        "www.youtube.com/embed/ABCDEFGHIJK",
    ],
)
def test_valid_youtube_urls(url):
    assert youtube_id(url) == "ABCDEFGHIJK"


@pytest.mark.parametrize(
    "url",
    [
        "http://youtu.be/ABCDEFGHIJK",
        "https://youtube.com.evil/watch?v=ABCDEFGHIJK",
        "https://localhost/watch?v=ABCDEFGHIJK",
        "https://user@youtu.be/ABCDEFGHIJK",
        "https://youtu.be/../../secret",
        "https://youtube.com/watch?v=a&v=b",
        "youtube.com.evil/watch?v=ABCDEFGHIJK",
        "evil.youtube.com/watch?v=ABCDEFGHIJK",
        "user@youtube.com/watch?v=ABCDEFGHIJK",
        "//youtube.com/watch?v=ABCDEFGHIJK",
        "youtube.com:443/watch?v=ABCDEFGHIJK",
        "https://youtube.com:invalid/watch?v=ABCDEFGHIJK",
        "https://[invalid/watch?v=ABCDEFGHIJK",
    ],
)
def test_invalid_urls_never_become_arbitrary_network_fetch(url):
    with pytest.raises(DomainError, match="invalid_youtube_url"):
        youtube_id(url)


def test_unapproved_youtube_and_paths_fail_closed(tmp_path):
    root = tmp_path / "audio"
    root.mkdir()
    (root / "tone.wav").write_bytes(b"fixture")
    resolver = ApprovedAudioResolver(root, {"tone": "tone.wav", "escape": "../secret"})
    assert resolver.resolve("approved_audio", "tone").name == "tone.wav"
    with pytest.raises(DomainError, match="audio_source_not_approved"):
        resolver.resolve("youtube", "ABCDEFGHIJK")
    with pytest.raises(DomainError, match="invalid_audio_mapping"):
        resolver.resolve("approved_audio", "escape")

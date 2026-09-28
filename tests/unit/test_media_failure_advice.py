from changgeun.discord_adapter.runtime import AudioRuntime


def test_media_failure_advice_distinguishes_supported_exclusion_without_upstream_echo():
    category, advice = AudioRuntime.failure_advice("youtube_unsupported")
    assert category == "unsupported" and "공개 영상" in advice
    category, advice = AudioRuntime.failure_advice("signed-url-secret")
    assert category == "unknown" and "signed-url-secret" not in advice

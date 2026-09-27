import pytest

from changgeun.domain.models import DomainError
from changgeun.playback.state import Entry, PlaybackState, Session


def playing():
    session = Session(queue=[Entry("e1", "t1"), Entry("e2", "t2")])
    session.connected(session.join())
    session.resolved(session.start())
    return session


def test_stop_leave_preserves_same_entry_once_and_restart_no_autoplay():
    session = playing()
    session.stop()
    session.stop()
    session.stop(leave=True)
    assert [e.id for e in session.queue] == ["e1", "e2"]
    assert session.current is None
    session.recover_restart()
    assert session.state == PlaybackState.DISCONNECTED
    assert [e.id for e in session.queue] == ["e1", "e2"]


def test_stale_resolve_end_and_connect_cannot_restart():
    session = playing()
    old = session.generation
    session.stop(leave=True)
    assert not session.resolved(old)
    assert not session.finished(old)
    assert not session.connected(old)
    assert session.state == PlaybackState.DISCONNECTED


def test_pause_enqueue_preserves_position_and_requires_resume():
    session = playing()
    session.pause()
    session.queue.append(Entry("e3", "t3"))
    with pytest.raises(DomainError, match="paused_use_resume"):
        session.start()
    session.resume()
    assert session.current.id == "e1"
    assert session.state == PlaybackState.PLAYING


@pytest.mark.parametrize("repeat", ["one", "queue", "off"])
def test_manual_skip_never_immediately_repeats(repeat):
    session = playing()
    session.repeat = repeat
    session.skip()
    assert session.current.id == "e2"
    assert all(e.id != "e1" for e in session.queue)


def test_repeat_on_natural_completion_and_queue_shuffle():
    session = playing()
    session.repeat = "one"
    session.finished(session.generation)
    assert session.current.id == "e1"
    session.resolved(session.generation)
    session.repeat = "queue"
    session.finished(session.generation)
    assert session.current.id == "e2"
    assert session.queue[-1].id == "e1"
    current = session.current
    session.shuffle(42)
    assert session.current == current


def test_retry_once_and_stop_after_three_failed_tracks():
    session = Session(state=PlaybackState.IDLE, queue=[Entry(str(i), str(i)) for i in range(4)])
    session.start()
    for _ in range(3):
        before = session.current
        session.finished(session.generation, failed=True)
        assert session.current == before
        assert session.retry_count == 1
        session.finished(session.generation, failed=True)
    assert session.failed_tracks == 3
    assert session.state == PlaybackState.IDLE
    assert session.current is None
    assert len(session.queue) == 1


def test_auto_leave_rechecks_listener_count_and_state():
    session = playing()
    values = dict(now=200, empty_since=0, idle_since=None, paused_since=None)
    assert session.auto_leave_due(**values, listener_count=0)
    assert not session.auto_leave_due(**values, listener_count=1)
    session.pause()
    assert session.auto_leave_due(
        now=1800, empty_since=None, idle_since=None, paused_since=0, listener_count=1
    )

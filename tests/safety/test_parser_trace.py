import sqlite3

import pytest

from changgeun.parser.contracts import ParseError
from changgeun.parser.trace import TTL_MS, TraceStore, sanitize


def test_expiry_exact_boundary_and_cascade(tmp_path):
    path = tmp_path / 'trace' / 'command-traces-v2.sqlite3'
    store = TraceStore(path)
    store.begin('r', 'g', 'u', 'c', '!!창근아 목록', now_ms=1000)
    store.call('r', 'j1', 1, 'command_select', 'initial', 1,
               remote_attempted=True, status='finished',
               usage={'status': 'reported', 'input_tokens': 8, 'output_tokens': 2},
               now_ms=1001)
    store.event('r', 'stage.complete', {'ok': True}, call_id='j1', now_ms=1002)
    assert store.get('r', now_ms=1000 + TTL_MS - 1)
    assert len(store.calls('r', now_ms=1000 + TTL_MS - 1)) == 1
    assert store.get('r', now_ms=1000 + TTL_MS) is None
    assert store.calls('r', now_ms=1000 + TTL_MS) == []
    assert store.purge(now_ms=1000 + TTL_MS) == 1
    with store._connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM model_calls').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM trace_events').fetchone()[0] == 0


def test_ttl_immutable_call_owner_and_usage_once(tmp_path):
    store = TraceStore(tmp_path / 'trace' / 'command-traces-v2.sqlite3')
    store.begin('r', 'g', 'u', 'c', 'text', now_ms=1000)
    store.begin('other', 'g', 'u', 'c', 'text', now_ms=1000)
    with store._connect() as conn:
        with pytest.raises(sqlite3.IntegrityError, match='immutable trace TTL'):
            conn.execute('UPDATE command_requests SET expires_at_ms=expires_at_ms+1')
    with pytest.raises(ParseError, match='foreign_trace_call'):
        store.event('other', 'stage', {}, call_id='j1', now_ms=1001)
    store.call('r', 'j1', 1, 'command_select', 'initial', 1,
               remote_attempted=True, status='finished',
               usage={'status': 'reported', 'input_tokens': 8, 'output_tokens': 2,
                      'cached_tokens': 3, 'reasoning_tokens': 1}, now_ms=1001)
    with pytest.raises(sqlite3.IntegrityError):
        store.call('r', 'j1', 1, 'command_select', 'initial', 1,
                   remote_attempted=True, status='finished', now_ms=1002)
    with pytest.raises(ParseError, match='foreign_trace_call'):
        store.event('other', 'stage', {}, call_id='j1', now_ms=1002)
    assert store.usage_summary('g', now_ms=1002) == {
        'calls': 1, 'unknown_usage_calls': 0, 'known_input_tokens': 8,
        'known_output_tokens': 2, 'usage_complete': True,
    }


def test_masking_unknown_usage_and_no_executed_command_for_preview(tmp_path):
    store = TraceStore(tmp_path / 'trace' / 'command-traces-v2.sqlite3')
    store.begin('r', 'g', 'u', 'c',
                'Bearer abcdef https://example.org/x?api_key=secret&x=ok sk-1234567890123',
                now_ms=1000)
    store.event('r', 'stage.skipped', {'token': 'secret', 'message': 'sk-1234567890123'},
                now_ms=1001)
    store.call('r', 'j1', 1, 'command_select', 'initial', 1,
               remote_attempted=True, status='timeout', now_ms=1002)
    store.outcome('r', parse_status='parsed', execution_status='waiting_confirmation',
                  resolved_command='C05', now_ms=1003)
    row = store.get('r', now_ms=1003)
    assert row and row['executed_command'] is None and row['success'] is None
    assert 'abcdef' not in row['input_redacted']
    assert 'secret' not in row['input_redacted']
    assert 'sk-1234567890123' not in row['input_redacted']
    with store._connect() as conn:
        data = conn.execute('SELECT data_json FROM trace_events').fetchone()[0]
        assert 'secret' not in data and 'sk-1234567890123' not in data
    assert store.usage_summary('g', now_ms=1003)['unknown_usage_calls'] == 1
    assert sanitize({'api_key': 'secret'}) == {'api_key': '[REDACTED]'}


def test_unknown_schema_requires_migration_and_private_directory(tmp_path):
    path = tmp_path / 'old' / 'traces.sqlite3'
    path.parent.mkdir(mode=0o700)
    sqlite3.connect(path).close()
    with pytest.raises(ValueError, match='explicit migration'):
        TraceStore(path)
    public = tmp_path / 'public'
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError, match='private'):
        TraceStore(public / 'trace.sqlite3')

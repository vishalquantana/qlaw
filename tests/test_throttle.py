"""Pins for the per-host politeness limiter (offline)."""
from __future__ import annotations

import http.client
import socket
import time
import urllib.error

from gst_aar_law_shim import _throttle


def _iso(tmp_path, monkeypatch, min_delay=0.0, block=300.0, ceiling=1800.0):
    monkeypatch.setattr(_throttle, "STATE", tmp_path / "throttle.json")
    monkeypatch.setattr(_throttle, "MIN_DELAY", min_delay)
    monkeypatch.setattr(_throttle, "BLOCK_DELAY", block)
    monkeypatch.setattr(_throttle, "MAX_DELAY", ceiling)
    monkeypatch.delenv("LAW_THROTTLE_OFF", raising=False)


def _http(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://x.gov.in/a.pdf", code, "err", {}, None)


class TestBlockClassification:
    def test_missing_document_is_not_a_block(self) -> None:
        # 404 must not slow the harvest down: dead links are normal here.
        assert _throttle.is_block_error(_http(404)) is False
        assert _throttle.is_block_error(_http(410)) is False

    def test_rate_limit_is_a_block(self) -> None:
        assert _throttle.is_block_error(_http(429)) is True

    def test_forbidden_and_server_errors_are_blocks(self) -> None:
        for code in (401, 403, 500, 502, 503, 504):
            assert _throttle.is_block_error(_http(code)) is True, code

    def test_remote_disconnect_is_a_block(self) -> None:
        assert _throttle.is_block_error(http.client.RemoteDisconnected()) is True

    def test_connection_reset_and_timeout_are_blocks(self) -> None:
        assert _throttle.is_block_error(ConnectionResetError()) is True
        assert _throttle.is_block_error(socket.timeout()) is True

    def test_urlerror_wrapping_a_reset_is_a_block(self) -> None:
        assert _throttle.is_block_error(
            urllib.error.URLError(ConnectionResetError())) is True

    def test_ordinary_error_is_not_a_block(self) -> None:
        assert _throttle.is_block_error(ValueError("bad json")) is False
        assert _throttle.is_block_error(KeyError("actName")) is False


class TestEscalation:
    def test_first_block_moves_host_to_the_blocked_cadence(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch)
        _throttle.on_error("https://haryanatax.gov.in/a.pdf",
                           http.client.RemoteDisconnected())
        assert _throttle.delay_for("haryanatax.gov.in") == 300.0

    def test_repeated_blocks_escalate_to_the_ceiling(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch)
        url = "https://haryanatax.gov.in/a.pdf"
        for _ in range(6):
            _throttle.on_error(url, ConnectionResetError())
        assert _throttle.delay_for("haryanatax.gov.in") == 1800.0

    def test_non_block_error_leaves_cadence_alone(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch)
        _throttle.on_error("https://x.gov.in/a.pdf", ValueError("nope"))
        assert _throttle.delay_for("x.gov.in") == 0.0

    def test_state_persists_across_loads(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch)
        _throttle.on_error("https://x.gov.in/a.pdf", _http(429))
        assert _throttle.delay_for("x.gov.in") == 300.0


class TestDecay:
    def test_cadence_halves_after_a_run_of_successes(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch, min_delay=1.0)
        url = "https://x.gov.in/a.pdf"
        _throttle.on_error(url, _http(429))          # -> 300
        for _ in range(_throttle.DECAY_AFTER):
            _throttle.on_success(url)
        assert _throttle.delay_for("x.gov.in") == 150.0

    def test_decay_never_goes_below_normal(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch, min_delay=1.0)
        url = "https://x.gov.in/a.pdf"
        _throttle.on_error(url, _http(429))
        for _ in range(_throttle.DECAY_AFTER * 12):
            _throttle.on_success(url)
        assert _throttle.delay_for("x.gov.in") == 1.0


class TestWait:
    def test_wait_sleeps_the_hosts_cadence(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch, min_delay=0.25)
        url = "https://x.gov.in/a.pdf"
        _throttle.wait(url)                  # first call sets the clock, no sleep
        t0 = time.time()
        _throttle.wait(url)
        assert time.time() - t0 >= 0.2

    def test_wait_is_free_when_throttling_is_off(self, tmp_path, monkeypatch) -> None:
        _iso(tmp_path, monkeypatch, min_delay=5.0)
        monkeypatch.setenv("LAW_THROTTLE_OFF", "1")
        url = "https://x.gov.in/a.pdf"
        _throttle.wait(url)
        t0 = time.time()
        assert _throttle.wait(url) == 0.0
        assert time.time() - t0 < 0.2

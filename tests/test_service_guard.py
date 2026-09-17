import asyncio
from dataclasses import fields
import json
import logging

import pytest

from service_guard import SECURITY_HEADERS, ServiceGuard, Settings


@pytest.fixture(autouse=True)
def clean_guard_environment(monkeypatch):
    for field in fields(Settings):
        monkeypatch.delenv(f"HEALTHQUERY_{field.name.upper()}", raising=False)


async def echo_app(scope, receive, send):
    body = bytearray()
    while True:
        message = await receive()
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": bytes(body)})


async def request(guard, chunks=(b"{}",), client="127.0.0.1", headers=(), path="/api/query", method="POST"):
    scope = {"type": "http", "path": path, "method": method, "client": (client, 1234),
             "headers": list(headers), "query_string": b"private=medical-question"}
    messages = [{"type": "http.request", "body": chunk, "more_body": index < len(chunks) - 1}
                for index, chunk in enumerate(chunks)]
    output, reads = [], []

    async def receive():
        reads.append(True)
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    async def send(message):
        output.append(message)

    await guard(scope, receive, send)
    return output, len(reads)


def test_settings_defaults_and_environment(monkeypatch):
    assert Settings.from_env() == Settings()
    monkeypatch.setenv("HEALTHQUERY_BODY_LIMIT_BYTES", "16384")
    monkeypatch.setenv("HEALTHQUERY_RATE_LIMIT", "120")
    monkeypatch.setenv("HEALTHQUERY_RATE_WINDOW_SECONDS", "30")
    monkeypatch.setenv("HEALTHQUERY_MAX_INFLIGHT", "2")
    assert Settings.from_env() == Settings(16384, 120, 30, 2)


@pytest.mark.parametrize("name,value", [
    ("BODY_LIMIT_BYTES", "0"), ("BODY_LIMIT_BYTES", "1048577"),
    ("RATE_LIMIT", "-1"), ("RATE_LIMIT", "100001"),
    ("RATE_WINDOW_SECONDS", "86401"), ("MAX_INFLIGHT", "129"),
    ("MAX_INFLIGHT", "1.0"), ("MAX_INFLIGHT", " 2"),
    ("MAX_INFLIGHT", "NaN"), ("MAX_INFLIGHT", ""),
])
def test_bad_environment_fails_startup(monkeypatch, name, value):
    monkeypatch.setenv(f"HEALTHQUERY_{name}", value)
    with pytest.raises(ValueError, match=f"HEALTHQUERY_{name}"):
        Settings.from_env()


def test_exact_body_budget_is_replayed_once_with_security_headers():
    guard = ServiceGuard(echo_app, Settings(body_limit_bytes=8))
    output, reads = asyncio.run(request(guard, (b"abcd", b"efgh"), headers=[(b"x-request-id", b"attacker")]))
    assert output[0]["status"] == 200
    assert output[1]["body"] == b"abcdefgh"
    assert reads == 2
    headers = dict(output[0]["headers"])
    assert all(headers[key] == value for key, value in SECURITY_HEADERS.items())
    assert headers[b"cache-control"] == b"no-store"
    assert len(headers[b"x-request-id"]) == 32
    assert headers[b"x-request-id"] != b"attacker"
    assert guard.inflight == 0


@pytest.mark.parametrize("headers,chunks,expected_reads", [
    ([], (b"1234", b"56789"), 2),
    ([(b"content-length", b"1")], (b"123456789",), 1),
    ([(b"content-length", b"9")], (b"unread",), 0),
    ([(b"content-length", b"9" * 5000)], (b"unread",), 0),
])
def test_oversize_body_rejected_before_application(headers, chunks, expected_reads):
    guard = ServiceGuard(echo_app, Settings(body_limit_bytes=8))
    output, reads = asyncio.run(request(guard, chunks, headers=headers))
    assert output[0]["status"] == 413
    assert reads == expected_reads
    assert dict(output[0]["headers"])[b"cache-control"] == b"no-store"
    assert guard.inflight == 0


@pytest.mark.parametrize("headers", [
    [(b"content-length", b"-1")], [(b"content-length", b"invalid")],
    [(b"content-length", b"2"), (b"content-length", b"2")],
])
def test_ambiguous_content_length_rejected(headers):
    guard = ServiceGuard(echo_app, Settings())
    output, reads = asyncio.run(request(guard, headers=headers))
    assert output[0]["status"] == 400
    assert reads == 0


def test_body_deadline_rejects_stalled_receive_and_releases_slot(monkeypatch):
    original_wait_for = asyncio.wait_for

    async def fast_deadline(awaitable, timeout):
        assert timeout == 5
        return await original_wait_for(awaitable, timeout=0.001)

    monkeypatch.setattr("service_guard.asyncio.wait_for", fast_deadline)

    async def scenario():
        guard = ServiceGuard(echo_app, Settings())
        output = []

        async def stalled_receive():
            await asyncio.Event().wait()

        async def send(message):
            output.append(message)

        await guard({"type": "http", "method": "POST", "path": "/api/query"}, stalled_receive, send)
        assert output[0]["status"] == 408
        assert guard.inflight == 0

    asyncio.run(scenario())


def test_rate_limit_uses_peer_address_ignores_spoofed_headers_and_expires():
    async def scenario():
        clock = [0.0]
        guard = ServiceGuard(echo_app, Settings(rate_limit=2), time_provider=lambda: clock[0])
        for spoofed in (b"1.1.1.1", b"2.2.2.2"):
            output, _ = await request(guard, headers=[(b"x-forwarded-for", spoofed)])
            assert output[0]["status"] == 200
        clock[0] = 50.1
        output, _ = await request(guard, path="/api/sources/record", method="GET")
        assert output[0]["status"] == 429
        assert dict(output[0]["headers"])[b"retry-after"] == b"10"
        output, _ = await request(guard, client="127.0.0.2")
        assert output[0]["status"] == 200
        output, _ = await request(guard, path="/health", method="GET")
        assert output[0]["status"] == 200
        clock[0] = 60.0
        output, _ = await request(guard)
        assert output[0]["status"] == 200

    asyncio.run(scenario())


def test_rate_limit_client_storage_is_bounded():
    async def scenario():
        guard = ServiceGuard(echo_app, Settings())
        assert guard.max_clients == 4096
        guard.max_clients = 3
        for number in range(10):
            await request(guard, client=f"127.0.0.{number}")
        assert len(guard.clients) == 3
        assert "127.0.0.0" not in guard.clients

    asyncio.run(scenario())


def test_concurrency_limit_rejects_excess_work_and_releases_capacity():
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_app(scope, receive, send):
            entered.set()
            await release.wait()
            await echo_app(scope, receive, send)

        guard = ServiceGuard(slow_app, Settings(max_inflight=1))
        first = asyncio.create_task(request(guard))
        await entered.wait()
        output, reads = await request(guard)
        assert output[0]["status"] == 503
        assert dict(output[0]["headers"])[b"retry-after"] == b"1"
        assert reads == 0
        release.set()
        output, _ = await first
        assert output[0]["status"] == 200
        assert guard.inflight == 0
        output, _ = await request(guard)
        assert output[0]["status"] == 200

    asyncio.run(scenario())


def test_error_is_generic_and_logs_do_not_contain_sensitive_input(caplog):
    async def broken_app(scope, receive, send):
        raise RuntimeError("sensitive-medical-question")

    caplog.set_level(logging.INFO, logger="healthquery.access")
    guard = ServiceGuard(broken_app, Settings(max_inflight=1))
    output, _ = asyncio.run(request(guard, (b"sensitive-medical-question",), client="10.20.30.40"))
    assert output[0]["status"] == 500
    assert b"sensitive-medical-question" not in output[1]["body"]
    assert guard.inflight == 0
    event = json.loads(caplog.records[-1].message)
    assert event["error_type"] == "RuntimeError"
    assert event["route"] == "/api/query"
    assert event["status"] == 500
    assert "sensitive-medical-question" not in caplog.text
    assert "10.20.30.40" not in caplog.text
    assert "private=medical-question" not in caplog.text
    guard.app = echo_app
    output, _ = asyncio.run(request(guard))
    assert output[0]["status"] == 200


def test_source_paths_and_unknown_methods_are_redacted_in_logs(caplog):
    caplog.set_level(logging.INFO, logger="healthquery.access")
    guard = ServiceGuard(echo_app, Settings())
    asyncio.run(request(guard, path="/api/sources/private-diagnosis", method="private-method"))
    event = json.loads(caplog.records[-1].message)
    assert event["route"] == "/api/sources/{id}"
    assert event["method"] == "OTHER"
    assert "private-diagnosis" not in caplog.text
    assert "private-method" not in caplog.text


def test_failure_after_headers_does_not_send_a_second_response():
    async def scenario():
        output = []

        async def broken_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            raise RuntimeError("stream failed")

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        async def send(message):
            output.append(message)

        guard = ServiceGuard(broken_app, Settings())
        with pytest.raises(RuntimeError, match="Response interrupted") as caught:
            await guard({"type": "http", "method": "POST", "path": "/api/query"}, receive, send)
        assert caught.value.__suppress_context__ is True
        assert len(output) == 1
        assert guard.inflight == 0

    asyncio.run(scenario())


def test_disconnect_while_reading_does_not_call_app_or_leak_capacity():
    guard = ServiceGuard(echo_app, Settings())
    output, _ = asyncio.run(request(guard, chunks=()))
    assert output == []
    assert guard.inflight == 0


def test_cancelled_request_releases_capacity():
    async def scenario():
        entered = asyncio.Event()

        async def waiting_app(scope, receive, send):
            entered.set()
            await asyncio.Event().wait()

        guard = ServiceGuard(waiting_app, Settings(max_inflight=1))
        pending = asyncio.create_task(request(guard))
        await entered.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert guard.inflight == 0

    asyncio.run(scenario())

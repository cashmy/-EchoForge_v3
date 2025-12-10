from starlette.requests import Request

from backend.app.api.dependencies import (
    DEFAULT_ACTOR_ID,
    DEFAULT_ACTOR_SOURCE,
    ActorContext,
    get_actor_context,
)


def _make_request(headers: dict[str, str] | None = None) -> Request:
    header_list = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": header_list,
        "client": ("test", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_get_actor_context_defaults() -> None:
    context = get_actor_context(_make_request())

    assert isinstance(context, ActorContext)
    assert context.actor_id == DEFAULT_ACTOR_ID
    assert context.actor_source == DEFAULT_ACTOR_SOURCE


def test_get_actor_context_honors_headers() -> None:
    context = get_actor_context(
        _make_request(
            {
                "X-Actor-Id": "  operator ",
                "X-Actor-Source": " desktop_app ",
            }
        )
    )

    assert context.actor_id == "operator"
    assert context.actor_source == "desktop_app"

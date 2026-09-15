import sys
import asyncio
import uvicorn


def _configure_windows_asyncio() -> None:
    """Prefer SelectorEventLoop on Windows for subprocess/audio compatibility."""
    if sys.platform != "win32":
        return

    if sys.version_info >= (3, 14):
        asyncio.EventLoop = asyncio.SelectorEventLoop
        return

    set_event_loop_policy = getattr(asyncio, "set_event_loop_policy", None)
    policy_cls = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if set_event_loop_policy is not None and policy_cls is not None:
        set_event_loop_policy(policy_cls())


if __name__ == "__main__":
    _configure_windows_asyncio()
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)

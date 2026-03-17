"""Local development server entry point.

Sets the correct event loop policy on Windows (psycopg3 requires
SelectorEventLoop, not ProactorEventLoop) before starting uvicorn.
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config("src.main:app", host="0.0.0.0", port=8080)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())

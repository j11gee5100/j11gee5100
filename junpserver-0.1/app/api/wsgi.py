from __future__ import annotations

from a2wsgi import ASGIMiddleware

from app.api.main import app as asgi_app

# uWSGI speaks WSGI in this deployment. FastAPI remains ASGI internally and is
# adapted here so the production process manager can be uWSGI with 8 workers.
# WebSocket is intentionally not supported by this WSGI adapter; current MCP
# transport is HTTP JSON-RPC, so this is acceptable for the container profile.
application = ASGIMiddleware(asgi_app)

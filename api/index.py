"""Vercel serverless entrypoint.

Vercel's Python runtime serves the ASGI ``app`` exported here. The committed ``data/`` files
travel with the deployment and are read at request time. See ``vercel.json`` for routing.
"""

from app.main import app  # noqa: F401  (re-exported for the Vercel Python runtime)

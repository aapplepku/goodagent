"""Bounded HTTPS raster ingestion with DNS pinning and no redirect/proxy support."""

import asyncio
import contextlib
import http.client
import io
import ipaddress
import socket
import ssl
import threading
import warnings
from typing import Protocol
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_DOWNLOAD_SECONDS = 20
_RASTER_FORMATS = ("JPEG", "PNG", "WEBP", "GIF")


class ImageIngestionError(ValueError):
    """Safe public image failure; never include the destination or response body."""


class CatalogImageProvider(Protocol):
    async def fetch(self, url: str) -> bytes: ...


def public_addresses(url: str) -> tuple[str, str, list[str]]:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
        or parsed.fragment
        or len(url) > 2000
    ):
        raise ImageIngestionError("Images must use public HTTPS without credentials or redirects.")
    host = parsed.hostname.encode("idna").decode()
    addresses = sorted(
        {str(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    )
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ImageIngestionError("Image destination is not a public network address.")
    return host, (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else ""), addresses


def raster(data: bytes) -> bytes:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=_RASTER_FORMATS) as source:
                if source.format not in _RASTER_FORMATS:
                    raise ImageIngestionError("Unsupported raster format.")
                if source.width * source.height > MAX_PIXELS or max(source.size) > 8192:
                    raise ImageIngestionError("Image dimensions exceed the limit.")
                source.seek(0)
                decoded = source.convert("RGB")
                decoded.thumbnail((1600, 1600))
                output = io.BytesIO()
                decoded.save(output, format="PNG", optimize=True)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ImageIngestionError("Image could not be safely decoded.") from exc


class SafeCatalogImages:
    async def fetch(self, url: str) -> bytes:
        try:
            if url.startswith("sample-abo:"):
                from open_commerce.stores.sample import sample_image_bytes

                # A fixed, hash-checked package asset, not a URL or caller-chosen path.
                return await asyncio.to_thread(lambda: raster(sample_image_bytes(url[11:])))
            return await asyncio.to_thread(self._fetch, url)
        except (OSError, ValueError, http.client.HTTPException) as exc:
            raise ImageIngestionError(
                "Image unavailable or blocked; replace its URL and retry."
            ) from exc

    @staticmethod
    def _fetch(url: str) -> bytes:
        host, path, addresses = public_addresses(url)
        connection = http.client.HTTPSConnection(host, timeout=10)
        # Connect to a validated IP directly; TLS still validates the original hostname.
        # No second DNS resolution, environment proxy, redirect, or URL-controlled port.
        raw = socket.create_connection((addresses[0], 443), timeout=10)
        timer: threading.Timer | None = None
        try:
            secure = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            connection.sock = secure
            expired = threading.Event()

            def abort_download() -> None:
                expired.set()
                with contextlib.suppress(OSError):
                    secure.shutdown(socket.SHUT_RDWR)

            # A read timeout alone resets on incoming bytes and permits indefinite trickling.
            timer = threading.Timer(MAX_DOWNLOAD_SECONDS, abort_download)
            timer.daemon = True
            timer.start()
            connection.request(
                "GET", path, headers={"Accept": "image/*", "User-Agent": "OpenCommerce/0.1"}
            )
            response = connection.getresponse()
            if response.status != 200 or not response.getheader("Content-Type", "").startswith(
                "image/"
            ):
                raise ImageIngestionError("Image server did not return a supported image.")
            data = response.read(MAX_IMAGE_BYTES + 1)
            if expired.is_set():
                raise ImageIngestionError("Image download exceeded its time limit.")
            if len(data) > MAX_IMAGE_BYTES:
                raise ImageIngestionError("Image exceeds 5 MiB.")
            return raster(data)
        finally:
            if timer is not None:
                timer.cancel()
            connection.close()
            raw.close()

"""Offline decoder selection and existing raster ingestion bounds."""

import io
from unittest.mock import MagicMock

import pytest
from PIL import Image

from open_commerce.providers import catalog_images
from open_commerce.providers.catalog_images import ImageIngestionError, SafeCatalogImages, raster


def image_bytes(image_format: str, size: tuple[int, int] = (12, 8)) -> bytes:
    output = io.BytesIO()
    with Image.new("RGB", size, "red") as source:
        source.save(output, format=image_format)
    return output.getvalue()


@pytest.mark.parametrize("image_format", ["BMP", "TIFF"])
def test_unsupported_decoder_factory_is_not_invoked(
    monkeypatch: pytest.MonkeyPatch, image_format: str
) -> None:
    data = image_bytes(image_format)
    factory, accept = Image.OPEN[image_format]
    observed_factory = MagicMock(wraps=factory)
    monkeypatch.setitem(Image.OPEN, image_format, (observed_factory, accept))

    # Positive control: the old unrestricted open invokes the registered factory.
    with Image.open(io.BytesIO(data)) as source:
        assert source.format == image_format
    observed_factory.assert_called_once()
    observed_factory.reset_mock()

    with pytest.raises(ImageIngestionError):
        raster(data)
    observed_factory.assert_not_called()


@pytest.mark.parametrize("image_format", ["JPEG", "PNG", "WEBP", "GIF"])
def test_supported_formats_reencode_as_rgb_png(image_format: str) -> None:
    result = raster(image_bytes(image_format))
    with Image.open(io.BytesIO(result), formats=("PNG",)) as decoded:
        decoded.load()
        assert decoded.format == "PNG"
        assert decoded.mode == "RGB"
        assert decoded.size == (12, 8)
        assert decoded.getpixel((0, 0)) == pytest.approx((255, 0, 0), abs=3)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not an image: synthetic-private-marker",
        b"<svg/>",
        b"\x89PNG\r\n\x1a\n",
        b"\xff\xd8\xff",
        b"GIF89a",
        b"RIFF\x00\x00\x00\x00WEBP",
    ],
)
def test_bad_data_has_a_redacted_decode_error(data: bytes) -> None:
    with pytest.raises(ImageIngestionError, match=r"^Image could not be safely decoded\.$"):
        raster(data)


@pytest.mark.parametrize(
    ("size", "expected_size"),
    [
        ((1, 1), (1, 1)),
        ((1600, 800), (1600, 800)),
        ((3200, 800), (1600, 400)),
        ((800, 3200), (400, 1600)),
        ((8192, 1), (1600, 1)),
        ((1, 8192), (1, 1600)),
        ((4000, 4000), (1600, 1600)),
    ],
)
def test_dimension_and_pixel_limits_are_inclusive_and_thumbnail_is_bounded(
    size: tuple[int, int], expected_size: tuple[int, int]
) -> None:
    result = raster(image_bytes("PNG", size))
    with Image.open(io.BytesIO(result), formats=("PNG",)) as decoded:
        decoded.load()
        assert decoded.size == expected_size


@pytest.mark.parametrize("size", [(8193, 1), (1, 8193), (4000, 4001)])
def test_images_exceeding_dimension_or_pixel_limits_are_rejected(
    size: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    data = image_bytes("PNG", size)
    convert = MagicMock(side_effect=AssertionError("Oversized image must not be converted"))
    monkeypatch.setattr(Image.Image, "convert", convert)
    with pytest.raises(ImageIngestionError, match=r"^Image dimensions exceed the limit\.$"):
        raster(data)
    convert.assert_not_called()


@pytest.mark.parametrize(
    ("size", "cause"),
    [
        ((11, 10), Image.DecompressionBombWarning),
        ((21, 10), Image.DecompressionBombError),
    ],
)
def test_pillow_pixel_warning_and_error_remain_rejected(
    monkeypatch: pytest.MonkeyPatch, size: tuple[int, int], cause: type[Exception]
) -> None:
    data = image_bytes("PNG", size)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(
        ImageIngestionError, match=r"^Image could not be safely decoded\.$"
    ) as caught:
        raster(data)
    assert isinstance(caught.value.__cause__, cause)


def test_animated_gif_still_uses_only_the_first_frame() -> None:
    output = io.BytesIO()
    with Image.new("RGB", (12, 8), "red") as first, Image.new("RGB", (12, 8), "blue") as second:
        first.save(output, format="GIF", save_all=True, append_images=[second], duration=100)
    result = raster(output.getvalue())
    with Image.open(io.BytesIO(result), formats=("PNG",)) as decoded:
        assert decoded.getpixel((0, 0)) == (255, 0, 0)
        with pytest.raises(EOFError):
            decoded.seek(1)


@pytest.fixture
def offline_download(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock, MagicMock]:
    connection = MagicMock()
    response = connection.getresponse.return_value
    response.status = 200
    response.getheader.return_value = "image/png"
    raw = MagicMock()
    timer = MagicMock()
    monkeypatch.setattr(
        catalog_images,
        "public_addresses",
        lambda _: ("images.example", "/fixture.png", ["93.184.216.34"]),
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.socket.create_connection",
        MagicMock(return_value=raw),
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.ssl.create_default_context", MagicMock()
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.http.client.HTTPSConnection",
        MagicMock(return_value=connection),
    )
    monkeypatch.setattr(
        "open_commerce.providers.catalog_images.threading.Timer", MagicMock(return_value=timer)
    )
    return connection, raw, timer


@pytest.mark.parametrize("extra_byte", [False, True])
def test_download_byte_limit_remains_inclusive(
    monkeypatch: pytest.MonkeyPatch,
    offline_download: tuple[MagicMock, MagicMock, MagicMock],
    extra_byte: bool,
) -> None:
    connection, raw, timer = offline_download
    response = connection.getresponse.return_value
    png = image_bytes("PNG")
    response.read.return_value = png + b"\x00" * (5 * 1024 * 1024 + int(extra_byte) - len(png))
    decoder = MagicMock(wraps=raster)
    monkeypatch.setattr(catalog_images, "raster", decoder)
    if extra_byte:
        with pytest.raises(ImageIngestionError, match=r"^Image exceeds 5 MiB\.$"):
            SafeCatalogImages._fetch("https://images.example/fixture.png")
        decoder.assert_not_called()
    else:
        result = SafeCatalogImages._fetch("https://images.example/fixture.png")
        with Image.open(io.BytesIO(result), formats=("PNG",)) as decoded:
            decoded.load()
            assert decoded.size == (12, 8)
        decoder.assert_called_once()
    response.read.assert_called_once_with(5 * 1024 * 1024 + 1)
    timer.start.assert_called_once()
    timer.cancel.assert_called_once()
    connection.close.assert_called_once()
    raw.close.assert_called_once()


async def test_fetch_decode_failure_does_not_expose_url_or_body(
    offline_download: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    connection, _, _ = offline_download
    connection.getresponse.return_value.read.return_value = b"synthetic-private-response"
    with pytest.raises(
        ImageIngestionError, match=r"^Image unavailable or blocked; replace its URL and retry\.$"
    ):
        await SafeCatalogImages().fetch(
            "https://images.example/fixture?token=synthetic-private-token"
        )

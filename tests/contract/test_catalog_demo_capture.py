"""Capture is a separate, explicit private Basic-mode workflow, not a release gate."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source(path: str) -> str:
    return (ROOT / path).read_text()


def test_real_model_recorder_is_unchanged() -> None:
    original = ROOT / "apps/web/capture/alpha-recordings.spec.ts"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == (
        "4c23b6e7bc30aa62e1491126008a7a3d6adf7c5a889b42b8615e77d5e63ea76d"
    )


def test_capture_config_is_explicit_new_private_and_non_retrying() -> None:
    config = source("apps/web/catalog-demo.config.ts")
    for required in (
        'OPEN_COMMERCE_CAPTURE_CATALOG_DEMO !== "1"',
        "!process.env.OPEN_COMMERCE_E2E_SETUP_TOKEN",
        "!process.env.CATALOG_DEMO_OUTPUT",
        "!process.env.CATALOG_DEMO_TEST_OUTPUT",
        "newPrivateCapturePath(root, process.env.CATALOG_DEMO_OUTPUT)",
        "captureScratchPath(root, process.env.CATALOG_DEMO_TEST_OUTPUT, {",
        "connected: process.connected === true",
        'canSend: typeof process.send === "function"',
        'testMatch: "catalog-demo.spec.ts"',
        'trace: "off", screenshot: "off", video: "off"',
        'serviceWorkers: "block"',
        "retries: 0",
        "workers: 1",
        "outputDir: testOutput",
        'reporter: [["./capture/catalog-demo-reporter.ts"]]',
    ):
        assert required in config
    assert "output.startsWith(testOutput" in config
    assert "testOutput.startsWith(output" in config


def test_capture_preserves_actual_boundary_and_failure_evidence() -> None:
    spec = source("apps/web/capture/catalog-demo.spec.ts")
    for expected in (
        "sample_data: true, product_count: 48, errors: []",
        'status: "ready", product_count: 48, indexed_product_count: 48',
        "expect(ready.image_failures).toBe(0)",
        'product_id: "B0896LJNLH", price_minor: 1388, currency: "USD"',
        "expect(state.store.readiness?.ai_verified ?? false).toBe(false)",
        "await inaccessible(store.slug)",
        "waits_shortened: false, separate_browser_page: true",
        "browser_denied_requests: denied",
        "publication_approved: false, release_qualified: false",
        "real_model_pair_completed: false",
        "finish_failures: finishFailures",
        'flag: "wx", mode: 0o600',
        "if (finishFailures.length || denied || completed.length !== 3) receipt.passed = false",
    ):
        assert expected in spec
    assert 'name: "Check AI connection"' not in spec
    assert 'name: "Approve test payment"' not in spec
    assert "auth/register" not in spec
    assert "storageState({" not in spec
    assert "request.storageState()" in spec  # Read cookies into memory only.
    assert "JSON.stringify({ ...receipt" in spec
    assert "JSON.stringify(ownerState" not in spec
    assert 'await result.routeWebSocket("**/*"' in spec
    assert "guardDemoRoute(route, origins" in spec
    assert "acceptedMilestone(JSON.parse" in spec
    assert "route.continue()" not in spec
    # A substring also matches the search input, causing a strict locator failure.
    assert 'getByLabel("Catalog products")' not in spec
    assert 'getByLabel("Catalog products", { exact: true })' in spec
    assert 'resultCard.getByRole("img").evaluate' in spec
    assert 'guestProduct.getByRole("img").evaluate' in spec
    assert "caption_alignment_review_required: true" in spec


def test_capture_source_is_exportable_but_raw_recordings_are_not() -> None:
    from scripts.export_public_source import omission

    assert omission("apps/web/capture/catalog-demo.spec.ts") is None
    assert omission("apps/web/catalog-demo.config.ts") is None
    assert omission(".opencommerce/catalog-demo/receipt.json") is not None
    assert omission(".opencommerce/catalog-demo/catalog-to-store.webm") is not None

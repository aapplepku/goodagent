"""Explicit disposable-store probe for the cold-backup drill; never uses a real model."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from scripts.backup_self_hosted import private_json

OWNER = {"username": "recovery-fixture-owner", "password": "synthetic-owner-recovery-password"}
SHOPPER = {
    "username": "recovery-fixture-shopper",
    "password": "synthetic-shopper-recovery-password",
}
CSV = b"product_id,title,price,currency,inventory_quantity\nstaged,Pending recovery item,19,USD,5\n"


def request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    if not response.is_success:
        raise RuntimeError(f"Recovery probe failed: {method} {path}, HTTP {response.status_code}")
    return response.json() if response.content else None


def seed(url: str, project: str) -> dict[str, Any]:
    with httpx.Client(base_url=url, timeout=120) as owner:
        assert request(owner, "GET", "/v1/merchant/auth/status")["setup_required"]
        result = subprocess.run(
            [
                "docker",
                "exec",
                f"{project}-api-1",
                "python",
                "-m",
                "open_commerce.stores.console",
                "bootstrap",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        response = request(
            owner,
            "POST",
            "/v1/merchant/auth/setup",
            json={
                **OWNER,
                "bootstrap_token": result.stdout.strip(),
                "name": "Recovery fixture store",
            },
        )
        store = response["store"]
        upload = request(owner, "POST", "/v1/merchant/imports/sample")
        confirmed = request(
            owner,
            "POST",
            f"/v1/merchant/imports/{upload['id']}/confirm",
            json={"expected_review_fingerprint": upload["review_fingerprint"]},
            headers={"Idempotency-Key": "recovery-confirm"},
        )
        for _ in range(120):
            readiness = request(owner, "GET", "/v1/merchant/store")
            if readiness["indexing"]["status"] == "ready":
                break
            time.sleep(1)
        else:
            raise RuntimeError("Synthetic catalog did not index in time")
        catalog = confirmed["catalog_id"]
        preview = request(owner, "POST", "/v1/merchant/store/preview", json={"catalog_id": catalog})
        with httpx.Client(
            base_url=url, timeout=120, headers={"x-store-slug": store["slug"]}
        ) as shopper:
            request(
                shopper,
                "POST",
                f"/v1/stores/{store['slug']}/preview",
                json={"token": preview["token"]},
            )
            request(shopper, "POST", "/v1/shopper/auth/guest")
            found = request(
                shopper,
                "POST",
                "/v1/shopper/chat",
                json={"content": "coffee"},
                headers={"Idempotency-Key": "recovery-preview-search"},
            )
            assert found["assistant_message"]["products"]
            request(
                owner,
                "POST",
                "/v1/merchant/store/sharing",
                json={
                    "catalog_id": catalog,
                    "enabled": True,
                    "acknowledge_demo_checkout": True,
                    "acknowledge_image_issues": True,
                },
                headers={"Idempotency-Key": "recovery-share"},
            )
            shopper.cookies.clear()
            request(shopper, "POST", "/v1/shopper/auth/guest")
            registered = request(
                shopper,
                "POST",
                "/v1/shopper/auth/register",
                json={**SHOPPER, "display_name": "Recovery tester"},
            )
            memory = request(
                shopper,
                "POST",
                "/v1/shopper/chat",
                json={"content": "Remember that I prefer organic products"},
                headers={"Idempotency-Key": "recovery-memory"},
            )
            assert memory["memories_saved"]
            product = found["assistant_message"]["products"][0]
            cart = request(
                shopper,
                "POST",
                "/v1/shopper/cart/items",
                json={"product_id": product["product_id"], "quantity": 1},
                headers={"Idempotency-Key": "recovery-cart"},
            )
            checkout = request(
                shopper,
                "POST",
                "/v1/shopper/checkout/preview",
                json={"cart_version": cart["version"]},
                headers={"Idempotency-Key": "recovery-checkout"},
            )
            payload = {"checkout_id": checkout["checkout_id"], "payment_method": "test_success"}
            paid = request(
                shopper,
                "POST",
                "/v1/shopper/checkout/confirm",
                json=payload,
                headers={"Idempotency-Key": "recovery-payment"},
            )
            assert paid["order"]
            cart = request(
                shopper,
                "POST",
                "/v1/shopper/cart/items",
                json={"product_id": product["product_id"], "quantity": 2},
                headers={"Idempotency-Key": "recovery-next-cart"},
            )
            staged = request(
                owner,
                "POST",
                "/v1/merchant/imports/upload?filename=recovery-staged.csv",
                content=CSV,
                headers={"Content-Type": "text/csv"},
            )
            return {
                "store": store,
                "catalog_id": catalog,
                "staged_id": staged["id"],
                "shopper_id": registered["account"]["id"],
                "conversation_id": memory["conversation"]["id"],
                "memory_id": memory["memories_saved"][0]["id"],
                "product_id": product["product_id"],
                "image_url": product["image_url"],
                "checkout_payload": payload,
                "order": paid["order"],
                "cart_id": cart["id"],
                "cart_count": cart["item_count"],
            }


def verify(url: str, fixture: dict[str, Any]) -> dict[str, bool]:
    with (
        httpx.Client(base_url=url, timeout=120) as owner,
        httpx.Client(
            base_url=url,
            timeout=120,
            headers={"x-store-slug": fixture["store"]["slug"]},
        ) as shopper,
    ):
        authenticated = request(owner, "POST", "/v1/merchant/auth/login", json=OWNER)
        assert authenticated["store"]["id"] == fixture["store"]["id"]
        assert authenticated["store"]["published_catalog_id"] == fixture["catalog_id"]
        assert authenticated["store"]["sharing_enabled"]
        staged = request(owner, "GET", f"/v1/merchant/imports/{fixture['staged_id']}")
        assert staged["filename"] == "recovery-staged.csv" and staged["status"] == "review"
        account = request(shopper, "POST", "/v1/shopper/auth/login", json=SHOPPER)
        assert account["account"]["id"] == fixture["shopper_id"]
        memory = request(shopper, "GET", "/v1/shopper/memories")
        assert any(item["id"] == fixture["memory_id"] for item in memory["items"])
        conversation = request(
            shopper, "GET", f"/v1/shopper/conversations/{fixture['conversation_id']}"
        )
        assert any("organic" in item["content"] for item in conversation["messages"])
        cart = request(shopper, "GET", "/v1/shopper/cart")
        assert cart["id"] == fixture["cart_id"] and cart["item_count"] == fixture["cart_count"]
        replay = request(
            shopper,
            "POST",
            "/v1/shopper/checkout/confirm",
            json=fixture["checkout_payload"],
            headers={"Idempotency-Key": "recovery-payment"},
        )
        assert replay["order"] == fixture["order"]
        orders = request(shopper, "GET", "/v1/shopper/orders")
        assert len(orders["items"]) == 1
        image_path = fixture["image_url"]
        assert image_path.startswith("/api/runtime/v1/shopper/assets/")
        image = shopper.get(image_path.removeprefix("/api/runtime"))
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
        found = request(
            shopper,
            "POST",
            "/v1/shopper/chat",
            json={"content": "coffee"},
            headers={"Idempotency-Key": "after-restore-search"},
        )
        assert found["assistant_message"]["products"]
        assert shopper.get("/v1/merchant/store").status_code == 401
        assert (
            httpx.get(
                url + "/v1/shopper/catalog", headers={"x-store-slug": "nonexistent-recovery-store"}
            ).status_code
            == 404
        )
        key = "recovery-worker-" + uuid4().hex
        thread = request(
            owner,
            "POST",
            "/v1/manager/threads",
            json={"title": "Recovery verification", "description": "Synthetic worker check"},
            headers={"Idempotency-Key": key},
        )
        submitted = request(
            owner,
            "POST",
            f"/v1/manager/threads/{thread['thread']['id']}/runs",
            json={"content": "Hello"},
            headers={"Idempotency-Key": key},
        )
        for _ in range(90):
            run = request(owner, "GET", f"/v1/manager/runs/{submitted['id']}")
            if run["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(1)
        assert run["status"] == "completed", "Recovered worker did not complete fresh work"
        replayed = request(
            owner,
            "POST",
            f"/v1/manager/threads/{thread['thread']['id']}/runs",
            json={"content": "Hello"},
            headers={"Idempotency-Key": key},
        )
        assert replayed["id"] == submitted["id"]
        return {
            name: True
            for name in (
                "owner_login",
                "publication_identity",
                "encrypted_import_review",
                "shopper_login",
                "memory",
                "conversation",
                "cart",
                "demo_order",
                "payment_idempotency",
                "stored_image",
                "search",
                "merchant_access_denied",
                "wrong_store_denied",
                "fresh_worker_run",
                "worker_command_idempotency",
            )
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "verify"])
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--confirm-disposable", action="store_true", required=True)
    args = parser.parse_args()
    if not args.api_url.startswith("http://127.0.0.1:"):
        raise SystemExit("Disposable loopback installation required")
    if args.action == "seed":
        private_json(args.fixture, seed(args.api_url, args.project))
        print("Synthetic recovery fixture created; no credentials printed.")
    else:
        print(
            json.dumps(verify(args.api_url, json.loads(args.fixture.read_bytes())), sort_keys=True)
        )


if __name__ == "__main__":
    main()

"""The implementation and `openapi.yaml` must not drift apart.

`openapi.yaml` was derived from `frontend/src/api/client.js`, so this is also
what keeps the backend answering the calls the frontend actually makes.
"""

from pathlib import Path

import pytest
import yaml

from app.main import app

CONTRACT = Path(__file__).resolve().parents[2] / "openapi.yaml"
METHODS = {"get", "post", "put", "patch", "delete"}


def operations(document: dict) -> set[tuple[str, str]]:
    return {
        (path, method)
        for path, item in document["paths"].items()
        for method in item
        if method in METHODS
    }


@pytest.fixture(scope="module")
def contract() -> dict:
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def implemented() -> dict:
    return app.openapi()


def test_the_contract_file_exists():
    assert CONTRACT.exists(), f"{CONTRACT} is the source of truth for this API"


def test_every_documented_operation_is_implemented(contract, implemented):
    missing = operations(contract) - operations(implemented)
    assert not missing, f"documented but not implemented: {sorted(missing)}"


def test_every_implemented_operation_is_documented(contract, implemented):
    undocumented = operations(implemented) - operations(contract)
    assert not undocumented, f"implemented but not documented: {sorted(undocumented)}"


def test_the_ten_endpoints_the_frontend_calls_are_present(implemented):
    """The list annotated in frontend/src/api/client.js."""
    expected = {
        ("/api/cards", "get"),
        ("/api/cards", "post"),
        ("/api/cards/{cardId}", "get"),
        ("/api/cards/{cardId}", "patch"),
        ("/api/cards/{cardId}", "delete"),
        ("/api/cards/{cardId}/job", "patch"),
        ("/api/learning/{learningId}/jobs/{jobId}", "put"),
        ("/api/learning/{learningId}/jobs/{jobId}", "delete"),
        ("/api/preferences", "get"),
        ("/api/preferences", "patch"),
        ("/api/ai/extract-job-advert", "post"),
    }
    assert expected <= operations(implemented)


def test_the_domain_vocabulary_matches_the_spec(implemented):
    """§28 — the enums are the product's vocabulary and must not drift."""
    schemas = implemented["components"]["schemas"]
    assert set(schemas["Area"]["enum"]) == {"CURRENT_JOB", "JOB_SEARCH", "LEARNING"}
    assert set(schemas["Priority"]["enum"]) == {"LOW", "MEDIUM", "HIGH", "URGENT"}
    assert set(schemas["Fit"]["enum"]) == {"LOW", "MEDIUM", "HIGH", "DREAM"}
    assert set(schemas["WorkMode"]["enum"]) == {"ONSITE", "HYBRID", "REMOTE", "UNKNOWN"}
    assert set(schemas["Outcome"]["enum"]) == {
        "ACTIVE",
        "REJECTED",
        "WITHDRAWN",
        "ACCEPTED",
        "DECLINED",
    }


def test_cards_are_served_in_camel_case(client):
    """The frontend's card model is camelCase; the API speaks its language."""
    response = client.post("/api/cards", json={"title": "x", "area": "CURRENT_JOB"})
    card = response.json()
    assert "plannedThisWeek" in card
    assert "estimatedHours" in card
    assert "createdAt" in card
    assert "planned_this_week" not in card


def test_errors_carry_a_message(client):
    for response in [
        client.get("/api/cards/nope"),
        client.post("/api/cards", json={"title": "", "area": "LEARNING"}),
    ]:
        assert "message" in response.json(), response.text


# --------------------------------------------------------------------- security
#
# The posture, not just the shape: closed by default, with login the one
# documented exception. A new endpoint that forgets its token requirement fails
# here rather than in production.

#: Endpoints reachable without a token. Adding to this set is deliberately a
#: visible edit in a file called "contract" - opening a door should not be a
#: one-line change nobody notices in review.
PUBLIC = {
    ("/api/auth/login", "post"),
    # §23 - someone who opens the API in a browser should learn what it is,
    # rather than be told to authenticate before they know to what.
    ("/", "get"),
    # The things that ask this are not people and cannot hold a token: a load
    # balancer, the container's HEALTHCHECK, and the deploy pipeline deciding
    # whether the release worked. It answers with two words.
    ("/api/health", "get"),
}


def _is_public(document: dict, path: str, method: str) -> bool:
    """An operation is public if it overrides the global requirement with []."""
    operation = document["paths"][path][method]
    if "security" in operation:
        return operation["security"] == []
    return not document.get("security")


def test_the_contract_is_closed_by_default(contract):
    assert contract.get("security") == [{"bearerAuth": []}]


def test_the_implementation_is_closed_by_default(implemented):
    for path, method in operations(implemented):
        if (path, method) in PUBLIC:
            continue
        operation = implemented["paths"][path][method]
        assert operation.get("security"), f"{method.upper()} {path} requires no token"


def test_exactly_the_expected_endpoints_are_public_in_the_contract(contract):
    public = {op for op in operations(contract) if _is_public(contract, *op)}
    assert public == PUBLIC


def test_exactly_the_expected_endpoints_are_public_in_the_implementation(implemented):
    public = {
        op
        for op in operations(implemented)
        if not implemented["paths"][op[0]][op[1]].get("security")
    }
    assert public == PUBLIC


def test_the_security_scheme_is_a_bearer_token(contract, implemented):
    for document in (contract, implemented):
        schemes = document["components"]["securitySchemes"]
        scheme = schemes.get("bearerAuth") or schemes.get("HTTPBearer")
        assert scheme["type"] == "http"
        assert scheme["scheme"] == "bearer"


def _refs(node) -> set[str]:
    """Every component schema name reachable from a fragment of the document."""
    found = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            found |= _refs(value)
    elif isinstance(node, list):
        for value in node:
            found |= _refs(value)
    return found


def _response_schemas(document: dict) -> set[str]:
    """Schema names reachable from any response, followed transitively."""
    seen: set[str] = set()
    queue = list(
        _refs(
            [
                operation.get("responses", {})
                for item in document["paths"].values()
                for method, operation in item.items()
                if method in METHODS
            ]
        )
    )
    components = document["components"]["schemas"]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        queue.extend(_refs(components.get(name, {})) - seen)
    return seen


def test_a_password_never_appears_in_a_response(implemented):
    """The hash must not be reachable from anything a client can be sent.

    `LoginRequest.password` is fine — it travels inbound only — so this walks
    from responses outwards rather than scanning every schema.
    """
    components = implemented["components"]["schemas"]
    for name in _response_schemas(implemented):
        for field in components.get(name, {}).get("properties", {}):
            assert "password" not in field.lower(), f"{name}.{field} is reachable from a response"


def test_the_login_request_is_never_a_response(implemented):
    assert "LoginRequest" not in _response_schemas(implemented)


def test_the_user_model_is_not_exposed_at_all(implemented):
    """`User` carries the hash. Only `UserPublic` goes on the wire."""
    assert "User" not in _response_schemas(implemented)

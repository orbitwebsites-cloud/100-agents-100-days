"""API Designer tools."""

import json

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("api-designer")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


def test_lint_endpoints_findings_and_rewrites():
    out = call("lint_endpoints", endpoints=["GET /getUsers", "POST /user/{id}/delete", "GET /v1/orders/", "GET /orders/:orderId/items", "DELETE /orders"])
    by = {f["endpoint"]: f for f in out["findings"]}
    assert any("verb 'get'" in i["message"] for i in by["GET /getUsers"]["issues"])
    assert by["GET /getUsers"]["suggested"] == "GET /users"
    msgs = " ".join(i["message"] for i in by["POST /user/{id}/delete"]["issues"])
    assert "singular" in msgs and "verb 'delete'" in msgs
    assert any("trailing slash" in i["message"] for i in by["GET /v1/orders/"]["issues"])
    assert any("DELETE on a collection" in i["message"] for i in by["DELETE /orders"]["issues"])
    assert any("mixed path-parameter styles" in g for g in out["global_issues"])
    assert any("versioned" in g for g in out["global_issues"])
    assert out["errors"] >= 2 and out["score"] < 70


def test_lint_endpoints_clean_list_scores_100():
    out = call("lint_endpoints", endpoints=["GET /v1/users", "GET /v1/users/{id}", "POST /v1/users", "PATCH /v1/users/{id}", "DELETE /v1/users/{id}", "POST /v1/users/{id}/password-resets"])
    assert out["score"] == 100 and out["clean"] == 6


def test_lint_endpoints_rejects_bad_line():
    with pytest.raises(ToolError):
        call("lint_endpoints", endpoints=["FETCH users"])


def test_status_code_advisor_conflict_and_validation():
    out = call("status_code_advisor", situation="user submits a booking but the slot was already booked by someone else — state conflict")
    assert out["status"] == 409
    assert out["body"]["status"] == 409
    out2 = call("status_code_advisor", situation="request body parsed fine but the email field is invalid and the date is in the past")
    assert out2["status"] == 422 and "errors" in out2["body"]
    out3 = call("status_code_advisor", situation="report generation takes minutes, accept the job and process in the background")
    assert out3["status"] == 202 and any("Location" in h for h in out3["headers"])


def test_status_code_advisor_rejects_unmappable():
    with pytest.raises(ToolError):
        call("status_code_advisor", situation="zzz qqq")


SPEC_OLD = {
    "openapi": "3.0.3",
    "info": {"title": "Shop", "version": "1.0.0"},
    "components": {
        "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}},
        "schemas": {"Order": {"type": "object", "required": ["id", "total"], "properties": {"id": {"type": "string"}, "total": {"type": "integer"}, "legacy_id": {"type": "string"}, "status": {"type": "string", "enum": ["new", "paid"]}}}},
    },
    "security": [{"bearer": []}],
    "paths": {
        "/orders": {
            "get": {"operationId": "listOrders", "summary": "List", "tags": ["orders"], "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}, "description": "n"}],
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/Order"}}}}}, "400": {"description": "bad"}}},
            "post": {"operationId": "createOrder", "summary": "Create", "tags": ["orders"], "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"total": {"type": "integer"}, "note": {"type": "string"}}}}}},
                     "responses": {"201": {"description": "created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Order"}}}}, "422": {"description": "invalid"}}},
        },
        "/orders/{id}": {
            "get": {"operationId": "getOrder", "summary": "Get", "tags": ["orders"], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "id"}],
                    "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Order"}}}}, "404": {"description": "nope"}}},
            "delete": {"operationId": "deleteOrder", "summary": "Delete", "tags": ["orders"], "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}, "description": "id"}],
                       "responses": {"204": {"description": "gone"}, "404": {"description": "nope"}}},
        },
    },
}


def test_check_openapi_scores_good_spec():
    out = call("check_openapi", spec=json.dumps(SPEC_OLD))
    assert out["operations"] == 4
    assert out["counts"].get("error", 0) == 0
    assert out["score"] >= 85


def test_check_openapi_finds_errors():
    bad = json.loads(json.dumps(SPEC_OLD))
    bad["paths"]["/orders/{id}"]["get"]["parameters"] = []
    del bad["paths"]["/orders"]["get"]["operationId"]
    bad["paths"]["/orders"]["post"]["operationId"] = "getOrder"
    del bad["paths"]["/orders"]["get"]["responses"]["200"]
    out = call("check_openapi", spec=json.dumps(bad))
    msgs = [i["message"] for i in out["issues"] if i["level"] == "error"]
    assert any("{id} not declared" in m for m in msgs)
    assert any("operationId missing" in m for m in msgs)
    assert any("used 2 times" in m for m in msgs)
    assert any("no 2xx" in m for m in msgs)
    assert "Not SDK-ready" in out["verdict"]


def test_check_openapi_rejects_yaml():
    with pytest.raises(ToolError):
        call("check_openapi", spec="openapi: 3.0.0\ninfo:\n  title: x")


def test_diff_breaking_changes_detects_each_kind():
    new = json.loads(json.dumps(SPEC_OLD))
    del new["components"]["schemas"]["Order"]["properties"]["legacy_id"]          # response field removed
    new["components"]["schemas"]["Order"]["properties"]["total"]["type"] = "number"  # type changed
    new["paths"]["/orders"]["post"]["requestBody"]["content"]["application/json"]["schema"]["required"] = ["total"]  # became required
    new["paths"]["/orders"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["currency"] = {"type": "string"}  # optional added
    new["paths"]["/orders"]["get"]["parameters"].append({"name": "status", "in": "query", "required": True, "schema": {"type": "string"}})  # new required param
    del new["paths"]["/orders/{id}"]["delete"]                                        # operation removed
    new["paths"]["/shipments"] = {"get": {"operationId": "listShipments", "responses": {"200": {"description": "ok"}}}}  # added
    out = call("diff_breaking_changes", old_spec=json.dumps(SPEC_OLD), new_spec=json.dumps(new))
    kinds = Counter = {}
    for b in out["breaking"]:
        kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    assert kinds["operation removed"] == 1
    assert kinds["new required parameter"] == 1
    assert kinds["request field became required"] == 1
    assert kinds["response field removed"] == 3  # legacy_id in list, create, get responses
    assert kinds["response field type changed"] == 3
    assert {a["kind"] for a in out["additive"]} >= {"operation added", "optional request field added"}
    assert out["semver_bump"] == "major"


def test_diff_breaking_changes_additive_only():
    new = json.loads(json.dumps(SPEC_OLD))
    new["components"]["schemas"]["Order"]["properties"]["eta"] = {"type": "string"}
    out = call("diff_breaking_changes", old_spec=json.dumps(SPEC_OLD), new_spec=json.dumps(new))
    assert out["breaking"] == [] and out["semver_bump"] == "minor"
    assert len(out["additive"]) == 3


def test_diff_breaking_changes_rejects_bad_json():
    with pytest.raises(ToolError):
        call("diff_breaking_changes", old_spec="{", new_spec="{}")

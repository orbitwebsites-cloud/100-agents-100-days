"""Bug Hunter tools."""

import pytest

from hundred import registry
from hundred.core import ToolError

A = registry.get("bug-hunter")


def call(tool, **kwargs):
    return A.get_tool(tool).call(kwargs)


PY_TRACE = '''Traceback (most recent call last):
  File "/app/services/orders.py", line 42, in create_order
    total = price_for(user.plan)
  File "/app/services/pricing.py", line 17, in price_for
    return PLANS[plan]["price"]
  File "/usr/lib/python3.11/site-packages/somelib/core.py", line 9, in __getitem__
    return self._d[key]
KeyError: 'enterprise'
'''

JAVA_TRACE = '''Exception in thread "main" java.lang.IllegalStateException: wrapper
\tat com.acme.api.OrderController.create(OrderController.java:55)
\tat org.springframework.web.method.support.InvocableHandlerMethod.invoke(InvocableHandlerMethod.java:205)
Caused by: java.lang.NullPointerException: Cannot invoke "String.length()" because "name" is null
\tat com.acme.core.Pricing.priceFor(Pricing.java:17)
\tat com.acme.api.OrderController.create(OrderController.java:53)
\t... 12 more
'''

JS_TRACE = '''TypeError: Cannot read properties of undefined (reading 'id')
    at getUser (/srv/app/src/users.js:12:18)
    at /srv/app/node_modules/express/lib/router/layer.js:95:5
    at Layer.handle [as handle_request] (/srv/app/node_modules/express/lib/router/layer.js:95:5)
'''


def test_parse_python_trace_blame_frame_is_user_code():
    out = call("parse_stack_trace", trace=PY_TRACE)
    assert out["language"] == "python"
    assert out["exception_type"] == "KeyError"
    assert out["message"] == "'enterprise'"
    assert out["frame_count"] == 3
    assert out["origin_frame"]["file"].endswith("somelib/core.py")
    assert out["blame_frame"]["file"] == "/app/services/pricing.py" and out["blame_frame"]["line"] == 17
    assert "missing that key" in out["hint"]


def test_parse_java_trace_chain_root_cause():
    out = call("parse_stack_trace", trace=JAVA_TRACE)
    assert out["language"] == "java"
    assert out["exception_type"] == "java.lang.IllegalStateException"
    assert len(out["chain"]) == 2
    assert out["root_cause_exception"]["type"] == "java.lang.NullPointerException"
    assert out["root_cause_exception"]["blame_frame"]["file"] == "Pricing.java"
    assert out["root_cause_exception"]["blame_frame"]["line"] == 17


def test_parse_js_trace():
    out = call("parse_stack_trace", trace=JS_TRACE)
    assert out["language"] == "javascript"
    assert out["blame_frame"]["function"] == "getUser" and out["blame_frame"]["line"] == 12
    assert out["frames"][1]["in_user_code"] is False


def test_parse_trace_rejects_prose():
    with pytest.raises(ToolError):
        call("parse_stack_trace", trace="it just crashed, no idea why")


LOGS = "\n".join(
    [f"2026-09-27T10:0{i % 10}:00Z INFO request id=abc{i} took {i * 3}ms" for i in range(20)]
    + ["2026-09-27T10:05:00Z WARN pool exhausted, waiting 200ms"]
    + [f"2026-09-27T10:06:0{i}Z ERROR db timeout after 5000ms for user 0x{i:04x}" for i in range(7)]
)


def test_cluster_logs_templates_counts_and_order():
    out = call("cluster_logs", logs=LOGS)
    assert out["total_lines"] == 28
    assert out["unique_templates"] == 3
    assert out["clusters"][0]["count"] == 20 and out["clusters"][0]["level"] == "INFO"
    assert out["error_lines"] == 7
    assert out["error_clusters"][0]["template"].startswith("<ts> ERROR db timeout after <n> for user <hex>")
    assert out["first_problems_in_order"][0]["level"] == "WARN"
    assert out["busiest_error_minute"]["minute"] == "2026-09-27T10:06"


def test_cluster_logs_rejects_empty():
    with pytest.raises(ToolError):
        call("cluster_logs", logs="\n\n")


def test_bisect_plan_math():
    out = call("bisect_plan", commit_count=100, good_ref="v1.2.0", minutes_per_test=4)
    assert out["steps"] == 7
    assert out["estimated_minutes"] == 28
    assert out["linear_steps_avoided"] == 92
    out2 = call("bisect_plan", commits=[f"c{i}" for i in range(8)])
    assert out2["steps"] == 3 and out2["first_commit_to_test"] == "c4"


def test_bisect_plan_rejects_zero():
    with pytest.raises(ToolError):
        call("bisect_plan", commit_count=0)


def test_rank_suspects_prefers_trace_files():
    frames = call("parse_stack_trace", trace=PY_TRACE)["frames"]
    out = call("rank_suspects", frames=frames, changed_files=["docs/README.md", "services/pricing.py", "services/orders.py"], error_message="KeyError enterprise plan pricing")
    assert out["ranked"][0]["file"] == "services/pricing.py"
    assert out["ranked"][-1]["file"] == "docs/README.md"
    assert "services/pricing.py" in out["in_trace"]


def test_rank_suspects_rejects_empty_files():
    with pytest.raises(ToolError):
        call("rank_suspects", frames=[], changed_files=[])


def test_compare_environments_ranks_major_version_first():
    out = call(
        "compare_environments",
        working={"python": "3.11.4", "TZ": "UTC", "requests": "2.31.0", "DEBUG": "1", "API_KEY": "abc"},
        broken={"python": "3.11.6", "TZ": "America/New_York", "requests": "3.0.1", "API_KEY": ""},
    )
    assert out["identical"] == 0
    assert out["differences"][0]["key"] == "requests"
    assert out["differences"][0]["weight"] >= 90
    keys = [d["key"] for d in out["differences"]]
    assert keys.index("TZ") < keys.index("python")
    api = next(d for d in out["differences"] if d["key"] == "API_KEY")
    assert api["working"] == "<set>" and api["broken"] == "<missing>"


def test_compare_environments_rejects_empty():
    with pytest.raises(ToolError):
        call("compare_environments", working={}, broken={})


def test_parse_node_async_and_internal_frames():
    trace = """TypeError: Cannot read properties of undefined (reading 'map')
    at formatLineItems (/app/src/format.js:23:28)
    at async InvoiceService.send (/app/src/service.js:112:21)
    at async /app/src/routes.js:34:5
    at process.processTicksAndRejections (node:internal/process/task_queues:95:5)
"""
    out = call("parse_stack_trace", trace=trace)
    assert [(f["file"], f["line"]) for f in out["frames"]] == [
        ("/app/src/format.js", 23), ("/app/src/service.js", 112), ("/app/src/routes.js", 34), ("node:internal/process/task_queues", 95)]
    assert out["frames"][-1]["in_user_code"] is False
    assert "undefined/null" in out["hint"]


def test_python_implicit_chain_final_exception_is_the_bug():
    trace = """Traceback (most recent call last):
  File "/srv/app/cache.py", line 10, in get
    return self._d[k]
KeyError: 'x'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/srv/app/cache.py", line 12, in get
    return self.db.load(k).value
AttributeError: 'NoneType' object has no attribute 'value'
"""
    out = call("parse_stack_trace", trace=trace)
    assert out["chain_kind"] == "implicit"
    assert out["root_cause_exception"]["type"] == "AttributeError"


def test_cluster_logs_surfaces_the_deploy_before_the_first_error():
    logs = "\n".join(["10:00:01 INFO request ok"] * 40 + ["10:00:05 INFO deployed api v42", "10:00:07 ERROR boom id=1", "10:00:08 ERROR boom id=2"])
    out = call("cluster_logs", logs=logs)
    assert out["changes_before_first_problem"][-1]["line"] == 41
    assert "deployed api v42" in out["verdict"]

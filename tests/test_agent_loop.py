"""Tests for agent_loop.py — the shared tool-calling loops.

Both run_openai_compatible and run_anthropic just orchestrate a client; we
fake the client's shape rather than hitting any network/API.
"""

import json

import pytest

from agent_loop import run_anthropic, run_openai_compatible


# ── run_openai_compatible ────────────────────────────────────────────────
#
# Contract: client.chat.completions.create(...) -> resp with
# resp.choices[0].message.content / .tool_calls, and each tool_call has
# .id / .function.name / .function.arguments (a JSON string).


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = FakeFunction(name, arguments)


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class FakeChoice:
    def __init__(self, message):
        self.message = message


class FakeResponse:
    def __init__(self, message):
        self.choices = [FakeChoice(message)]


class FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeChat:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)


class FakeOpenAIClient:
    def __init__(self, responses):
        self.chat = FakeChat(responses)


def test_no_tool_call_returns_text_reply():
    client = FakeOpenAIClient([FakeResponse(FakeMessage(content="Hello there"))])
    result = run_openai_compatible(
        client, "model", "system prompt", [], dispatch=lambda name, args: "unused",
        user_content="hi",
    )
    assert result == "Hello there"
    assert len(client.chat.completions.calls) == 1
    assert client.chat.completions.calls[0]["model"] == "model"


def test_tool_call_round_dispatches_then_returns_final_text():
    tool_call = FakeToolCall("call-1", "search_emails", json.dumps({"query": "amazon"}))
    responses = [
        FakeResponse(FakeMessage(content=None, tool_calls=[tool_call])),
        FakeResponse(FakeMessage(content="Found your order.", tool_calls=None)),
    ]
    client = FakeOpenAIClient(responses)
    dispatched = []

    def dispatch(name, args):
        dispatched.append((name, args))
        return "tool result text"

    result = run_openai_compatible(
        client, "model", "system", [], dispatch=dispatch, user_content="where's my order?",
    )
    assert result == "Found your order."
    assert dispatched == [("search_emails", {"query": "amazon"})]
    # Second API call's messages should include the tool result appended.
    assert len(client.chat.completions.calls) == 2
    second_call_messages = client.chat.completions.calls[1]["messages"]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert tool_messages == [
        {"role": "tool", "tool_call_id": "call-1", "content": "tool result text"}
    ]


def test_json_decode_error_arguments_become_empty_dict():
    tool_call = FakeToolCall("call-1", "search_emails", "not valid json{{{")
    responses = [
        FakeResponse(FakeMessage(content=None, tool_calls=[tool_call])),
        FakeResponse(FakeMessage(content="done", tool_calls=None)),
    ]
    client = FakeOpenAIClient(responses)
    dispatched = []

    def dispatch(name, args):
        dispatched.append((name, args))
        return "ok"

    run_openai_compatible(client, "model", "system", [], dispatch=dispatch, user_content="hi")
    assert dispatched == [("search_emails", {})]


def test_turn_limit_returns_warning():
    tool_call = FakeToolCall("call-x", "search_emails", "{}")
    # Every response keeps calling a tool, never finishing — with max_turns=2
    # the loop should bail out with the warning instead of looping forever.
    responses = [
        FakeResponse(FakeMessage(content=None, tool_calls=[tool_call])) for _ in range(2)
    ]
    client = FakeOpenAIClient(responses)
    result = run_openai_compatible(
        client, "model", "system", [], dispatch=lambda name, args: "result",
        user_content="hi", max_turns=2,
    )
    assert result == "Reached the turn limit before the agent finished."
    assert len(client.chat.completions.calls) == 2


def test_history_is_prepended_before_user_content():
    client = FakeOpenAIClient([FakeResponse(FakeMessage(content="ok"))])
    history = [{"role": "user", "content": "earlier question"}, {"role": "assistant", "content": "earlier answer"}]
    run_openai_compatible(
        client, "model", "system", [], dispatch=lambda name, args: "unused",
        user_content="new question", history=history,
    )
    assert len(client.chat.completions.calls) == 1
    messages = client.chat.completions.calls[0]["messages"]
    contents = [m.get("content") for m in messages]
    assert "earlier question" in contents
    assert "earlier answer" in contents
    # The user turn is the last thing sent in the request; the loop appends
    # the assistant's reply to `messages` only *after* the call returns.
    assert contents[contents.index("new question") + 1] == "ok"
    assert contents.index("earlier question") < contents.index("earlier answer") < contents.index("new question")


# ── run_anthropic ─────────────────────────────────────────────────────────
#
# Contract: client.beta.messages.tool_runner(...) returns an iterable of
# messages, each with .content -> list of blocks with .type/.text.


class FakeBlock:
    def __init__(self, type, text=None):
        self.type = type
        self.text = text


class FakeAnthropicMessage:
    def __init__(self, content):
        self.content = content


class FakeToolRunner:
    def __init__(self, messages, calls):
        self._messages = messages
        self._calls = calls

    def __call__(self, **kwargs):
        self._calls.append(kwargs)
        return iter(self._messages)


class FakeBetaMessages:
    def __init__(self, runner):
        self.tool_runner = runner


class FakeBeta:
    def __init__(self, runner):
        self.messages = FakeBetaMessages(runner)


class FakeAnthropicClient:
    def __init__(self, messages):
        self._calls = []
        self.beta = FakeBeta(FakeToolRunner(messages, self._calls))


def test_run_anthropic_collects_text_blocks_and_ignores_others():
    messages = [
        FakeAnthropicMessage(content=[FakeBlock("tool_use"), FakeBlock("text", "Part one.")]),
        FakeAnthropicMessage(content=[FakeBlock("text", "Part two.")]),
    ]
    client = FakeAnthropicClient(messages)
    result = run_anthropic(client, "model", "system prompt", tools=[], user_content="hi")
    assert result == "Part one.\n\nPart two."


def test_run_anthropic_skips_blank_text_blocks():
    messages = [FakeAnthropicMessage(content=[FakeBlock("text", "   ")])]
    client = FakeAnthropicClient(messages)
    result = run_anthropic(client, "model", "system", tools=[], user_content="hi")
    assert result == ""


def test_run_anthropic_passes_history_and_user_content_through():
    messages = [FakeAnthropicMessage(content=[FakeBlock("text", "answer")])]
    client = FakeAnthropicClient(messages)
    history = [{"role": "user", "content": "earlier"}]
    run_anthropic(client, "model", "system", tools=[], user_content="new", history=history)
    calls = client.beta.messages.tool_runner._calls
    assert len(calls) == 1
    assert calls[0]["messages"] == [{"role": "user", "content": "earlier"}, {"role": "user", "content": "new"}]

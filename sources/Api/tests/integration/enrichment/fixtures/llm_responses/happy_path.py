"""Pre-recorded LLM response sequences for E2E tests.

Each function returns a list of mock LLM responses to feed to the agent loop.
"""

from types import SimpleNamespace


def _resp(stop: str, tool_uses=None, in_t: int = 200, out_t: int = 200):
    """Build a mock LLM response block."""
    blocks = []
    for tu in (tool_uses or []):
        blocks.append(SimpleNamespace(
            type="tool_use",
            id=tu["id"],
            name=tu["name"],
            input=tu.get("input", {}),
        ))
    return SimpleNamespace(
        stop_reason=stop,
        content=blocks,
        usage=SimpleNamespace(input_tokens=in_t, output_tokens=out_t),
    )


def happy_path_responses():
    """3-turn sequence: grep → read_file → emit_node → end_turn."""
    return [
        _resp("tool_use", tool_uses=[
            {"id": "g1", "name": "grep",
             "input": {"pattern": "acme-payments", "path": "."}},
        ]),
        _resp("tool_use", tool_uses=[
            {"id": "r1", "name": "read_file",
             "input": {"path": "app/main.py"}},
        ]),
        _resp("tool_use", tool_uses=[
            {"id": "e1", "name": "emit_node",
             "input": {
                 "type": "external_dep",
                 "name": "Acme Payments",
                 "props": {
                     "confidence": 0.9,
                     "dep_type": "payment",
                     "evidence": [
                         {"file": "app/main.py", "line": 3,
                          "snippet": "http.post(...)"}
                     ],
                 },
             }},
        ]),
        _resp("end_turn"),
    ]


def budget_exceeded_responses():
    """Burn through max_tool_calls to trigger budget_exceeded."""
    return [
        _resp("tool_use", tool_uses=[
            {"id": f"g{i}", "name": "grep", "input": {"pattern": f"pattern{i}", "path": "."}}
        ])
        for i in range(25)  # exceeds max_tool_calls=20
    ] + [_resp("end_turn")]


def no_tool_calls_responses():
    """LLM responds without calling any tools."""
    return [_resp("end_turn")]
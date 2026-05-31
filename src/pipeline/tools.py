"""Stubbed tool interface.

Sprint engineer: replace these stubs with real implementations.
Each tool function takes a dict input and returns a dict output.
The status field in trajectory records tracks whether a tool was
executed ("executed") or returned a canned response ("stubbed").

Extension point: add new tools by defining a function with the
signature (input: dict) -> dict and registering it in TOOL_REGISTRY.
"""


def retrieval_stub(input: dict) -> dict:
    query = input.get("query", "")
    return {
        "results": [
            {"content": f"[STUB] Retrieved document for: {query}", "score": 0.95}
        ],
        "status": "stubbed",
    }


def code_execution_stub(input: dict) -> dict:
    code = input.get("code", "")
    return {
        "stdout": f"[STUB] Would execute: {code[:100]}",
        "stderr": "",
        "exit_code": 0,
        "status": "stubbed",
    }


TOOL_REGISTRY = {
    "retrieval": retrieval_stub,
    "code_execution": code_execution_stub,
}


def call_tool(tool_name: str, input: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {tool_name}", "status": "error"}
    return TOOL_REGISTRY[tool_name](input)

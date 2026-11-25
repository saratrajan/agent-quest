"""Session 9: the tool loop, written by you.

A language model can only produce text. "Calling a tool" means: the model
writes a small structured request naming a function and its arguments; YOUR
code runs the function; the result goes back into the conversation as one
more message; and the model carries on from there. That is the whole
mechanism behind every agent, and it is about thirty lines.

Fill the four gaps marked YOUR CODE (about 30 lines in total).
"""
import json


def tool_spec(name: str, description: str, parameters: dict[str, str]) -> dict:
    """Describe one tool to the model, in the JSON Schema form models are trained on.

    parameters maps each argument name to a sentence describing it. Treat
    every argument as a required string. The result must look like this:

        {"type": "function",
         "function": {"name": name, "description": description,
                      "parameters": {"type": "object",
                                     "properties": {"<arg>": {"type": "string", "description": "<sentence>"}, ...},
                                     "required": ["<arg>", ...]}}}
    """
    # >>> YOUR CODE (about 6 lines)
    raise NotImplementedError("tool_spec is yours to write")
    # <<< YOUR CODE


def clip(text: str, max_chars: int) -> str:
    """Keep a tool result within a budget. If text is longer than max_chars,
    return its first max_chars characters followed by
    "\n[cut: N more characters]" where N is how many were dropped.
    Otherwise return it unchanged. Everything a tool returns is paid for in
    context-window tokens on every later step."""
    # >>> YOUR CODE (about 3 lines)
    raise NotImplementedError("clip is yours to write")
    # <<< YOUR CODE


def run_tool(call: dict, tools: dict, max_chars: int = 2000) -> str:
    """Carry out one tool call and return what the model should read next.

    call is {"function": {"name": "...", "arguments": {...}}} as the model
    produced it. tools maps tool names to Python functions.
    Return the function's result as a JSON string, clipped to max_chars.

    Never raise. The model wrote this call, so it can be wrong in any way:
    a tool that does not exist, missing or misnamed arguments, an id that is
    not found. In each case return a JSON string {"error": "..."} that says
    what went wrong (for an unknown tool, include the names that do exist),
    so the model can read it and try again.
    """
    # >>> YOUR CODE (about 9 lines)
    raise NotImplementedError("run_tool is yours to write")
    # <<< YOUR CODE


def tool_loop(messages: list[dict], tools: dict, specs: list[dict], chat, max_steps: int = 6) -> str | None:
    """Run the conversation until the model answers in words.

    chat(messages, tools=specs) sends the conversation and returns
    {"message": {...}}. The message is the model's turn: it has "content",
    and when the model wants tools, a "tool_calls" list.

    Each step:
      1. call chat, and append the model's message to messages;
      2. if it has no tool calls, return its content: that is the answer;
      3. otherwise run every call with run_tool and append one message per
         result: {"role": "tool", "tool_name": <name>, "content": <result>}.
    After max_steps model turns without an answer, return None. A loop that
    cannot stop is the first thing that goes wrong with an agent.
    messages is changed in place, so the caller keeps the full transcript.
    """
    # >>> YOUR CODE (about 10 lines)
    raise NotImplementedError("tool_loop is yours to write")
    # <<< YOUR CODE

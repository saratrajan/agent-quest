"""Given: a small client for the model running locally under Ollama.

    from ollama_client import generate
    r = generate("Why is the sky blue?", temperature=0.2, num_ctx=4096)
    r["text"], r["output_tokens"], r["tokens_per_second"]

Nothing here needs to be edited. Read it: it is 40 lines and shows exactly
what goes over the wire.
"""
import json
import urllib.error
import urllib.request

HOST = "http://localhost:11434"
MODEL = "qwen3:4b"


def generate(prompt: str, model: str = MODEL, host: str = HOST, json_output: bool = False,
             think: bool = True, timeout: int = 300, **options) -> dict:
    """Send one prompt and wait for the whole answer.

    Any extra keyword goes to the model as a sampling or runtime option:
    temperature, top_k, top_p, num_ctx (context window), num_predict (output limit), seed.
    Returns the answer text, the model's separate "thinking" text, token counts and speed.

    think=True lets the model reason before answering. That reasoning is
    returned separately but its tokens are generated, counted and waited for
    like any others: often over a thousand of them for a one-line answer.
    think=False with json_output=True gives a short, direct, structured answer.
    """
    body = {"model": model, "prompt": prompt, "stream": False, "think": think, "options": options}
    if json_output:
        body["format"] = "json"
    request = urllib.request.Request(f"{host}/api/generate", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:200]
        if err.code == 404:
            raise RuntimeError(f"Ollama does not have the model '{model}'. Fetch it with: ollama pull {model}") from None
        raise RuntimeError(f"Ollama answered with an error ({err.code}): {detail}") from None
    except (urllib.error.URLError, OSError):
        raise RuntimeError(f"Could not reach Ollama at {host}. Open the Ollama app, or run: ollama serve") from None
    seconds = data.get("eval_duration", 0) / 1e9
    out = data.get("eval_count", 0)
    return {"text": (data.get("response") or "").strip(), "thinking": (data.get("thinking") or "").strip(),
            "prompt_tokens": data.get("prompt_eval_count", 0), "output_tokens": out,
            "seconds": round(seconds, 2), "tokens_per_second": round(out / seconds, 1) if seconds else 0.0}

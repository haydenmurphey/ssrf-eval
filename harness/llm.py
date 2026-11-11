"""The single place LiteLLM is called. The mock model substitutes for this."""
import litellm


def complete(model_spec: dict, messages: list, tools: list):
    """Call the model and return (assistant_message, usage_dict, finish_reason).

    `model_spec` is an entry from config.MODELS. `assistant_message` is the raw
    LiteLLM message object (has `.content` and `.tool_calls`). `finish_reason`
    lets the loop distinguish a safety block ("content_filter") from a normal
    answer — e.g. Gemini's filter returns empty content with this reason.
    """
    kwargs = dict(model_spec)
    response = litellm.completion(
        messages=messages,
        tools=tools,
        tool_choice="auto",
        **kwargs,
    )
    choice = response.choices[0]
    usage = getattr(response, "usage", None)
    usage_dict = {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
    return choice.message, usage_dict, choice.finish_reason

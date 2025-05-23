from typing import TypedDict


class ModelSpec(TypedDict):
    title: str
    pricing: dict[str, float]
    cache_pricing: dict[str, float]
    max_tokens: int
    context_window: int


MODEL_MAP: dict[str, ModelSpec] = {
    "opus": {
        "title": "claude-opus-4-20250514",
        "pricing": {"input": 15.00, "output": 18.75},
        "cache_pricing": {"write": 3.75, "read": 0.30},
        "max_tokens": 8192,
        "context_window": 200000,  # 200k tokens context window
    },
    "sonnet": {
        "title": "claude-sonnet-4-20250514",
        "pricing": {"input": 3.00, "output": 15.00},
        "cache_pricing": {"write": 3.75, "read": 0.30},
        "max_tokens": 8192,
        "context_window": 200000,  # 200k tokens context window
    },
    "haiku": {
        "title": "claude-3-5-haiku-20241022",
        "pricing": {"input": 0.80, "output": 4.00},
        "cache_pricing": {"write": 1.00, "read": 0.08},
        "max_tokens": 8192,
        "context_window": 100000,  # 100k tokens context window
    },
}

# pivot on model ids as well
_KEY_MAP = {model.get("title"): model for model in MODEL_MAP.values()}

_ALL_ALIASES = _KEY_MAP | MODEL_MAP


def model_names() -> list[str]:
    return list(_ALL_ALIASES.keys())


def get_model(model_name: str) -> ModelSpec:
    if model_name not in _ALL_ALIASES:
        raise ValueError(f"{model_name} is not a valid model name")
    return _ALL_ALIASES[model_name]

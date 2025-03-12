from heare.developer.context import ModelSpec

MODEL_MAP: dict[str, ModelSpec] = {
    "sonnet-3.7": {
        "title": "claude-3-7-sonnet-latest",
        "pricing": {"input": 3.00, "output": 15.00},
        "cache_pricing": {"write": 3.75, "read": 0.30},
        "max_tokens": 8192,
    },
    "sonnet-3.5": {
        "title": "claude-3-5-sonnet-latest",
        "pricing": {"input": 3.00, "output": 15.00},
        "cache_pricing": {"write": 3.75, "read": 0.30},
        "max_tokens": 8192,
    },
    "haiku": {
        "title": "claude-3-5-haiku-20241022",
        "pricing": {"input": 0.80, "output": 4.00},
        "cache_pricing": {"write": 1.00, "read": 0.08},
        "max_tokens": 8192,
    },
}

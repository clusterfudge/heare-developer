from heare.developer.sandbox import Sandbox


def build_tree(sandbox: Sandbox):
    root = {"is_leaf": False}

    for path in sandbox.get_directory_listing():
        parts = path.split("/")
        current = root

        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # It's a file
                current[part] = {"path": path, "is_leaf": True}
            else:  # It's a directory
                if part not in current:
                    current[part] = {"is_leaf": False}
                current = current[part]

    return root


_STRUCT_KEYS = {"path", "is_leaf"}


def render_tree(tree, indent=""):
    result = ""
    for key, value in sorted(tree.items()):
        if key in _STRUCT_KEYS:
            continue
        if isinstance(value, dict):
            is_leaf = value.get("is_leaf", False)
            if not is_leaf:
                result += f"{indent}{key}/\n"
                result += render_tree(value, indent + "  ")
            else:
                result += f"{indent}{key}\n"
        else:
            result += f"{indent}{key}\n"
    return result


def render_sandbox_content(sandbox, summarize):
    tree = build_tree(sandbox)
    result = "<sandbox_contents>\n"
    result += render_tree(tree)
    result += "</sandbox_contents>\n"
    return result


def create_system_message(sandbox, MAX_ESTIMATED_TOKENS=10_240):
    system_message = "You are an AI assistant with access to a sandbox environment. The current contents of the sandbox are:\n"
    sandbox_content = render_sandbox_content(sandbox, False)
    if estimate_token_count(sandbox_content) > MAX_ESTIMATED_TOKENS:
        sandbox_content = render_sandbox_content(sandbox, True)

    system_message += sandbox_content
    system_message += "\nYou can read, write, and list files/directories, as well as execute some bash commands."

    return system_message


def estimate_token_count(text):
    """
    Estimate the number of tokens in a given text.
    This is a rough estimate based on word count and should not be considered exact.
    """
    words = text.split()
    estimated_tokens = int(len(words) * 1.3)
    return estimated_tokens

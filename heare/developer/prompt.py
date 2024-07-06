import os
from collections import defaultdict

from heare.developer.sandbox import Permission
from heare.developer.summarize import summarize_file


def build_tree(sandbox):
    tree = defaultdict(lambda: defaultdict(dict))
    cwd = os.getcwd()

    for file_path, permission in sandbox.list_sandbox():
        relative_path = os.path.relpath(file_path, cwd)
        parts = relative_path.split(os.sep)
        current = tree
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = {"path": relative_path, "permission": permission}

    return dict(tree)


_STRUCT_KEYS = {'path', 'permission'}

def render_tree(tree, indent=""):
    result = ""
    for key, value in sorted(tree.items()):
        if key in _STRUCT_KEYS:
            continue
        if isinstance(value, dict):
            is_leaf = value.keys() == _STRUCT_KEYS if isinstance(value, dict) else True
            if not is_leaf:
                result += f"{indent}{key}/\n"
                result += render_tree(value, indent + "  ")
            else:
                result += f"{indent}{key} ({value['permission']})\n"
        else:
            result += f"{indent}{key} ({Permission.LIST})\n"
    return result


def render_sandbox_content(sandbox, summarize):
    tree = build_tree(sandbox)
    result = "<sandbox_contents>\n"
    result += render_tree(tree)
    result += "</sandbox_contents>\n"
    return result


def create_system_message(sandbox, MAX_ESTIMATED_TOKENS=10_240):
    system_message = f"You are an AI assistant with access to a sandbox environment. The current contents of the sandbox are:\n"
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
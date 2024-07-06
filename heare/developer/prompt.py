import os

from heare.developer.summarize import summarize_file


def render_sandbox_content(sandbox, summarize):
    cwd = os.getcwd()

    result = "<sandbox_contents>\n"
    for file_path, permission in sandbox.list_sandbox():
        relative_path = os.path.relpath(file_path, cwd)
        try:
            file_content = sandbox.read_file(file_path)
            if summarize:  # Limit summary to about 500 tokens
                summary = summarize_file(file_content)
                result += f"<file path='{relative_path}' summarized='true' permission={permission}>\n"
                result += f"{summary}...\n"
            else:
                result += f"<file path='{relative_path}' summarized='false' permission={permission}>\n"
                result += f"{file_content}\n"
        except Exception as e:
            result += f"<file path='{relative_path}' summarized='false' permission={permission}>\n"
            result += f"Unable to read file: {str(e)}\n"

        result += "</file>\n"
    result += "</sandbox_contents>\n"
    return result


def create_system_message(sandbox, MAX_ESTIMATED_TOKENS=10_240):
    system_message = f"You are an AI assistant with access to a sandbox environment. The current contents of the sandbox are:\n"
    cwd = os.getcwd()
    sandbox_content = render_sandbox_content(sandbox, False)
    if estimate_token_count(sandbox_content):
        sandbox_content = render_sandbox_content(sandbox, True)

    system_message += sandbox_content
    system_message += "\nYou can read, write, and list files/directories, as well as execute some bash commands."
    
    return system_message

def estimate_token_count(text):
    """
    Estimate the number of tokens in a given text.
    This is a rough estimate based on word count and should not be considered exact.
    """
    # Split the text into words
    words = text.split()
    
    # Estimate tokens based on word count
    # On average, one word is about 1.3 tokens in many language models
    estimated_tokens = int(len(words) * 1.3)
    
    return estimated_tokens
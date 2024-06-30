import os

def create_system_message(sandbox):
    system_message = f"You are an AI assistant with access to a sandbox environment. The current contents of the sandbox are:\n"
    
    system_message += "<sandbox_contents>\n"
    cwd = os.getcwd()
    for file_path in sandbox.list_sandbox():
        relative_path = os.path.relpath(file_path, cwd)
        try:
            file_content = sandbox.read_file(file_path)
            total_tokens = estimate_token_count(file_content)
            
            if total_tokens > 500:  # Limit summary to about 500 tokens
                words = file_content.split()
                summary = ' '.join(words[:385])  # Approximately 500 tokens
                system_message += f"<file path='{relative_path}' summarized='true'>\n"
                system_message += f"{summary}...\n"
            else:
                system_message += f"<file path='{relative_path}' summarized='false'>\n"
                system_message += f"{file_content}\n"
        except Exception as e:
            system_message += f"<file path='{relative_path}' summarized='false'>\n"
            system_message += f"Unable to read file: {str(e)}\n"
        
        system_message += "</file>\n"
    system_message += "</sandbox_contents>\n"

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
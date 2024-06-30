def create_system_message(sandbox):
    system_message = f"You are an AI assistant with access to a sandbox environment. The current contents of the sandbox are\n"
    for line in sandbox.list_sandbox():
        system_message += line + "\n"

    system_message += "\nYou can read, write, and list files/directories, as well as execute some bash commands."
    
    return system_message
import inspect

class CLITools:
    def __init__(self):
        self.tools = {}

    def tool(self, func):
        tool_name = func.__name__
        tool_args = inspect.signature(func).parameters
        tool_docstring = inspect.getdoc(func)
        self.tools[tool_name] = {
            "name": tool_name,
            "args": tool_args,
            "docstring": tool_docstring,
            "invoke": func,
        }
        return func

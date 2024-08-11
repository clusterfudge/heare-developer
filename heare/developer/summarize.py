"""
This module provides functionality for summarizing code files.
"""

import ast
import re


def summarize_file(file_content):
    """
    Summarize the content of a file.

    Args:
    file_content (str): The content of the file to summarize.

    Returns:
    str: A summary of the file content.
    """
    summary = []
    key_elements = extract_key_elements(file_content)
    structure_analysis = analyze_code_structure(file_content)

    summary.append("File Structure:")
    summary.append(f"  Lines of code: {structure_analysis['loc']}")
    summary.append(f"  Number of classes: {structure_analysis['num_classes']}")
    summary.append(f"  Number of functions: {structure_analysis['num_functions']}")
    if structure_analysis["has_main"]:
        summary.append("  Contains main execution block")
    summary.append("")

    if key_elements["file_docstring"]:
        summary.append(f"File Docstring: {key_elements['file_docstring']}\n")

    if key_elements["imports"]:
        summary.append("Imports:")
        summary.extend(f"  - {imp}" for imp in key_elements["imports"])

    if key_elements["classes"]:
        summary.append("\nClasses:")
        for cls in key_elements["classes"]:
            summary.append(f"  - {cls['name']}")
            if cls["docstring"]:
                summary.append(f"    Docstring: {cls['docstring']}")
            if cls["methods"]:
                summary.append("    Methods:")
                for method in cls["methods"]:
                    summary.append(f"      - {method['name']}")
                    if method["docstring"]:
                        summary.append(f"        Docstring: {method['docstring']}")
            if cls["class_vars"]:
                summary.append("    Class Variables:")
                summary.extend(f"      - {var}" for var in cls["class_vars"])

    if key_elements["functions"]:
        summary.append("\nFunctions:")
        for func in key_elements["functions"]:
            summary.append(f"  - {func['name']}({', '.join(func['params'])})")
            if func["returns"]:
                summary.append(f"    Returns: {func['returns']}")
            if func["docstring"]:
                summary.append(f"    Docstring: {func['docstring']}")

    if key_elements["global_vars"]:
        summary.append("\nGlobal Variables:")
        summary.extend(f"  - {var}" for var in key_elements["global_vars"])

    return "\n".join(summary)


def extract_key_elements(file_content):
    """
    Extract key elements from the file content.

    Args:
    file_content (str): The content of the file to analyze.

    Returns:
    dict: A dictionary containing key elements of the file.
    """
    tree = ast.parse(file_content)

    imports = []
    classes = []
    functions = []
    global_vars = []
    file_docstring = extract_docstring(tree)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            imports.extend(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(f"{node.module}.{node.names[0].name}")
        elif isinstance(node, ast.ClassDef):
            methods = []
            class_vars = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(
                        {"name": item.name, "docstring": extract_docstring(item)}
                    )
                elif isinstance(item, ast.Assign):
                    class_vars.extend(
                        t.id for t in item.targets if isinstance(t, ast.Name)
                    )
            classes.append(
                {
                    "name": node.name,
                    "docstring": extract_docstring(node),
                    "methods": methods,
                    "class_vars": class_vars,
                }
            )
        elif isinstance(node, ast.FunctionDef):
            params = [a.arg for a in node.args.args]
            returns = (
                node.returns.id
                if node.returns and hasattr(node.returns, "id")
                else None
            )
            functions.append(
                {
                    "name": node.name,
                    "params": params,
                    "returns": returns,
                    "docstring": extract_docstring(node),
                }
            )
        elif isinstance(node, ast.Assign) and all(
            isinstance(t, ast.Name) for t in node.targets
        ):
            global_vars.extend(t.id for t in node.targets)

    return {
        "file_docstring": file_docstring,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "global_vars": global_vars,
    }


def extract_docstring(node):
    """
    Extract the docstring from an AST node.

    Args:
    node (ast.AST): The AST node to extract the docstring from.

    Returns:
    str: The docstring of the node, or None if no docstring is found.
    """
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
        if (docstring := ast.get_docstring(node)) is not None:
            return re.sub(r"\s+", " ", docstring).strip()
    return None


def analyze_code_structure(file_content):
    """
    Analyze the overall structure of the code.

    Args:
    file_content (str): The content of the file to analyze.

    Returns:
    dict: A dictionary containing structural information about the code.
    """
    tree = ast.parse(file_content)

    loc = len(file_content.splitlines())
    num_classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
    num_functions = sum(
        1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    )

    has_main = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
        and isinstance(node.test.comparators[0], ast.Str)
        and node.test.comparators[0].s == "__main__"
        for node in ast.iter_child_nodes(tree)
    )

    return {
        "loc": loc,
        "num_classes": num_classes,
        "num_functions": num_functions,
        "has_main": has_main,
    }


# Add more functions as needed for summarization tasks

import os
import pathlib
import shutil

class Sandbox:
    def __init__(self, *sandbox_paths):
        self.sandbox_paths = [pathlib.Path(path).resolve() for path in sandbox_paths]

    def _is_in_sandbox(self, file_path):
        resolved_path = pathlib.Path(file_path).resolve()
        return any(sandbox_path in resolved_path.parents or resolved_path == sandbox_path 
                   for sandbox_path in self.sandbox_paths)

    def add_to_sandbox(self, path):
        resolved_path = pathlib.Path(path).resolve()
        if not resolved_path.exists():
            raise ValueError(f"Path does not exist: {path}")
        self.sandbox_paths.append(resolved_path)

    def remove_from_sandbox(self, path):
        resolved_path = pathlib.Path(path).resolve()
        if resolved_path in self.sandbox_paths:
            self.sandbox_paths.remove(resolved_path)
        else:
            raise ValueError(f"Path is not in sandbox: {path}")

    def create_file(self, file_path, content=''):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot create file outside of sandbox: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)

    def read_file(self, file_path):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot read file outside of sandbox: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        with open(full_path, 'r') as f:
            return f.read()

    def open_file(self, file_path, mode='r'):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot open file outside of sandbox: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        return open(full_path, mode)

    def list_directory(self, path):
        if not self._is_in_sandbox(path):
            raise ValueError(f"Cannot read file outside of sandbox: {path}")

        return '\n'.join([path.name for path in pathlib.Path(path).iterdir()])

    def list_sandbox(self, allowed_extensions=None, excluded_directories=None):
        if allowed_extensions is None:
            allowed_extensions = ['.py', '.md']
        if excluded_directories is None:
            excluded_directories = ['.git', '.venv', 'venv', '.idea']
        files_and_dirs = []
        for sandbox_path in self.sandbox_paths:
            if os.path.isdir(sandbox_path):
                for root, dirs, files in os.walk(sandbox_path):
                    dirs[:] = [d for d in dirs if d not in excluded_directories] 
                    files_and_dirs.extend([os.path.join(root, d) for d in dirs])
                    files_and_dirs.extend([os.path.join(root, f) for f in files if os.path.splitext(f)[1] in allowed_extensions])
            elif os.path.isfile(sandbox_path) and os.path.splitext(sandbox_path)[1] in allowed_extensions:
                files_and_dirs.append(str(sandbox_path))
        return files_and_dirs

    def write_file(self, file_path, content):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot read file outside of sandbox: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        with open(full_path, 'w') as f:
            return f.write(content)


    def remove_file_or_dir(self, path):
        if not self._is_in_sandbox(path):
            raise ValueError(f"Cannot remove item outside of sandbox: {path}")
        full_path = pathlib.Path(path).resolve()
        if full_path.is_file():
            os.remove(full_path)
        elif full_path.is_dir():
            shutil.rmtree(full_path)
        else:
            raise ValueError(f"Path is neither a file nor a directory: {path}")
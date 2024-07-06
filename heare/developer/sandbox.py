import os
import pathlib
import shutil
from enum import Flag, auto
import pathlib

class Permission(Flag):
    NONE = 0
    LIST = auto()
    READ = auto()
    WRITE = auto()

class Sandbox:
    def __init__(self, *sandbox_paths):
        self.sandbox_paths = [pathlib.Path(path).resolve() for path in sandbox_paths]
        self.permissions = {str(path): Permission.LIST for path in self.sandbox_paths}

    def _is_in_sandbox(self, file_path):
        resolved_path = pathlib.Path(file_path).resolve()
        return any(sandbox_path in resolved_path.parents or resolved_path == sandbox_path
                   for sandbox_path in self.sandbox_paths)

    def _get_permission(self, path):
        resolved_path = str(pathlib.Path(path).resolve())
        applicable_perms = Permission.NONE
        for sandbox_path, perm in self.permissions.items():
            if resolved_path.startswith(sandbox_path):
                applicable_perms |= perm
        return applicable_perms

    def get_permissions(self, path):
        if not self._is_in_sandbox(path):
            raise ValueError(f"Path is not in sandbox: {path}")
        return self._get_permission(path)

    def set_permissions(self, path, permissions):
        if not self._is_in_sandbox(path):
            raise ValueError(f"Path is not in sandbox: {path}")
        resolved_path = str(pathlib.Path(path).resolve())
        self.permissions[resolved_path] = permissions

    def grant_permission(self, path, permission):
        current_permissions = self.get_permissions(path)
        self.set_permissions(path, current_permissions | permission)

    def revoke_permission(self, path, permission):
        current_permissions = self.get_permissions(path)
        self.set_permissions(path, current_permissions & ~permission)

    def list_sandbox(self, allowed_extensions=None, excluded_directories=None):
        if allowed_extensions is None:
            allowed_extensions = ['.py', '.md', '.txt']  # Added .txt for test files
        if excluded_directories is None:
            excluded_directories = ['.git', '.venv', 'venv', '.idea']
        files_and_permissions = []
        for sandbox_path in self.sandbox_paths:
            if Permission.LIST not in self._get_permission(sandbox_path):
                continue
            if os.path.isdir(sandbox_path):
                files_and_permissions.append((str(sandbox_path), self._get_permission(sandbox_path)))
                for root, dirs, files in os.walk(sandbox_path):
                    dirs[:] = [d for d in dirs if d not in excluded_directories]
                    for d in dirs:
                        path = os.path.join(root, d)
                        files_and_permissions.append((str(pathlib.Path(path).resolve()), self._get_permission(path)))
                    for f in files:
                        if os.path.splitext(f)[1] in allowed_extensions:
                            path = os.path.join(root, f)
                            files_and_permissions.append((str(pathlib.Path(path).resolve()), self._get_permission(path)))
            elif os.path.isfile(sandbox_path) and os.path.splitext(sandbox_path)[1] in allowed_extensions:
                files_and_permissions.append((str(sandbox_path), self._get_permission(sandbox_path)))
        return files_and_permissions

    def create_file(self, file_path, content=''):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot create file outside of sandbox: {file_path}")
        if Permission.WRITE not in self._get_permission(file_path):
            raise PermissionError(f"No write permission for: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w') as f:
            f.write(content)

    def read_file(self, file_path):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot read file outside of sandbox: {file_path}")
        if Permission.READ not in self._get_permission(file_path):
            raise PermissionError(f"No read permission for: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        with open(full_path, 'r') as f:
            return f.read()

    def write_file(self, file_path, content):
        if not self._is_in_sandbox(file_path):
            raise ValueError(f"Cannot write file outside of sandbox: {file_path}")
        if Permission.WRITE not in self._get_permission(file_path):
            raise PermissionError(f"No write permission for: {file_path}")
        full_path = pathlib.Path(file_path).resolve()
        with open(full_path, 'w') as f:
            f.write(content)

    def remove_file_or_dir(self, path):
        if not self._is_in_sandbox(path):
            raise ValueError(f"Cannot remove item outside of sandbox: {path}")
        if Permission.WRITE not in self._get_permission(path):
            raise PermissionError(f"No write permission for: {path}")
        full_path = pathlib.Path(path).resolve()
        if full_path.is_file():
            os.remove(full_path)
        elif full_path.is_dir():
            shutil.rmtree(full_path)
        else:
            raise ValueError(f"Path is neither a file nor a directory: {path}")

    def add_to_sandbox(self, path, permission=Permission.LIST):
        resolved_path = pathlib.Path(path).resolve()
        if not resolved_path.exists():
            raise ValueError(f"Path does not exist: {path}")
        self.sandbox_paths.append(resolved_path)
        self.permissions[str(resolved_path)] = permission

    def remove_from_sandbox(self, path):
        resolved_path = pathlib.Path(path).resolve()
        if resolved_path in self.sandbox_paths:
            self.sandbox_paths.remove(resolved_path)
            del self.permissions[str(resolved_path)]
        else:
            raise ValueError(f"Path is not in sandbox: {path}")

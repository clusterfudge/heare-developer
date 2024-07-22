import os
from enum import Enum, auto
from typing import Dict

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern


class SandboxMode(Enum):
    REQUEST_EVERY_TIME = auto()
    REMEMBER_PER_RESOURCE = auto()
    REMEMBER_ALL = auto()
    ALLOW_ALL = auto()


class Sandbox:
    def __init__(self, root_directory: str, mode: SandboxMode):
        self.root_directory = os.path.abspath(root_directory)
        self.mode = mode
        self.permissions_cache = self._initialize_cache()
        self.gitignore_spec = self._load_gitignore()

    def _initialize_cache(self):
        if self.mode in [SandboxMode.REMEMBER_PER_RESOURCE, SandboxMode.REMEMBER_ALL]:
            return {}
        return None

    def _load_gitignore(self):
        gitignore_path = os.path.join(self.root_directory, '.gitignore')
        patterns = ['.git']  # Always ignore .git directory
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                patterns.extend([line.strip() for line in f if line.strip() and not line.startswith('#')])
        return PathSpec.from_lines(GitWildMatchPattern, patterns)

    def get_directory_listing(self):
        listing = []
        for root, dirs, files in os.walk(self.root_directory):
            # Remove ignored directories to prevent further traversal
            dirs[:] = [d for d in dirs if not self.gitignore_spec.match_file(os.path.join(root, d))]
            
            # Add non-ignored directories to the listing
            for d in dirs:
                full_path = os.path.join(root, d)
                rel_path = os.path.relpath(full_path, self.root_directory)
                if not self.gitignore_spec.match_file(rel_path):
                    listing.append(rel_path + '/')

            for item in files:
                full_path = os.path.join(root, item)
                rel_path = os.path.relpath(full_path, self.root_directory)
                if not self.gitignore_spec.match_file(rel_path):
                    listing.append(rel_path)

        return sorted(listing)

    def check_permissions(self, action: str, resource: str, action_arguments: Dict | None = None) -> bool:
        if self.mode == SandboxMode.ALLOW_ALL:
            return True

        key = f"{action}:{resource}"

        if self.mode == SandboxMode.REMEMBER_ALL:
            assert isinstance(self.permissions_cache, dict)
            if key in self.permissions_cache:
                return self.permissions_cache[key]
        elif self.mode == SandboxMode.REMEMBER_PER_RESOURCE:
            assert isinstance(self.permissions_cache, dict)
            if action in self.permissions_cache and resource in self.permissions_cache[action]:
                return self.permissions_cache[action][resource]

        # Request human input
        response = input(f"Allow {action} on {resource} with arguments {action_arguments}? (Y/N): ").lower()
        allowed = response == 'y'

        # Cache only affirmative responses based on the mode
        if allowed:
            if self.mode == SandboxMode.REMEMBER_PER_RESOURCE:
                assert isinstance(self.permissions_cache, dict)
                self.permissions_cache.setdefault(action, {})[resource] = True
            elif self.mode == SandboxMode.REMEMBER_ALL:
                assert isinstance(self.permissions_cache, dict)
                self.permissions_cache[key] = True

        return allowed

    def _is_path_in_sandbox(self, path):
        abs_path = os.path.abspath(path)
        return os.path.commonpath([abs_path, self.root_directory]) == self.root_directory

    def read_file(self, file_path):
        """
        Read the contents of a file within the sandbox.
        """
        if not self.check_permissions("read_file", file_path):
            raise PermissionError
        full_path = os.path.join(self.root_directory, file_path)
        if not self._is_path_in_sandbox(full_path):
            raise ValueError(f"File path {file_path} is outside the sandbox")

        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File {file_path} does not exist in the sandbox")

        with open(full_path, 'r') as file:
            return file.read()

    def write_file(self, file_path, content):
        """
        Write content to a file within the sandbox.
        """
        if not self.check_permissions("write_file", file_path, {'content': content}):
            raise PermissionError
        full_path = os.path.join(self.root_directory, file_path)
        if not self._is_path_in_sandbox(full_path):
            raise ValueError(f"File path {file_path} is outside the sandbox")

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as file:
            file.write(content)

    def create_file(self, file_path, content=''):
        """
        Create a new file within the sandbox with optional content.
        """
        if not self.check_permissions("write_file", file_path, {'content': content}):
            raise PermissionError
        full_path = os.path.join(self.root_directory, file_path)
        if not self._is_path_in_sandbox(full_path):
            raise ValueError(f"File path {file_path} is outside the sandbox")

        if os.path.exists(full_path):
            raise FileExistsError(f"File {file_path} already exists in the sandbox")

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w') as file:
            file.write(content)

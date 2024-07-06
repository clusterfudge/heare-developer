import unittest
import tempfile
import os
from heare.developer.sandbox import Sandbox, Permission
import pathlib


class TestSandboxPermissions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sandbox = Sandbox(self.temp_dir)

        # Create a test file structure
        self.test_file = os.path.join(self.temp_dir, 'test.txt')
        with open(self.test_file, 'w') as f:
            f.write('Test content')

        self.test_dir = os.path.join(self.temp_dir, 'test_dir')
        os.mkdir(self.test_dir)

        self.test_subfile = os.path.join(self.test_dir, 'subfile.txt')
        with open(self.test_subfile, 'w') as f:
            f.write('Subfile content')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_initial_permissions(self):
        """Test that initial permissions are set to LIST only"""
        perms = self.sandbox._get_permission(self.temp_dir)
        self.assertEqual(perms, Permission.LIST)

    def test_grant_permission(self):
        """Test granting a single permission"""
        self.sandbox.grant_permission(self.test_file, Permission.READ)
        perms = self.sandbox._get_permission(self.test_file)
        self.assertEqual(perms, Permission.LIST | Permission.READ)

    def test_grant_multiple_permissions(self):
        """Test granting multiple permissions"""
        self.sandbox.grant_permission(self.test_file, Permission.READ | Permission.WRITE)
        perms = self.sandbox._get_permission(self.test_file)
        self.assertEqual(perms, Permission.LIST | Permission.READ | Permission.WRITE)

    def test_recursive_permissions(self):
        """Test that granting permissions to a directory affects its contents"""
        self.sandbox.grant_permission(self.test_dir, Permission.READ)
        dir_perms = self.sandbox._get_permission(self.test_dir)
        file_perms = self.sandbox._get_permission(self.test_subfile)
        self.assertEqual(dir_perms, Permission.LIST | Permission.READ)
        self.assertEqual(file_perms, Permission.LIST | Permission.READ)

    def test_revoke_permission(self):
        """Test revoking a permission"""
        self.sandbox.grant_permission(self.test_file, Permission.READ | Permission.WRITE)
        self.sandbox.revoke_permission(self.test_file, Permission.WRITE)
        perms = self.sandbox._get_permission(self.test_file)
        self.assertEqual(perms, Permission.LIST | Permission.READ)

    def test_list_sandbox_with_permissions(self):
        """Test that list_sandbox returns correct permissions"""
        self.sandbox.grant_permission(self.test_file, Permission.READ)
        self.sandbox.grant_permission(self.test_dir, Permission.WRITE)

        sandbox_contents = self.sandbox.list_sandbox()

        expected_contents = [
            (str(pathlib.Path(self.temp_dir).resolve()), Permission.LIST),
            (str(pathlib.Path(self.test_file).resolve()), Permission.LIST | Permission.READ),
            (str(pathlib.Path(self.test_dir).resolve()), Permission.LIST | Permission.WRITE),
            (str(pathlib.Path(self.test_subfile).resolve()), Permission.LIST | Permission.WRITE)
        ]

        self.assertEqual(set(sandbox_contents), set(expected_contents))

    def test_permission_inheritance(self):
        """Test that new files/directories inherit permissions from their parent"""
        self.sandbox.grant_permission(self.test_dir, Permission.READ | Permission.WRITE)

        new_file = os.path.join(self.test_dir, 'new_file.txt')
        with open(new_file, 'w') as f:
            f.write('New file content')

        new_file_perms = self.sandbox._get_permission(new_file)
        self.assertEqual(new_file_perms, Permission.LIST | Permission.READ | Permission.WRITE)


if __name__ == '__main__':
    unittest.main()
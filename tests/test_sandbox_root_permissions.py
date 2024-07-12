import pytest
from heare.developer.sandbox import Sandbox, Permission

def test_add_file_to_root():
    sandbox = Sandbox('.')
    
    # Grant write permission to the root of the sandbox
    sandbox.request_permission('.', 'WRITE')
    
    # Attempt to add a file to the root of the sandbox
    sandbox.write_file('test_file.txt', 'Test content')
    
    # Verify the file was created
    assert sandbox.read_file('test_file.txt') == 'Test content'
    
    # Clean up
    sandbox.remove_file_or_dir('test_file.txt')

def test_grant_permission_to_root():
    sandbox = Sandbox('.')
    
    # Attempt to grant write permission to the root of the sandbox
    sandbox.request_permission('.', 'WRITE')
    
    # Verify that the permission was granted
    assert Permission.WRITE in sandbox.get_permissions('.')

# Run the tests
if __name__ == "__main__":
    pytest.main([__file__])
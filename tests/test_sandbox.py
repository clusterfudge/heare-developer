import os
import tempfile
import pytest

from heare.developer.sandbox import Sandbox, SandboxMode

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

def test_sandbox_init(temp_dir):
    # Test initializing Sandbox with different modes
    sandbox = Sandbox(temp_dir, SandboxMode.REQUEST_EVERY_TIME)
    assert sandbox.permissions_cache is None
    
    sandbox = Sandbox(temp_dir, SandboxMode.REMEMBER_PER_RESOURCE)
    assert isinstance(sandbox.permissions_cache, dict)
    
    sandbox = Sandbox(temp_dir, SandboxMode.REMEMBER_ALL)
    assert isinstance(sandbox.permissions_cache, dict)
    
    sandbox = Sandbox(temp_dir, SandboxMode.ALLOW_ALL)
    assert sandbox.permissions_cache is None
            
def test_gitignore_loading(temp_dir):
    with open(os.path.join(temp_dir, '.gitignore'), 'w') as f:
        f.write("ignored_dir/\n*.txt")
        
    sandbox = Sandbox(temp_dir, SandboxMode.ALLOW_ALL)
    
    os.makedirs(os.path.join(temp_dir, 'ignored_dir'))
    os.makedirs(os.path.join(temp_dir, 'included_dir'))
    
    with open(os.path.join(temp_dir, 'ignored_dir/file.txt'), 'w') as f:
        f.write("text")
    with open(os.path.join(temp_dir, 'included_dir/file.py'), 'w') as f:
        f.write("code")
        
    listing = sandbox.get_directory_listing()
    assert 'ignored_dir/file.txt' not in listing
    assert 'included_dir/file.py' in listing
    
def test_permissions(temp_dir, monkeypatch):
    sandbox = Sandbox(temp_dir, SandboxMode.REQUEST_EVERY_TIME)
    
    monkeypatch.setattr('builtins.input', lambda _: "y")
    assert sandbox.check_permissions("read", "file.txt") == True
    
    monkeypatch.setattr('builtins.input', lambda _: "n")
    assert sandbox.check_permissions("write", "file.txt") == False
    
    sandbox = Sandbox(temp_dir, SandboxMode.ALLOW_ALL) 
    assert sandbox.check_permissions("any_action", "any_resource") == True

def test_read_write_file(temp_dir):
    sandbox = Sandbox(temp_dir, SandboxMode.ALLOW_ALL)
    
    file_path = "test.txt"
    content = "test content"
    
    sandbox.write_file(file_path, content)
    assert sandbox.read_file(file_path) == content
    
    with pytest.raises(ValueError):
        sandbox.read_file("../outside_sandbox.txt")
    
    with pytest.raises(FileNotFoundError):
        sandbox.read_file("nonexistent.txt")
      
def test_create_file(temp_dir):
    sandbox = Sandbox(temp_dir, SandboxMode.ALLOW_ALL)
    
    file_path = "new_file.txt" 
    sandbox.create_file(file_path)
    assert os.path.exists(os.path.join(temp_dir, file_path))
    
    with pytest.raises(FileExistsError):
        sandbox.create_file(file_path)
  
    with pytest.raises(ValueError):
        sandbox.create_file("../outside_sandbox.txt")
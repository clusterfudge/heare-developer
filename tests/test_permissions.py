from heare.developer.sandbox import Permission, check_permission


def test_permission_hierarchy():
    # Test that WRITE permission implies READ and LIST
    assert check_permission(Permission.WRITE, Permission.READ)
    assert check_permission(Permission.WRITE, Permission.LIST)
    
    # Test that READ permission implies LIST
    assert check_permission(Permission.READ, Permission.LIST)
    
    # Test that lower permissions do not imply higher ones
    assert not check_permission(Permission.LIST, Permission.READ)
    assert not check_permission(Permission.LIST, Permission.WRITE)
    assert not check_permission(Permission.READ, Permission.WRITE)


def test_permission_combination():
    # Test that combined permissions work correctly
    combined = Permission.WRITE | Permission.READ | Permission.LIST
    assert check_permission(combined, Permission.WRITE)
    assert check_permission(combined, Permission.READ)
    assert check_permission(combined, Permission.LIST)


def test_permission_equality():
    # Test that permissions are equal to themselves
    assert check_permission(Permission.WRITE, Permission.WRITE)
    assert check_permission(Permission.READ, Permission.READ)
    assert check_permission(Permission.LIST, Permission.LIST)


def test_no_permission():
    # Test that no permission does not allow any access
    assert not check_permission(Permission(0), Permission.WRITE)
    assert not check_permission(Permission(0), Permission.READ)
    assert not check_permission(Permission(0), Permission.LIST)
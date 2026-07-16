from scripts.reset_test_db import is_safe_test_database


def test_only_explicit_test_database_names_are_safe_to_reset() -> None:
    assert is_safe_test_database("My_eBookStore_Test")
    assert is_safe_test_database("acceptance_test")
    assert not is_safe_test_database("My_eBookStore")
    assert not is_safe_test_database("master")
    assert not is_safe_test_database("other_test; DROP DATABASE master")
    assert not is_safe_test_database("test")

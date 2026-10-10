from greenlight.tools import is_test_file, norm_path, shadows_library


def test_shadowing_detection():
    assert shadows_library("pydantic.py", "pydantic")
    assert shadows_library("/repo/src/pydantic.py", "pydantic")
    assert shadows_library("vendor/sqlalchemy/__init__.py", "SQLAlchemy")
    assert shadows_library("lib/pydantic_settings.py", "pydantic-settings")
    assert not shadows_library("shop/models.py", "pydantic")
    assert not shadows_library("pydantic_vault/settings.py", "pydantic")


def test_paths():
    assert norm_path("/repo/shop/models.py") == "shop/models.py"
    assert norm_path("./x.py") == "x.py"
    assert is_test_file("tests/test_a.py") and is_test_file("pkg/conftest.py") and is_test_file("a_test.py")
    assert not is_test_file("pkg/testing_utils.py")

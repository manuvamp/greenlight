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


from greenlight.tools import audit_test_edit  # noqa: E402

OLD = """from pydantic import BaseSettings

def test_dump():
    m = Model(a=1)
    assert m.dict() == {"a": 1}
    with pytest.raises(ValidationError):
        Model(a="x")
"""


def test_api_migration_of_tests_is_allowed():
    new = OLD.replace("from pydantic import BaseSettings", "from pydantic_settings import BaseSettings") \
             .replace("m.dict()", "m.model_dump()")
    assert audit_test_edit(OLD, new) == []


def test_weakening_tests_is_refused():
    assert audit_test_edit(OLD, OLD.replace('    assert m.dict() == {"a": 1}\n', ""))
    assert audit_test_edit(OLD, OLD.replace('assert m.dict() == {"a": 1}', 'assert True'))
    assert audit_test_edit(OLD, "import pytest\n@pytest.mark.skip\n" + OLD)
    assert audit_test_edit(OLD, OLD.replace("def test_dump", "def helper_dump"))

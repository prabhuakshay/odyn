import odyn.exceptions


def test_exceptions_imports():
    """Test imports from odyn.exceptions"""
    assert "OdynError" in odyn.exceptions.__all__
    assert "QueryValidationError" in odyn.exceptions.__all__

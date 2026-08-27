import pytest
from pydantic import ValidationError

from app.models import AnalyzeRequest, EstimateRequest


@pytest.mark.parametrize("model", [AnalyzeRequest, EstimateRequest])
def test_warrant_requests_only_accept_six_digits(model):
    assert model(code="067185").code == "067185"

    with pytest.raises(ValidationError):
        model(code="03002T")

    with pytest.raises(ValidationError):
        model(code="67185")

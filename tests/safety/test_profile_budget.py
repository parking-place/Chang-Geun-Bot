import pytest
import yaml

from changgeun_inference.config import read_profile


def profile(limit=20, purpose=None, identifier="test-jev-api"):
    hosted = {
        "endpoint": "https://api.typesafe.ai/v1/systemone",
        "model": "jev-1.13.0",
        "api_key_env": "JEV_HOSTED_API_KEY",
        "max_calls_per_run": limit,
    }
    if purpose is not None:
        hosted["run_purpose"] = purpose
    return {
        "provider": "jev-api",
        "profile_id": identifier,
        "api_schema_version": "1.2",
        "automatic_provider_retries": 0,
        "automatic_fallback": False,
        "max_provider_calls_per_request": 3,
        "hosted": hosted,
    }


@pytest.mark.parametrize(
    "config",
    [
        profile(21),
        profile(3000, "development-evaluation"),
        profile(3001, "release-evaluation", "eval-jev-api"),
        profile(True),
        profile(100, "unknown", "eval-jev-api"),
    ],
)
def test_large_or_malformed_budget_is_not_implicitly_allowed(tmp_path, config):
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        read_profile(path)


def test_explicit_evaluation_budget_is_hash_bound_and_smoke_remains_20(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(profile()))
    smoke, smoke_hash = read_profile(path)
    assert smoke["hosted"]["max_calls_per_run"] == 20
    path.write_text(yaml.safe_dump(profile(3000, "development-evaluation", "eval-jev-api")))
    evaluation, evaluation_hash = read_profile(path)
    assert evaluation["hosted"]["max_calls_per_run"] == 3000
    assert smoke_hash != evaluation_hash


@pytest.mark.parametrize("provider", ["local-openjev", "openjev", "other-api"])
def test_retired_or_unregistered_provider_is_rejected_before_dispatch(tmp_path, provider):
    config = profile()
    config["provider"] = provider
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        read_profile(path, allow_mock=True)


@pytest.mark.parametrize("field", ["local", "snapshot", "model_revision"])
def test_local_model_fields_cannot_be_attached_to_hosted_profile(tmp_path, field):
    config = profile()
    config[field] = {"device": "cpu", "model_id": "retired"}
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="unknown/missing"):
        read_profile(path)


def test_mock_needs_explicit_test_mode_and_cannot_carry_hosted_credentials(tmp_path):
    config = profile()
    config["provider"] = "mock"
    del config["hosted"]
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="explicit test mode"):
        read_profile(path)
    assert read_profile(path, allow_mock=True)[0]["provider"] == "mock"
    config["hosted"] = profile()["hosted"]
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError, match="cannot contain hosted"):
        read_profile(path, allow_mock=True)


def test_internal_request_and_response_schema_exclude_retired_provider():
    from changgeun_inference.contracts import DecisionRequest, DecisionResponse

    for contract in (DecisionRequest, DecisionResponse):
        assert contract.model_json_schema()["properties"]["provider"]["enum"] == ["jev-api", "mock"]

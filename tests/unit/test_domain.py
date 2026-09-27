from dataclasses import replace

import pytest

from changgeun.domain.models import (
    Action,
    ActionPlan,
    Actor,
    DomainError,
    Policy,
    authorize,
    needs_confirmation,
    normalized_name,
)


@pytest.fixture
def policy():
    return Policy(
        frozenset({"1", "2"}), frozenset({"dj"}), frozenset({"text"}), frozenset({"voice"})
    )


@pytest.fixture
def actor():
    return Actor("1", "999999999999999999", frozenset({"dj"}), "text", "voice", "voice")


def test_normalized_korean_and_unicode():
    assert normalized_name("  새벽   노동요  ") == "새벽 노동요"
    assert normalized_name("ＡＢＣ") == "abc"
    with pytest.raises(DomainError, match="invalid_name"):
        normalized_name(" ")


@pytest.mark.parametrize("action", list(Action))
def test_every_action_has_policy(action, actor, policy):
    actor = replace(actor, manage_guild=True)
    authorize(ActionPlan("request", actor.guild_id, actor.user_id, action), actor, policy)


@pytest.mark.parametrize(
    "change,error",
    [
        ({"role_ids": frozenset()}, "dj_required"),
        ({"role_ids": frozenset(), "manage_guild": True}, "dj_required"),
        ({"permissions_known": False}, "permissions_unavailable"),
        ({"text_channel_id": "elsewhere"}, "text_channel_not_allowed"),
        ({"voice_channel_id": "other"}, "same_voice_required"),
    ],
)
def test_fail_closed_mutation(change, error, actor, policy):
    with pytest.raises(DomainError, match=error):
        authorize(
            ActionPlan("r", actor.guild_id, actor.user_id, Action.QUEUE_CLEAR),
            replace(actor, **change),
            policy,
        )


def test_read_and_proposal_allowed_non_dj(actor, policy):
    for action in (Action.PLAYLIST_LIST, Action.CATALOG_SEARCH, Action.PROPOSAL_CREATE):
        authorize(
            ActionPlan("r", actor.guild_id, actor.user_id, action),
            replace(actor, role_ids=frozenset()),
            policy,
        )


def test_identity_cannot_come_from_model(actor, policy):
    with pytest.raises(DomainError, match="identity_mismatch"):
        authorize(ActionPlan("r", "2", actor.user_id, Action.PLAYLIST_LIST), actor, policy)


def test_admin_override_is_explicit(actor, policy):
    authorize(
        ActionPlan("r", "1", actor.user_id, Action.PLAYLIST_CREATE),
        replace(actor, manage_guild=True, role_ids=frozenset()),
        replace(policy, admin_dj_override=True),
    )


def test_confirmation_cannot_be_overridden(actor, policy):
    assert needs_confirmation(ActionPlan("r", "1", actor.user_id, Action.PLAYLIST_DELETE), policy)
    assert needs_confirmation(
        ActionPlan("r", "1", actor.user_id, Action.PLAYLIST_REMOVE, origin="natural_language"),
        policy,
    )
    assert needs_confirmation(
        ActionPlan("r", "1", actor.user_id, Action.PLAYLIST_ADD, {"track_ids": ["id"] * 20}), policy
    )


@pytest.mark.parametrize("provider", ["local-openjev", "other-api"])
def test_unsupported_provider_trace_cannot_authorize_execution(provider):
    from changgeun.domain.models import InferenceTrace

    trace = InferenceTrace(provider, "test", "a" * 64, 1, 1, 1, None, "unavailable")
    with pytest.raises(DomainError, match="invalid_inference_binding"):
        trace.validate()


def test_hosted_trace_cannot_claim_a_measured_forward_count():
    from changgeun.domain.models import InferenceTrace

    trace = InferenceTrace("jev-api", "test", "a" * 64, 1, 1, 1, 1, "measured")
    with pytest.raises(DomainError, match="invalid_forward_provenance"):
        trace.validate()

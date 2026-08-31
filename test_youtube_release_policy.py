"""Regression tests for fail-closed YouTube release policy."""

from copy import deepcopy

from backend.services.orchestration.youtube_release_policy import (
    YoutubeReleasePolicy,
)


def cycle_result(
    *,
    status="completed",
    eligible=True,
    selected=True,
    production_score=85.0,
    upload_status="completed",
    privacy_status="private",
    video_id="video-123",
):
    return {
        "status": status,
        "selected_trend": {
            "title": "Production Candidate",
            "production_selection": {
                "eligible": eligible,
                "selected": selected,
                "production_score": production_score,
            },
        },
        "upload": {
            "status": upload_status,
            "privacy_status": privacy_status,
            "upload": {
                "status": upload_status,
                "result": {
                    "video_id": video_id,
                    "privacy_status": privacy_status,
                },
            },
        },
    }


def assert_denied(
    decision,
    reason,
):
    assert decision["authorized"] is False
    assert decision["status"] == "denied"
    assert reason in decision["reasons"]
    assert decision["target_privacy_status"] is None


# --------------------------------------------------
# Default policy must be fail closed.
# --------------------------------------------------

result = cycle_result()

policy = YoutubeReleasePolicy()

decision = policy.evaluate(
    cycle_result=result,
    manual_approved=True,
)

assert_denied(
    decision,
    "release_disabled",
)

print(
    "PASS: release policy is disabled by default."
)


# --------------------------------------------------
# Manual approval defaults to required.
# --------------------------------------------------

policy = YoutubeReleasePolicy(
    enabled=True,
)

decision = policy.evaluate(
    cycle_result=result,
)

assert_denied(
    decision,
    "manual_approval_required",
)

print(
    "PASS: manual approval is required by default."
)


# --------------------------------------------------
# Complete valid evidence may authorize publication.
# --------------------------------------------------

decision = policy.evaluate(
    cycle_result=result,
    manual_approved=True,
)

assert decision["authorized"] is True
assert decision["status"] == "authorized"
assert decision["reasons"] == []
assert decision["video_id"] == "video-123"
assert decision["target_privacy_status"] == "public"

print(
    "PASS: complete release evidence authorizes publication."
)


# --------------------------------------------------
# Failed/incomplete production cannot publish.
# --------------------------------------------------

bad = cycle_result(
    status="upload_failed",
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "production_cycle_not_completed",
)

print(
    "PASS: incomplete production cycle cannot publish."
)


# --------------------------------------------------
# Ineligible or unselected topics cannot publish.
# --------------------------------------------------

bad = cycle_result(
    eligible=False,
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "production_selection_not_eligible",
)

bad = cycle_result(
    selected=False,
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "production_selection_not_selected",
)

print(
    "PASS: production selection gates remain authoritative."
)


# --------------------------------------------------
# Production quality threshold is fail closed.
# --------------------------------------------------

bad = cycle_result(
    production_score=69.99,
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "production_score_below_threshold",
)

bad = cycle_result(
    production_score=None,
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "production_score_unavailable",
)

print(
    "PASS: weak or missing production score blocks release."
)


# --------------------------------------------------
# Upload must already be completed and PRIVATE.
# --------------------------------------------------

bad = cycle_result(
    upload_status="failed",
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "upload_not_completed",
)

bad = cycle_result(
    privacy_status="public",
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "video_not_private",
)

print(
    "PASS: release only operates on completed private uploads."
)


# --------------------------------------------------
# Provider video identity is mandatory.
# --------------------------------------------------

bad = cycle_result(
    video_id="",
)

decision = policy.evaluate(
    cycle_result=bad,
    manual_approved=True,
)

assert_denied(
    decision,
    "youtube_video_id_unavailable",
)

print(
    "PASS: missing YouTube video identity blocks release."
)


# --------------------------------------------------
# Missing/malformed evidence must never authorize.
# --------------------------------------------------

for malformed in (
    None,
    {},
    {"status": "completed"},
    {"status": "completed", "selected_trend": []},
    {"status": "completed", "upload": []},
):
    decision = policy.evaluate(
        cycle_result=malformed,
        manual_approved=True,
    )

    assert decision["authorized"] is False
    assert decision["reasons"]

print(
    "PASS: malformed release evidence fails closed."
)


# --------------------------------------------------
# Explicit autonomous mode may disable manual approval,
# but all other gates still apply.
# --------------------------------------------------

autonomous_policy = YoutubeReleasePolicy(
    enabled=True,
    require_manual_approval=False,
)

decision = autonomous_policy.evaluate(
    cycle_result=result,
)

assert decision["authorized"] is True

bad = cycle_result(
    production_score=20.0,
)

decision = autonomous_policy.evaluate(
    cycle_result=bad,
)

assert_denied(
    decision,
    "production_score_below_threshold",
)

print(
    "PASS: autonomous release cannot bypass quality gates."
)


# --------------------------------------------------
# Evaluation must be side-effect free.
# --------------------------------------------------

original = cycle_result()
before = deepcopy(original)

policy.evaluate(
    cycle_result=original,
    manual_approved=True,
)

assert original == before

print(
    "PASS: release policy does not mutate production state."
)


# --------------------------------------------------
# Configuration validation.
# --------------------------------------------------

for invalid in (
    -1,
    101,
    True,
    "invalid",
):
    try:
        YoutubeReleasePolicy(
            min_production_score=invalid,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid release threshold was accepted."
        )

print(
    "PASS: release threshold configuration is bounded."
)

print(
    "PASS: YouTube release policy regression suite complete."
)

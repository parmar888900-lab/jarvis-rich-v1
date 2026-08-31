"""Tests for goal-aware production topic intelligence."""

from backend.services.intelligence.goal_topic_intelligence import (
    GoalTopicIntelligence,
)


def strategy(
    *,
    status="goal_guided",
    metric="views",
    priority=100.0,
    exploitation=1.0,
):
    return {
        "status": status,
        "target_metric": metric,
        "production_priority": priority,
        "exploitation_bias": exploitation,
        "exploration_bias": 1.0 - exploitation,
        "scheduler_interval_multiplier": 1.0,
    }


intelligence = GoalTopicIntelligence()


# Missing strategy must be exactly neutral.
result = intelligence.evaluate(
    {"final_score": 100},
    None,
)

assert result["status"] == "neutral"
assert result["reason"] == "goal_strategy_unavailable"
assert result["adjustment"] == 0.0

print("PASS: missing strategy produces neutral goal intelligence.")


# Neutral strategy must not influence candidate ranking.
result = intelligence.evaluate(
    {"final_score": 100},
    strategy(status="neutral"),
)

assert result["status"] == "neutral"
assert result["reason"] == "goal_strategy_not_active"
assert result["adjustment"] == 0.0

print("PASS: inactive goal strategy cannot influence candidate ranking.")


# Unsupported metrics must fail neutral rather than inventing a mapping.
result = intelligence.evaluate(
    {"final_score": 100},
    strategy(metric="revenue"),
)

assert result["status"] == "neutral"
assert result["reason"] == "unsupported_goal_metric"
assert result["adjustment"] == 0.0

print("PASS: unsupported goal metric fails neutral.")


# Maximum-strength views candidate can receive at most +5.
result = intelligence.evaluate(
    {"final_score": 100},
    strategy(
        priority=100,
        exploitation=1.0,
    ),
)

assert result["status"] == "applied"
assert result["candidate_signal"] == "viral_score"
assert result["candidate_signal_value"] == 100.0
assert result["adjustment"] == 5.0

print("PASS: strongest views candidate receives bounded +5 adjustment.")


# Minimum-strength candidate can receive at most -5.
result = intelligence.evaluate(
    {"final_score": 0},
    strategy(
        priority=100,
        exploitation=1.0,
    ),
)

assert result["adjustment"] == -5.0

print("PASS: weakest views candidate receives bounded -5 adjustment.")


# A midpoint candidate should remain neutral.
result = intelligence.evaluate(
    {"final_score": 50},
    strategy(
        priority=100,
        exploitation=1.0,
    ),
)

assert result["adjustment"] == 0.0

print("PASS: midpoint candidate receives zero goal adjustment.")


# Greater goal pressure should increase influence without exceeding bounds.
low_pressure = intelligence.evaluate(
    {"final_score": 90},
    strategy(
        priority=40,
        exploitation=0.5,
    ),
)

high_pressure = intelligence.evaluate(
    {"final_score": 90},
    strategy(
        priority=90,
        exploitation=0.8,
    ),
)

assert high_pressure["adjustment"] > low_pressure["adjustment"]
assert abs(low_pressure["adjustment"]) <= intelligence.MAX_ADJUSTMENT
assert abs(high_pressure["adjustment"]) <= intelligence.MAX_ADJUSTMENT

print("PASS: stronger goal pressure creates greater bounded influence.")


# Score fallback order must work.
result = intelligence.evaluate(
    {"score": 80},
    strategy(),
)

assert result["candidate_signal_value"] == 80.0
assert result["adjustment"] > 0

result = intelligence.evaluate(
    {"initial_score": 20},
    strategy(),
)

assert result["candidate_signal_value"] == 20.0
assert result["adjustment"] < 0

print("PASS: candidate viral-score fallback signals are supported.")


# Missing or malformed candidate signals fail neutral.
result = intelligence.evaluate(
    {"title": "No score"},
    strategy(),
)

assert result["status"] == "neutral"
assert result["reason"] == "candidate_signal_unavailable"
assert result["adjustment"] == 0.0

result = intelligence.evaluate(
    {"final_score": True},
    strategy(),
)

assert result["status"] == "neutral"
assert result["adjustment"] == 0.0

print("PASS: malformed candidate signals fail neutral.")


# Goal intelligence must never change scheduler cadence.
input_strategy = strategy(
    priority=100,
    exploitation=1.0,
)

before_multiplier = input_strategy["scheduler_interval_multiplier"]

intelligence.evaluate(
    {"final_score": 100},
    input_strategy,
)

assert input_strategy["scheduler_interval_multiplier"] == before_multiplier
assert input_strategy["scheduler_interval_multiplier"] == 1.0

print("PASS: topic intelligence cannot alter scheduler cadence.")


# Exhaustive representative bounds check.
for viral_score in (
    -100,
    0,
    10,
    25,
    50,
    75,
    90,
    100,
    200,
):
    for priority in (
        -100,
        0,
        25,
        50,
        100,
        200,
    ):
        for exploitation in (
            -1.0,
            0.0,
            0.25,
            0.5,
            1.0,
            2.0,
        ):
            result = intelligence.evaluate(
                {"final_score": viral_score},
                strategy(
                    priority=priority,
                    exploitation=exploitation,
                ),
            )

            assert (
                -intelligence.MAX_ADJUSTMENT
                <= result["adjustment"]
                <= intelligence.MAX_ADJUSTMENT
            )

print("PASS: all representative goal adjustments remain within ±5.")
print("PASS: GoalTopicIntelligence regression suite complete.")

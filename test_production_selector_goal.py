"""Goal intelligence integration tests for ProductionTopicSelector."""

from copy import deepcopy

from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)


def make_trend(
    title,
    *,
    viral=80,
    research=85,
    category="Stories",
):
    return {
        "title": title,
        "source": "Test",
        "final_score": viral,
        "category": category,
        "knowledge": {
            "score": research,
            "category": category,
            "summary": "Useful researched explanation.",
            "facts": [
                "Relevant fact one.",
                "Relevant fact two.",
                "Relevant fact three.",
            ],
            "sources": [
                {"source": "Source A"},
                {"source": "Source B"},
                {"source": "Source C"},
            ],
        },
    }


def goal_strategy(
    *,
    metric="views",
    priority=100.0,
    exploitation=1.0,
):
    return {
        "status": "goal_guided",
        "active_goal_count": 1,
        "target_metric": metric,
        "trajectory": "behind",
        "production_priority": priority,
        "exploration_bias": 1.0 - exploitation,
        "exploitation_bias": exploitation,
        "scheduler_interval_multiplier": 1.0,
    }


# ------------------------------------------------------------------
# No goal must preserve existing score exactly.
# ------------------------------------------------------------------

selector = ProductionTopicSelector()

candidate = make_trend(
    "Strong candidate",
    viral=90,
)

winner = selector.select(
    [candidate],
)

selection = winner["production_selection"]

assert selection["goal_adjustment"] == 0.0
assert (
    selection["production_score"]
    == round(
        selection["base_production_score"]
        + selection["historical_adjustment"],
        2,
    )
)

assert selection["goal_evidence"]["status"] == "neutral"

print("PASS: no active goal preserves existing production scoring.")


# ------------------------------------------------------------------
# Behind views goal should reward a strong viral candidate.
# ------------------------------------------------------------------

candidate = make_trend(
    "High viral candidate",
    viral=100,
)

winner = selector.select(
    [candidate],
    goal_strategy=goal_strategy(),
)

selection = winner["production_selection"]

assert selection["goal_adjustment"] == 5.0
assert selection["goal_evidence"]["status"] == "applied"

assert selection["production_score"] == min(
    round(
        selection["base_production_score"]
        + selection["historical_adjustment"]
        + selection["goal_adjustment"],
        2,
    ),
    100.0,
)

print("PASS: active views goal applies bounded candidate adjustment.")


# ------------------------------------------------------------------
# Unsupported goals must remain neutral.
# ------------------------------------------------------------------

candidate = make_trend(
    "Revenue candidate",
    viral=100,
)

winner = selector.select(
    [candidate],
    goal_strategy=goal_strategy(
        metric="revenue",
    ),
)

selection = winner["production_selection"]

assert selection["goal_adjustment"] == 0.0
assert (
    selection["goal_evidence"]["reason"]
    == "unsupported_goal_metric"
)

print("PASS: unsupported goal metric preserves existing scoring.")


# ------------------------------------------------------------------
# Goal intelligence must not authorize rejected candidates.
# ------------------------------------------------------------------

candidate = make_trend(
    "Poor research candidate",
    viral=100,
    research=0,
)

ranked = selector.rank(
    [candidate],
    goal_strategy=goal_strategy(),
)

selection = ranked[0]["production_selection"]

assert selection["eligible"] is False
assert (
    "research_confidence_below_threshold"
    in selection["rejection_reasons"]
)

# Goal adjustment may still describe candidate alignment, but cannot
# change eligibility.
assert selection["goal_adjustment"] == 5.0

winner = selector.select(
    [
        make_trend(
            "Still poor research",
            viral=100,
            research=0,
        )
    ],
    goal_strategy=goal_strategy(),
)

assert winner is None

print("PASS: goal pressure cannot authorize an ineligible candidate.")


# ------------------------------------------------------------------
# Historical and goal adjustments must compose independently.
# ------------------------------------------------------------------

class FakeHistoricalIntelligence:
    def evaluate(self, candidate, performance):
        return {
            "status": "applied",
            "reason": "test_historical_evidence",
            "confidence": 1.0,
            "adjustment": 8.0,
        }


selector_with_history = ProductionTopicSelector()
selector_with_history.historical_intelligence = (
    FakeHistoricalIntelligence()
)

candidate = make_trend(
    "Historically strong and goal aligned",
    viral=100,
)

winner = selector_with_history.select(
    [candidate],
    performance={
        "strategy_ready": True,
    },
    goal_strategy=goal_strategy(),
)

selection = winner["production_selection"]

assert selection["historical_adjustment"] == 8.0
assert selection["goal_adjustment"] == 5.0

expected = min(
    max(
        selection["base_production_score"]
        + 8.0
        + 5.0,
        0.0,
    ),
    100.0,
)

assert selection["production_score"] == round(
    expected,
    2,
)

print("PASS: historical and goal intelligence compose independently.")


# ------------------------------------------------------------------
# Goal adjustment must be able to change ordering among eligible topics.
# ------------------------------------------------------------------

baseline_candidates = [
    make_trend(
        "High suitability style candidate",
        viral=55,
        research=95,
    ),
    make_trend(
        "High viral candidate",
        viral=100,
        research=70,
    ),
]

without_goal = ProductionTopicSelector().rank(
    deepcopy(baseline_candidates)
)

with_goal = ProductionTopicSelector().rank(
    deepcopy(baseline_candidates),
    goal_strategy=goal_strategy(),
)

for candidate in with_goal:
    selection = candidate["production_selection"]
    assert selection["eligible"] is True
    assert abs(selection["goal_adjustment"]) <= 5.0

# We do not require every arbitrary pair to reverse ordering.
# We require that the goal signal actually changes relative scores.
without_scores = {
    item["title"]: item["production_selection"][
        "production_score"
    ]
    for item in without_goal
}

with_scores = {
    item["title"]: item["production_selection"][
        "production_score"
    ]
    for item in with_goal
}

assert (
    with_scores["High viral candidate"]
    > without_scores["High viral candidate"]
)

assert (
    with_scores["High suitability style candidate"]
    != without_scores[
        "High suitability style candidate"
    ]
)

print("PASS: goal strategy changes eligible candidate scoring.")


# ------------------------------------------------------------------
# Existing scheduler strategy field must remain untouched.
# ------------------------------------------------------------------

strategy_input = goal_strategy()
before = deepcopy(strategy_input)

ProductionTopicSelector().select(
    [
        make_trend(
            "Scheduler invariant candidate",
            viral=100,
        )
    ],
    goal_strategy=strategy_input,
)

assert strategy_input == before
assert (
    strategy_input["scheduler_interval_multiplier"]
    == 1.0
)

print("PASS: selector cannot alter goal strategy or scheduler cadence.")

print(
    "PASS: ProductionTopicSelector goal integration regression "
    "suite complete."
)

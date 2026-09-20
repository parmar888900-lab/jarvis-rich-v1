from backend.services.agent_registry import build_default_registry


registry = build_default_registry()

print(
    "AGENTS:",
    registry.list_agents(),
)

goal = registry.get("goal")

print(
    "GOAL TASKS:",
    sorted(goal.supported_tasks),
)

assert registry.is_registered("goal")
assert goal.supports_task("create_goal")
assert goal.supports_task("get_goal_status")
assert goal.supports_task("update_goal")
assert goal.supports_task("list_goals")
assert goal.supports_task("pause_goal")
assert goal.supports_task("resume_goal")

print()
print(
    "PASS: Goal agent registered "
    "with AgentRegistry."
)

"""Movie commentary planning for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class MovieCommentaryBeat:
    beat_id: str
    purpose: str
    narration_goal: str
    visual_goal: str
    target_duration: float


class MovieCommentaryPlanner:
    """
    Build the editorial structure for famous-movie Shorts.

    The planner describes what footage is needed but does not
    authorize or acquire copyrighted material.
    """

    def plan(
        self,
        *,
        movie_title: str,
        topic: str,
    ) -> list[MovieCommentaryBeat]:

        return [
            MovieCommentaryBeat(
                beat_id="hook",
                purpose="hook",
                narration_goal=(
                    "Immediately explain the surprising or interesting "
                    "thing about this movie or scene."
                ),
                visual_goal=(
                    f"Recognizable authorized visual from {movie_title}"
                ),
                target_duration=4.0,
            ),
            MovieCommentaryBeat(
                beat_id="context",
                purpose="context",
                narration_goal=(
                    "Give only the context required to understand "
                    "why the moment matters."
                ),
                visual_goal=(
                    "Authorized contextual movie or production visual"
                ),
                target_duration=8.0,
            ),
            MovieCommentaryBeat(
                beat_id="detail_1",
                purpose="analysis",
                narration_goal=(
                    "Explain the first concrete filmmaking, character, "
                    "editing, VFX, or storytelling detail."
                ),
                visual_goal=(
                    "Supporting authorized detail or production visual"
                ),
                target_duration=10.0,
            ),
            MovieCommentaryBeat(
                beat_id="detail_2",
                purpose="analysis",
                narration_goal=(
                    "Add a second detail that increases the viewer's "
                    "understanding or changes how they see the scene."
                ),
                visual_goal=(
                    "Different supporting authorized visual"
                ),
                target_duration=10.0,
            ),
            MovieCommentaryBeat(
                beat_id="payoff",
                purpose="payoff",
                narration_goal=(
                    "Finish with the reason the scene, technique, "
                    "or decision was effective."
                ),
                visual_goal=(
                    "Strong final authorized movie or filmmaking visual"
                ),
                target_duration=8.0,
            ),
        ]

    @staticmethod
    def to_dicts(
        beats: list[MovieCommentaryBeat],
    ) -> list[dict]:

        return [
            asdict(beat)
            for beat in beats
        ]

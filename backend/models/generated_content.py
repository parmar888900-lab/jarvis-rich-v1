from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class GeneratedContent:
    """
    Standard content object passed through the Jarvis Rich V1 pipeline.
    """

    title: str
    hashtags: List[str] = field(default_factory=list)
    script_lines: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def full_script(self) -> str:
        return "\n".join(self.script_lines)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "hashtags": list(self.hashtags),
            "script_lines": list(self.script_lines),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GeneratedContent":
        return cls(
            title=data.get("title", ""),
            hashtags=data.get("hashtags", []),
            script_lines=data.get("script_lines", []),
            metadata=data.get("metadata", {}),
        )
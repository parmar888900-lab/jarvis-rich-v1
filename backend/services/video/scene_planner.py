import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ScenePlanner:
    """
    Parses structured script data and generates timing and visual directives.
    """

    def __init__(self):
        pass

    async def plan(self, content_package: Any) -> List[Dict[str, Any]]:
        logger.info("Planning scenes from content package...")

        script_lines = []

        if isinstance(content_package, dict):
            # Inspect multiple possible key names
            for key in ["script_lines", "script", "lines", "scenes", "narration"]:
                val = content_package.get(key)
                if val:
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, str) and item.strip():
                                script_lines.append(item.strip())
                            elif isinstance(item, dict):
                                text = item.get("narration") or item.get("text") or item.get("line")
                                if text:
                                    script_lines.append(str(text).strip())
                        if script_lines:
                            break
                    elif isinstance(val, str) and val.strip():
                        script_lines = [line.strip() for line in val.split("\n") if line.strip()]
                        break

        elif isinstance(content_package, list):
            script_lines = [str(item).strip() for item in content_package if str(item).strip()]

        elif isinstance(content_package, str):
            script_lines = [line.strip() for line in content_package.split("\n") if line.strip()]

        # Filter out stage directions and empty lines
        filtered_lines = []
        for line in script_lines:
            clean = line.strip('"').strip("'").strip()
            if clean and not clean.startswith("[") and not clean.startswith("#"):
                filtered_lines.append(clean)

        if not filtered_lines:
            logger.warning("No script lines found. Applying safety scene line.")
            filtered_lines = ["Check out the latest updates on this viral topic!"]

        scenes = []
        current_time = 0.0

        for i, sentence in enumerate(filtered_lines):
            visual_prompt, text_overlay = self._generate_visual_directives(sentence)

            word_count = len(sentence.split())
            duration = max(2.5, round(word_count / 2.5, 1))

            scene = {
                "scene_id": i + 1,
                "narration_text": sentence,
                "visual_prompt": visual_prompt,
                "text_overlay": text_overlay,
                "start_time": current_time,
                "end_time": round(current_time + duration, 1),
                "duration": duration,
            }
            scenes.append(scene)
            current_time = round(current_time + duration, 1)

        logger.info(f"Successfully generated {len(scenes)} scenes.")
        return scenes

    def _generate_visual_directives(self, sentence: str) -> Tuple[str, str]:
        words = [w for w in re.sub(r"[^\w\s]", "", sentence).split() if len(w) > 2]
        text_overlay = " ".join(words[:4]).upper() if words else "WATCH NOW"

        visual_prompt = (
            f"Cinematic photorealistic shot, vertical video 9:16 aspect ratio, "
            f"visualizing context: '{sentence[:90]}'"
        )

        return visual_prompt, text_overlay
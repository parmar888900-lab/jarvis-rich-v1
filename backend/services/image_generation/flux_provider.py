import asyncio
import json
import shutil
import time
import uuid
from pathlib import Path

import aiohttp

from backend.services.image_generation.base_provider import BaseImageProvider
from backend.services.image_generation.models import GeneratedImage


class FluxProvider(BaseImageProvider):

    def __init__(self):
        self.comfyui_url = "http://127.0.0.1:8188"

        self.workflow_path = Path(
            "configs/workflows/flux_api.json"
        )

        self.comfyui_output_dir = Path(
            r"C:\Users\hp\ComfyUI\output"
        )

        self.jarvis_output_dir = Path(
            "generated/images"
        )

        self.jarvis_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def generate(
        self,
        prompt: str,
    ) -> GeneratedImage:

        print("[FLUX] loading workflow")

        workflow = self._load_workflow()

        print("[FLUX] injecting prompt")

        self._inject_prompt(
            workflow,
            prompt,
        )

        print("[FLUX] sending prompt to ComfyUI")

        prompt_id = await self._queue_prompt(
            workflow
        )

        print(f"[FLUX] prompt queued: {prompt_id}")
        print("[FLUX] waiting for image")

        output_filename = await self._wait_for_image(
            prompt_id
        )

        print(f"[FLUX] image finished: {output_filename}")

        source_path = (
            self.comfyui_output_dir
            / output_filename
        )

        destination_name = (
            f"jarvis_{uuid.uuid4().hex}.png"
        )

        destination_path = (
            self.jarvis_output_dir
            / destination_name
        )

        shutil.copy2(
            source_path,
            destination_path,
        )

        print(f"[FLUX] copied to: {destination_path}")

        return GeneratedImage(
            prompt=prompt,
            image_path=str(destination_path),
            provider="flux-comfyui",
            width=720,
            height=1280,
        )

    def _load_workflow(self) -> dict:

        if not self.workflow_path.exists():
            raise FileNotFoundError(
                f"Workflow not found: {self.workflow_path}"
            )

        with open(
            self.workflow_path,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    def _inject_prompt(
        self,
        workflow: dict,
        prompt: str,
    ) -> None:

        prompt_node = workflow["41"]

        prompt_node["inputs"]["clip_l"] = prompt
        prompt_node["inputs"]["t5xxl"] = prompt

        workflow["31"]["inputs"]["seed"] = (
            int(time.time_ns())
            % 1_000_000_000_000_000
        )

    async def _queue_prompt(
        self,
        workflow: dict,
    ) -> str:

        payload = {
            "prompt": workflow,
            "client_id": str(uuid.uuid4()),
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.comfyui_url}/prompt",
                json=payload,
            ) as response:

                if response.status != 200:
                    text = await response.text()

                    raise RuntimeError(
                        "ComfyUI rejected prompt: "
                        f"{response.status} {text}"
                    )

                data = await response.json()

        prompt_id = data.get("prompt_id")

        if not prompt_id:
            raise RuntimeError(
                "ComfyUI did not return a prompt_id."
            )

        return prompt_id

    async def _wait_for_image(
        self,
        prompt_id: str,
        timeout: int = 900,
    ) -> str:

        start_time = time.monotonic()

        async with aiohttp.ClientSession() as session:

            while True:

                if time.monotonic() - start_time > timeout:
                    raise TimeoutError(
                        "ComfyUI generation timed out."
                    )

                async with session.get(
                    f"{self.comfyui_url}/history/{prompt_id}"
                ) as response:

                    if response.status != 200:
                        text = await response.text()

                        raise RuntimeError(
                            "Could not read ComfyUI "
                            f"history: {text}"
                        )

                    history = await response.json()

                if prompt_id in history:

                    prompt_history = history[prompt_id]

                    outputs = prompt_history.get(
                        "outputs",
                        {},
                    )

                    save_node = outputs.get(
                        "9",
                        {},
                    )

                    images = save_node.get(
                        "images",
                        [],
                    )

                    if images:
                        return images[0]["filename"]

                    status = prompt_history.get(
                        "status",
                        {},
                    )

                    if status.get("status_str") == "error":
                        raise RuntimeError(
                            "ComfyUI reported generation failure."
                        )

                await asyncio.sleep(2)


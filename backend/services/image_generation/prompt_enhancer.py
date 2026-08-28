class PromptEnhancer:

    STYLE = (
        "cinematic, ultra detailed, "
        "dramatic lighting, volumetric light, "
        "8k, realistic, masterpiece, "
        "vertical composition, highly detailed"
    )

    def enhance(
        self,
        prompt: str,
    ) -> str:

        return f"{prompt}, {self.STYLE}"
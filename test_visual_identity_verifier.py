from backend.services.video.visual_identity_verifier import (
    VisualIdentityVerifier,
)


verifier = VisualIdentityVerifier()

tests = [
    (
        "b1",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_015.jpg",
        [
            "commercial jet airplane in flight",
            "aircraft with turbofan engine visible",
            "jet engine intake on airplane",
        ],
        [
            "metal kettle",
            "tea kettle with steam",
            "small household appliance",
            "generic mechanical demonstration model",
        ],
    ),
    (
        "b5",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_034.jpg",
        [
            "jet engine combustion chamber",
            "turbofan combustion section",
            "jet engine fuel combustion",
        ],
        [
            "kettle",
            "steam demonstration",
            "generic pressure apparatus",
            "unrelated mechanical model",
        ],
    ),
]

for name, path, positive, negative in tests:

    result = verifier.verify(
        image_path=path,
        required_prompts=positive,
        reject_prompts=negative,
    )

    print()
    print(
        name,
        result.to_dict(),
    )

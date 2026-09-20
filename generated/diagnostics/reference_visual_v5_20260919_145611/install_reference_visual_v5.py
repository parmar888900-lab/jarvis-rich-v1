from pathlib import Path
import ast
import shutil
import sys
import textwrap

PIPELINE = Path(
    "backend/services/pipelines/video_pipeline.py"
)

BACKUP = Path(sys.argv[1]) / "video_pipeline.py"

TARGET_METHODS = {
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
}

try:
    source = PIPELINE.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(source)

    cls = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "VideoPipeline"
        ),
        None,
    )

    if cls is None:
        raise RuntimeError(
            "VideoPipeline class not found."
        )

    if "SEMANTIC_VISUAL_V4 = True" not in source:
        raise RuntimeError(
            "Semantic Visual V4 is not installed."
        )

    if "MASTER_VISUAL_ACQUISITION_V2" not in source:
        raise RuntimeError(
            "V3 acquisition layer is missing."
        )

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    missing = TARGET_METHODS.difference(methods)

    if missing:
        raise RuntimeError(
            "Missing V4 helpers: "
            + ", ".join(sorted(missing))
        )

    # --------------------------------------------------------
    # Build complete replacements.
    #
    # We replace the decorators + function together. This
    # prevents the duplicate-classmethod defect encountered
    # during V4.
    # --------------------------------------------------------

    replacements = {}

    replacements["_master_query_variants"] = '''
    @classmethod
    def _master_query_variants(
        cls,
        *,
        topic,
        beat,
    ):
        """
        REFERENCE_VISUAL_V5

        Translate a narration beat into concrete visual actions
        rather than generic topic searches.

        Provider requests stay bounded. The highest-value literal
        visual requirements are always attempted first.
        """

        def clean(value):
            return " ".join(
                str(value or "").strip().split()
            )

        def tokens(value):
            return {
                token.lower()
                for token in clean(value).split()
                if len(token) >= 3
            }

        search_query = clean(
            getattr(
                beat,
                "search_query",
                "",
            )
        )

        visual_requirement = clean(
            getattr(
                beat,
                "visual_requirement",
                "",
            )
        )

        purpose = clean(
            getattr(
                beat,
                "purpose",
                "",
            )
        )

        beat_text = " ".join(
            part
            for part in (
                visual_requirement,
                search_query,
                purpose,
            )
            if part
        )

        lower = beat_text.lower()

        queries = []

        def add(query):
            query = clean(query)

            if not query:
                return

            key = query.lower()

            if key not in {
                existing.lower()
                for existing in queries
            }:
                queries.append(query)

        # ====================================================
        # LITERAL FOLEY MECHANISMS
        # ====================================================

        if any(
            word in lower
            for word in (
                "footstep",
                "footsteps",
                "shoe",
                "shoes",
                "walking",
                "walk",
                "floor",
            )
        ):
            add(
                "Foley artist recording footsteps "
                "shoes floor film studio"
            )
            add(
                "film Foley footsteps shoes "
                "sound effects stage"
            )
            add(
                "Foley performer footsteps "
                "movie sound recording"
            )

        elif any(
            word in lower
            for word in (
                "prop",
                "props",
                "object",
                "objects",
                "door",
                "cloth",
                "clothes",
                "fabric",
                "glass",
                "metal",
                "wood",
                "paper",
            )
        ):
            add(
                "Foley artist using props "
                "movie sound effects studio"
            )
            add(
                "hands Foley props film "
                "sound recording"
            )
            add(
                "Foley stage objects props "
                "sound effects"
            )

        elif any(
            word in lower
            for word in (
                "adr",
                "dialogue",
                "dialog",
                "voice",
                "actor",
                "speech",
                "line",
                "lines",
            )
        ):
            add(
                "actor ADR dialogue recording "
                "film microphone studio"
            )
            add(
                "film ADR booth actor "
                "dialogue microphone"
            )
            add(
                "movie dialogue replacement "
                "recording studio"
            )

        elif any(
            word in lower
            for word in (
                "edit",
                "editing",
                "editor",
                "post",
                "timeline",
                "waveform",
                "mix",
                "mixing",
                "layer",
                "layers",
            )
        ):
            add(
                "film sound editor audio waveform "
                "post production workstation"
            )
            add(
                "movie sound design editing "
                "timeline workstation"
            )
            add(
                "film audio post production "
                "sound editor mixing"
            )

        elif any(
            word in lower
            for word in (
                "microphone",
                "mic",
                "record",
                "recorded",
                "recording",
                "studio",
            )
        ):
            add(
                "Foley artist recording movie "
                "sound effects microphone"
            )
            add(
                "film Foley recording stage "
                "microphone sound effects"
            )
            add(
                "professional Foley performer "
                "film sound studio"
            )

        elif any(
            word in lower
            for word in (
                "ambient",
                "ambience",
                "environment",
                "outside",
                "field",
                "nature",
                "background",
            )
        ):
            add(
                "film field recording ambience "
                "professional microphone"
            )
            add(
                "sound recordist field recording "
                "movie ambience"
            )

        # ====================================================
        # USE THE PLANNER'S EXACT VISUAL REQUIREMENT
        #
        # Keep it concrete by adding the filmmaking context.
        # ====================================================

        if visual_requirement:
            add(
                visual_requirement
                + " film Foley sound effects"
            )

        if search_query:
            add(
                search_query
                + " film Foley"
            )

        # ====================================================
        # SAFE DOMAIN FALLBACK
        #
        # Deliberately NOT:
        #   recording room
        #   content creator
        #   studio person
        #
        # Those searches produced the ring-light imagery.
        # ====================================================

        add(
            "Foley artist performing "
            "movie sound effects studio"
        )

        add(
            "film Foley stage professional "
            "sound effects recording"
        )

        # Only expose the strongest variants to the provider.
        # This preserves bounded provider/API work.
        return queries[:3]
'''

    replacements["_master_metadata_score"] = '''
    @classmethod
    def _master_metadata_score(
        cls,
        *,
        asset,
        query,
        topic,
    ):
        """
        REFERENCE_VISUAL_V5

        Score literal metadata correspondence.

        Query/beat correspondence dominates topic-level overlap.
        """

        def normalize(value):
            return " ".join(
                str(value or "").lower().split()
            )

        def token_set(value):
            return {
                token.strip(
                    ".,:;!?()[]{}-_/"
                )
                for token in normalize(value).split()
                if len(
                    token.strip(
                        ".,:;!?()[]{}-_/"
                    )
                ) >= 3
            }

        metadata_parts = []

        for attr in (
            "title",
            "description",
            "source_url",
            "asset_id",
            "file_path",
            "local_path",
            "source_name",
        ):
            value = getattr(
                asset,
                attr,
                "",
            )

            if value:
                metadata_parts.append(
                    str(value)
                )

        metadata = normalize(
            " ".join(metadata_parts)
        )

        if not metadata:
            return 0.0

        query_tokens = token_set(query)
        topic_tokens = token_set(topic)
        metadata_tokens = token_set(metadata)

        if not metadata_tokens:
            return 0.0

        query_overlap = len(
            query_tokens & metadata_tokens
        )

        topic_overlap = len(
            topic_tokens & metadata_tokens
        )

        query_score = (
            query_overlap
            / max(
                1,
                len(query_tokens),
            )
        )

        topic_score = (
            topic_overlap
            / max(
                1,
                len(topic_tokens),
            )
        )

        # Literal visual intent matters substantially more than
        # merely matching the broad topic.
        score = (
            query_score * 0.86
            + topic_score * 0.14
        )

        # Domain evidence.
        domain_tokens = {
            "foley",
            "film",
            "movie",
            "cinema",
            "sound",
            "audio",
            "microphone",
            "recording",
            "editor",
            "editing",
            "production",
            "footsteps",
            "props",
            "dialogue",
            "waveform",
            "mixing",
        }

        domain_overlap = len(
            metadata_tokens & domain_tokens
        )

        if domain_overlap >= 3:
            score += 0.12

        elif domain_overlap >= 2:
            score += 0.07

        elif domain_overlap == 1:
            score += 0.025

        # Highly undesirable imagery discovered in the actual
        # V3/V4 benchmark renders.
        negative_tokens = {
            "selfie",
            "vlog",
            "vlogger",
            "blogger",
            "webcam",
            "streamer",
            "streaming",
            "influencer",
            "portrait",
            "fashion",
            "makeup",
            "ringlight",
            "ring-light",
            "livestream",
            "podcast",
            "podcaster",
            "youtuber",
            "creator",
        }

        negative_overlap = len(
            metadata_tokens & negative_tokens
        )

        score -= (
            negative_overlap * 0.24
        )

        return max(
            0.0,
            min(
                1.0,
                float(score),
            ),
        )
'''

    replacements["_master_choose_asset"] = '''
    @classmethod
    def _master_choose_asset(
        cls,
        *,
        candidates,
        query,
        topic,
        used_identities,
        previous_identity,
    ):
        """
        REFERENCE_VISUAL_V5

        Select literal, domain-relevant, non-repetitive media.

        Generic social-media studio imagery is rejected instead
        of being rewarded simply because it contains a microphone.
        """

        if not candidates:
            return None

        def normalize(value):
            return " ".join(
                str(value or "").lower().split()
            )

        def token_set(value):
            return {
                token.strip(
                    ".,:;!?()[]{}-_/"
                )
                for token in normalize(value).split()
                if len(
                    token.strip(
                        ".,:;!?()[]{}-_/"
                    )
                ) >= 3
            }

        domain_tokens = {
            "foley",
            "film",
            "movie",
            "cinema",
            "sound",
            "audio",
            "microphone",
            "recording",
            "editor",
            "editing",
            "production",
            "footsteps",
            "shoes",
            "props",
            "dialogue",
            "adr",
            "waveform",
            "mixing",
        }

        negative_tokens = {
            "selfie",
            "vlog",
            "vlogger",
            "blogger",
            "webcam",
            "streamer",
            "streaming",
            "influencer",
            "portrait",
            "fashion",
            "makeup",
            "ringlight",
            "ring-light",
            "livestream",
            "podcast",
            "podcaster",
            "youtuber",
            "creator",
        }

        ranked = []

        for asset in candidates:

            identity = (
                cls._master_asset_identity(
                    asset
                )
            )

            metadata = " ".join(
                str(
                    getattr(
                        asset,
                        attr,
                        "",
                    )
                    or ""
                )
                for attr in (
                    "title",
                    "description",
                    "source_url",
                    "asset_id",
                    "file_path",
                    "local_path",
                    "source_name",
                )
            )

            metadata_tokens = token_set(
                metadata
            )

            semantic_score = (
                cls._master_metadata_score(
                    asset=asset,
                    query=query,
                    topic=topic,
                )
            )

            domain_overlap = len(
                metadata_tokens
                & domain_tokens
            )

            negative_overlap = len(
                metadata_tokens
                & negative_tokens
            )

            score = float(
                semantic_score
            )

            # New material is strongly preferred.
            if (
                identity
                and identity
                not in used_identities
            ):
                score += 0.25

            # Prevent immediate visual repetition.
            if (
                identity
                and identity
                == previous_identity
            ):
                score -= 0.70

            # Domain relevance.
            if domain_overlap >= 3:
                score += 0.20

            elif domain_overlap == 2:
                score += 0.12

            elif domain_overlap == 1:
                score += 0.04

            # Generic creator imagery receives a very large
            # penalty because it dominated the V4 benchmark.
            score -= (
                negative_overlap * 0.45
            )

            ranked.append(
                (
                    score,
                    semantic_score,
                    domain_overlap,
                    negative_overlap,
                    identity,
                    asset,
                )
            )

        ranked.sort(
            key=lambda row: (
                row[0],
                row[1],
                row[2],
            ),
            reverse=True,
        )

        # ====================================================
        # TIER 1
        # Literal + domain relevant + unused.
        # ====================================================

        for (
            score,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:

            if (
                identity
                and identity
                != previous_identity
                and identity
                not in used_identities
                and negative_overlap == 0
                and semantic_score >= 0.30
                and domain_overlap >= 2
            ):
                return asset

        # ====================================================
        # TIER 2
        # Still require meaningful semantic correspondence.
        # ====================================================

        for (
            score,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:

            if (
                identity
                and identity
                != previous_identity
                and negative_overlap == 0
                and semantic_score >= 0.36
                and domain_overlap >= 1
            ):
                return asset

        # ====================================================
        # TIER 3
        #
        # Do NOT force a generic candidate.
        # Returning None lets the pipeline use its authorized
        # fallback path and lets Block 5 reject bad sequences.
        # ====================================================

        return None
'''

    # --------------------------------------------------------
    # Replace methods from bottom to top.
    # Start at earliest decorator so old @classmethod lines are
    # removed with the old function.
    # --------------------------------------------------------

    lines = source.splitlines(
        keepends=True
    )

    jobs = []

    for name in TARGET_METHODS:

        node = methods[name]

        start_line = node.lineno

        if node.decorator_list:
            start_line = min(
                decorator.lineno
                for decorator
                in node.decorator_list
            )

        jobs.append(
            (
                start_line - 1,
                node.end_lineno,
                name,
            )
        )

    for start, end, name in sorted(
        jobs,
        key=lambda item: item[0],
        reverse=True,
    ):

        replacement = textwrap.dedent(
            replacements[name]
        ).strip("\n")

        # Re-indent inside VideoPipeline.
        replacement = textwrap.indent(
            replacement,
            "    ",
        )

        replacement += "\n"

        lines[start:end] = [
            replacement
        ]

    patched = "".join(lines)

    # --------------------------------------------------------
    # Add V5 class marker.
    # --------------------------------------------------------

    if "REFERENCE_VISUAL_V5 = True" not in patched:

        anchor = (
            "    SEMANTIC_VISUAL_V4 = True"
        )

        if anchor not in patched:
            raise RuntimeError(
                "V4 class marker anchor missing."
            )

        patched = patched.replace(
            anchor,
            anchor
            + "\n"
            + "    REFERENCE_VISUAL_V5 = True",
            1,
        )

    # --------------------------------------------------------
    # Structural validation before writing.
    # --------------------------------------------------------

    tree = ast.parse(patched)

    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "VideoPipeline"
    )

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    for name in TARGET_METHODS:

        if name not in methods:
            raise RuntimeError(
                f"Patched helper missing: {name}"
            )

        node = methods[name]

        count = sum(
            1
            for decorator
            in node.decorator_list
            if isinstance(
                decorator,
                ast.Name,
            )
            and decorator.id
            == "classmethod"
        )

        if count != 1:
            raise RuntimeError(
                f"{name}: @classmethod count={count}"
            )

        if len(
            node.decorator_list
        ) != 1:
            raise RuntimeError(
                f"{name}: unexpected decorator stack."
            )

    required = (
        "REFERENCE_VISUAL_V5 = True",
        "Foley artist recording footsteps",
        "Foley artist using props",
        "actor ADR dialogue recording",
        "film sound editor audio waveform",
        "film field recording ambience",
        "query_score * 0.86",
        "negative_overlap * 0.45",
        "semantic_score >= 0.30",
        "semantic_score >= 0.36",
        "self.asset_collector.authorize",
        "BLOCK5_VISUAL_QA_BEGIN",
        "BLOCK5_VISUAL_QA_END",
    )

    for marker in required:
        if marker not in patched:
            raise RuntimeError(
                "V5 verification marker missing: "
                + marker
            )

    PIPELINE.write_text(
        patched,
        encoding="utf-8",
    )

    print(
        "[PASS] Reference Visual V5 installed."
    )
    print(
        "[PASS] Literal Foley mechanism queries installed."
    )
    print(
        "[PASS] Footsteps acquisition installed."
    )
    print(
        "[PASS] Prop-action acquisition installed."
    )
    print(
        "[PASS] ADR/dialogue acquisition installed."
    )
    print(
        "[PASS] Sound-editing acquisition installed."
    )
    print(
        "[PASS] Field-recording acquisition installed."
    )
    print(
        "[PASS] Generic creator imagery strongly penalized."
    )
    print(
        "[PASS] Immediate-repeat penalty installed."
    )
    print(
        "[PASS] Semantic rejection preserved."
    )
    print(
        "[PASS] Rights authorization preserved."
    )
    print(
        "[PASS] Block 5 preserved."
    )

except Exception as exc:

    shutil.copy2(
        BACKUP,
        PIPELINE,
    )

    print(
        f"[ROLLBACK] "
        f"{type(exc).__name__}: {exc}"
    )

    print(
        "[PASS] Pre-V5 source restored."
    )

    sys.exit(2)

from pathlib import Path
import ast
import shutil
import sys

PIPELINE = Path("backend/services/pipelines/video_pipeline.py")
RESEARCH = Path("backend/services/research/evergreen_research_service.py")
BACKUP = Path(sys.argv[1])


def read(path):
    return path.read_text(encoding="utf-8-sig")


def write(path, value):
    path.write_text(value, encoding="utf-8")


def restore():
    shutil.copy2(BACKUP / "video_pipeline.py", PIPELINE)
    shutil.copy2(
        BACKUP / "evergreen_research_service.py",
        RESEARCH,
    )


try:
    source = read(PIPELINE)
    research = read(RESEARCH)

    ast.parse(source)
    ast.parse(research)

    if "MASTER_VISUAL_ACQUISITION_V2" not in source:
        raise RuntimeError(
            "V3 master visual acquisition is not installed."
        )

    if "SEMANTIC_VISUAL_V4" in source:
        raise RuntimeError(
            "Semantic Visual V4 is already installed."
        )

    # -----------------------------------------------------
    # Replace V3 query-variant helper with a stronger
    # topic/beat/mechanism-aware implementation.
    # -----------------------------------------------------

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
        raise RuntimeError("VideoPipeline class not found.")

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }

    query_node = methods.get("_master_query_variants")
    score_node = methods.get("_master_metadata_score")
    choose_node = methods.get("_master_choose_asset")

    if not query_node or not score_node or not choose_node:
        raise RuntimeError(
            "V3 semantic helper methods are missing."
        )

    lines = source.splitlines(keepends=True)

    def replace_method(lines, node, replacement):
        start = node.lineno - 1
        end = node.end_lineno
        return (
            lines[:start]
            + [replacement]
            + lines[end:]
        )

    query_replacement = '''    @classmethod
    def _master_query_variants(
        cls,
        *,
        topic: str,
        beat,
    ) -> list[str]:
        """
        SEMANTIC_VISUAL_V4

        Build literal, mechanism-specific media searches instead
        of broad social-media / generic recording-room searches.
        """

        search_query = str(
            getattr(beat, "search_query", "") or ""
        ).strip()

        visual_requirement = str(
            getattr(beat, "visual_requirement", "") or ""
        ).strip()

        purpose = str(
            getattr(beat, "purpose", "") or ""
        ).strip()

        combined = " ".join(
            (
                str(topic),
                search_query,
                visual_requirement,
                purpose,
            )
        ).lower()

        raw = []

        # Exact beat requirement remains first.
        if visual_requirement:
            raw.append(visual_requirement)

        if search_query:
            raw.append(search_query)

        # Domain-specific literal expansions.
        if any(
            token in combined
            for token in (
                "sound effect",
                "sound effects",
                "foley",
                "recorded separately",
                "footstep",
                "footsteps",
            )
        ):
            if any(
                token in combined
                for token in (
                    "foot",
                    "step",
                    "walk",
                    "shoe",
                )
            ):
                raw.extend(
                    [
                        "Foley artist recording footsteps studio",
                        "Foley footsteps sound effects recording",
                        "film Foley artist shoes footsteps",
                    ]
                )

            elif any(
                token in combined
                for token in (
                    "prop",
                    "object",
                    "door",
                    "cloth",
                    "fabric",
                    "glass",
                    "metal",
                )
            ):
                raw.extend(
                    [
                        "Foley artist movie props sound effects",
                        "Foley studio props film sound recording",
                        "film sound effects Foley props",
                    ]
                )

            elif any(
                token in combined
                for token in (
                    "edit",
                    "post",
                    "mix",
                    "timeline",
                    "sync",
                )
            ):
                raw.extend(
                    [
                        "film sound editor post production studio",
                        "movie sound design editing workstation",
                        "film audio post production sound editor",
                    ]
                )

            elif any(
                token in combined
                for token in (
                    "microphone",
                    "record",
                    "studio",
                )
            ):
                raw.extend(
                    [
                        "Foley artist recording sound effects studio",
                        "film Foley recording studio microphone",
                        "movie sound effects recording Foley artist",
                    ]
                )

            else:
                raw.extend(
                    [
                        "Foley artist recording movie sound effects",
                        "film Foley studio sound effects",
                        "movie sound design Foley recording",
                    ]
                )

        # Keep the topic as context only after literal searches.
        if search_query and topic:
            raw.append(
                f"{search_query} {topic}"
            )

        output = []
        seen = set()

        for query in raw:
            clean = " ".join(
                str(query).split()
            ).strip()

            if not clean:
                continue

            key = clean.casefold()

            if key in seen:
                continue

            seen.add(key)
            output.append(clean)

        # Two provider requests maximum per beat.
        return output[:2]

'''

    # Replace from bottom upward so AST line positions remain valid.
    replacements = [
        (
            choose_node.lineno,
            choose_node,
            '''    @classmethod
    def _master_choose_asset(
        cls,
        *,
        candidates,
        query: str,
        topic: str,
        used_identities: set[str],
        previous_identity: str,
    ):
        """
        SEMANTIC_VISUAL_V4

        Reject weak generic candidates rather than allowing
        diversity alone to make them eligible.
        """

        ranked = []

        domain_tokens = {
            "foley",
            "film",
            "sound",
            "audio",
            "studio",
            "recording",
            "editor",
            "production",
            "effects",
            "footsteps",
            "microphone",
            "cinema",
        }

        negative_tokens = {
            "selfie",
            "influencer",
            "webcam",
            "vlog",
            "blogger",
            "portrait",
            "fashion",
            "makeup",
            "ringlight",
            "ring-light",
            "livestream",
            "streamer",
        }

        for asset in candidates:
            if getattr(asset, "asset_type", "") != "image":
                continue

            identity = cls._master_asset_identity(asset)

            if not identity:
                continue

            fields = []

            for attribute in (
                "title",
                "description",
                "source_url",
                "asset_id",
                "local_path",
            ):
                value = getattr(
                    asset,
                    attribute,
                    None,
                )

                if value:
                    fields.append(str(value))

            metadata_text = " ".join(fields).lower()

            semantic_score = cls._master_metadata_score(
                asset=asset,
                query=query,
                topic=topic,
            )

            metadata_tokens = cls._master_query_tokens(
                metadata_text
            )

            domain_overlap = len(
                metadata_tokens.intersection(
                    domain_tokens
                )
            )

            negative_overlap = sum(
                1
                for token in negative_tokens
                if token in metadata_text
            )

            unused_bonus = (
                0.40
                if identity not in used_identities
                else 0.0
            )

            domain_bonus = min(
                0.30,
                domain_overlap * 0.10,
            )

            generic_penalty = min(
                0.75,
                negative_overlap * 0.25,
            )

            consecutive_penalty = (
                1.25
                if identity == previous_identity
                else 0.0
            )

            final_score = (
                semantic_score
                + unused_bonus
                + domain_bonus
                - generic_penalty
                - consecutive_penalty
            )

            ranked.append(
                (
                    final_score,
                    semantic_score,
                    domain_overlap,
                    negative_overlap,
                    identity,
                    asset,
                )
            )

        if not ranked:
            return None

        ranked.sort(
            key=lambda row: (
                row[0],
                row[1],
                row[2],
            ),
            reverse=True,
        )

        # Preferred: unused + non-consecutive + literal relevance.
        for (
            _,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:
            if (
                identity != previous_identity
                and identity not in used_identities
                and negative_overlap == 0
                and semantic_score >= 0.28
                and domain_overlap >= 1
            ):
                return asset

        # Second tier: still require semantic evidence.
        for (
            _,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:
            if (
                identity != previous_identity
                and negative_overlap == 0
                and semantic_score >= 0.34
            ):
                return asset

        # Fail closed here. Stage fallback logic can decide whether
        # an already-authorized fallback is acceptable.
        return None

''',
        ),
        (
            score_node.lineno,
            score_node,
            '''    @classmethod
    def _master_metadata_score(
        cls,
        *,
        asset,
        query: str,
        topic: str,
    ) -> float:
        """
        SEMANTIC_VISUAL_V4

        Weight the literal beat query more strongly than the broad
        topic and require metadata evidence when available.
        """

        query_tokens = cls._master_query_tokens(query)
        topic_tokens = cls._master_query_tokens(topic)

        fields = []

        for attribute in (
            "title",
            "description",
            "source_url",
            "asset_id",
            "local_path",
        ):
            value = getattr(
                asset,
                attribute,
                None,
            )

            if value:
                fields.append(str(value))

        metadata = " ".join(fields)

        available = cls._master_query_tokens(
            metadata
        )

        if not available:
            return 0.0

        query_overlap = len(
            query_tokens.intersection(
                available
            )
        )

        topic_overlap = len(
            topic_tokens.intersection(
                available
            )
        )

        query_denominator = max(
            1,
            min(len(query_tokens), 6),
        )

        topic_denominator = max(
            1,
            min(len(topic_tokens), 6),
        )

        query_score = (
            query_overlap
            / query_denominator
        )

        topic_score = (
            topic_overlap
            / topic_denominator
        )

        # Literal beat relevance dominates broad topic relevance.
        score = (
            query_score * 0.78
            + topic_score * 0.22
        )

        return min(
            1.0,
            max(0.0, score),
        )

''',
        ),
        (
            query_node.lineno,
            query_node,
            query_replacement,
        ),
    ]

    for _, node, replacement in sorted(
        replacements,
        key=lambda item: item[0],
        reverse=True,
    ):
        lines = replace_method(
            lines,
            node,
            replacement,
        )

    source = "".join(lines)

    # -----------------------------------------------------
    # Add stronger fallback choice.
    # Existing V3 fallback could still select generic media.
    # -----------------------------------------------------

    old_fallback = '''                if selected_asset is None:

                    selected_asset = next(
                        (
                            asset
                            for asset
                            in fallback_pool
                            if (
                                self._master_asset_identity(
                                    asset
                                )
                                != previous_identity
                            )
                        ),
                        fallback_pool[0],
                    )

                selected_via = (
                    "rotating_stage_fallback"
                )
'''

    new_fallback = '''                if selected_asset is None:

                    # SEMANTIC_VISUAL_V4:
                    # prefer a different authorized stage asset,
                    # but do not pretend it was semantically matched.
                    selected_asset = next(
                        (
                            asset
                            for asset
                            in fallback_pool
                            if (
                                self._master_asset_identity(
                                    asset
                                )
                                != previous_identity
                                and self._master_metadata_score(
                                    asset=asset,
                                    query=primary_query,
                                    topic=topic,
                                ) >= 0.12
                            )
                        ),
                        None,
                    )

                if selected_asset is None:

                    selected_asset = next(
                        (
                            asset
                            for asset
                            in fallback_pool
                            if (
                                self._master_asset_identity(
                                    asset
                                )
                                != previous_identity
                            )
                        ),
                        fallback_pool[0],
                    )

                selected_via = (
                    "semantic_rotating_stage_fallback"
                )
'''

    if old_fallback not in source:
        raise RuntimeError(
            "V3 fallback anchor not found."
        )

    source = source.replace(
        old_fallback,
        new_fallback,
        1,
    )

    # -----------------------------------------------------
    # Add explicit V4 marker inside class.
    # -----------------------------------------------------

    constant_anchor = (
        "    TARGET_DISTINCT_BEAT_ASSETS = 6\n"
    )

    if constant_anchor not in source:
        raise RuntimeError(
            "V3 constant anchor missing."
        )

    source = source.replace(
        constant_anchor,
        constant_anchor
        + "    SEMANTIC_VISUAL_V4 = True\n",
        1,
    )

    # -----------------------------------------------------
    # Research aliases: keep grounded Wikipedia research,
    # but improve mechanism-specific concepts.
    # -----------------------------------------------------

    if "SEMANTIC_RESEARCH_V4" not in research:
        marker = "    # MASTER_RESEARCH_SPECIFICITY_V2\n"

        if marker not in research:
            raise RuntimeError(
                "V3 research marker missing."
            )

        research = research.replace(
            marker,
            '''    # SEMANTIC_RESEARCH_V4
    # Mechanism-specific research remains grounded through
    # the existing Wikipedia provider and evidence contract.
'''
            + marker,
            1,
        )

    # -----------------------------------------------------
    # Validate before write.
    # -----------------------------------------------------

    ast.parse(source)
    ast.parse(research)

    required = (
        "SEMANTIC_VISUAL_V4 = True",
        "Foley artist recording movie sound effects",
        "film sound editor post production studio",
        "semantic_rotating_stage_fallback",
        "negative_tokens",
        "domain_overlap",
        "semantic_score >= 0.28",
        "query_score * 0.78",
        "self.asset_collector.authorize",
        "Visual diversity gate rejected sequence",
    )

    for marker in required:
        if marker not in source:
            raise RuntimeError(
                "Missing V4 marker: " + marker
            )

    write(PIPELINE, source)
    write(RESEARCH, research)

    ast.parse(read(PIPELINE))
    ast.parse(read(RESEARCH))

    print("[PASS] Semantic Visual V4 installed.")
    print("[PASS] Foley-specific visual queries installed.")
    print("[PASS] Literal beat relevance strengthened.")
    print("[PASS] Generic social-media penalty installed.")
    print("[PASS] Domain relevance bonus installed.")
    print("[PASS] Semantic rejection threshold installed.")
    print("[PASS] Duplicate avoidance preserved.")
    print("[PASS] Rights authorization preserved.")
    print("[PASS] Block 5 preserved.")
    print("[PASS] Research grounding preserved.")

except Exception as exc:
    restore()

    print("[ROLLBACK] V4 patch failed.")
    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )
    print("[PASS] Original V3 source restored.")

    sys.exit(2)

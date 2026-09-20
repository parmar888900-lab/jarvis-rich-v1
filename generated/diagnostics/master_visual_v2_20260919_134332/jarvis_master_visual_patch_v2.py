from pathlib import Path
import ast
import shutil
import sys

pipeline_path = Path(
    "backend/services/pipelines/video_pipeline.py"
)

research_path = Path(
    "backend/services/research/evergreen_research_service.py"
)

backup = Path(sys.argv[1])


def read(path):
    return path.read_text(
        encoding="utf-8-sig"
    )


def write(path, text):
    path.write_text(
        text,
        encoding="utf-8"
    )


def syntax(path, text):
    compile(
        text,
        str(path),
        "exec",
    )


def restore():
    shutil.copy2(
        backup / "video_pipeline.py",
        pipeline_path,
    )

    shutil.copy2(
        backup / "evergreen_research_service.py",
        research_path,
    )


try:
    pipeline = read(pipeline_path)
    research = read(research_path)

    syntax(
        pipeline_path,
        pipeline,
    )

    syntax(
        research_path,
        research,
    )

    # ======================================================
    # CONSTANTS
    # ======================================================

    old_constants = (
        "    MAX_SEMANTIC_MEDIA_ENRICHMENTS = 6\n"
    )

    new_constants = '''    MAX_SEMANTIC_MEDIA_ENRICHMENTS = 10

    # MASTER_VISUAL_ACQUISITION_V2
    STAGE_MEDIA_CANDIDATE_LIMIT = 3
    BEAT_MEDIA_CANDIDATE_LIMIT = 3
    TARGET_DISTINCT_BEAT_ASSETS = 6
'''

    if old_constants not in pipeline:
        raise RuntimeError(
            "Pipeline constants anchor not found."
        )

    pipeline = pipeline.replace(
        old_constants,
        new_constants,
        1,
    )

    # ======================================================
    # IMPORT RE
    # ======================================================

    if (
        "\nimport re\n" not in pipeline
        and not pipeline.startswith("import re\n")
    ):
        anchor = (
            "from backend.services.content_generator "
            "import ContentGenerator"
        )

        if anchor not in pipeline:
            raise RuntimeError(
                "Pipeline import anchor not found."
            )

        pipeline = pipeline.replace(
            anchor,
            "import re\n\n" + anchor,
            1,
        )

    # ======================================================
    # STAGE ACQUISITION
    # ======================================================

    old_stage = '''                found = await (
                    self.media_provider
                    .search_and_download(
                        query=query,
                        content_id=content_id,
                        limit=1,
                    )
                )

                if not found:
                    continue

                try:
                    authorized = (
                        self.asset_collector.authorize(
                            found,
                            content_id=content_id,
                        )
                    )
                except RuntimeError:
                    continue

                image_asset = next(
                    (
                        asset
                        for asset in authorized
                        if asset.asset_type
                        == "image"
                    ),
                    None,
                )

                if image_asset is None:
                    continue

                authorized_scene_assets.append(
                    image_asset
                )

                # Current renderer needs only one image
                # per narration scene. Stop immediately.
                break
'''

    new_stage = '''                found = await (
                    self.media_provider
                    .search_and_download(
                        query=query,
                        content_id=content_id,
                        limit=(
                            self.STAGE_MEDIA_CANDIDATE_LIMIT
                        ),
                    )
                )

                if not found:
                    continue

                try:
                    authorized = (
                        self.asset_collector.authorize(
                            found,
                            content_id=content_id,
                        )
                    )
                except RuntimeError:
                    continue

                for image_asset in authorized:

                    if (
                        image_asset.asset_type
                        != "image"
                    ):
                        continue

                    identity = (
                        self._master_asset_identity(
                            image_asset
                        )
                    )

                    existing_ids = {
                        self._master_asset_identity(
                            existing
                        )
                        for existing
                        in authorized_scene_assets
                    }

                    if (
                        identity
                        and identity
                        not in existing_ids
                    ):
                        authorized_scene_assets.append(
                            image_asset
                        )

                    if (
                        len(authorized_scene_assets)
                        >= self.STAGE_MEDIA_CANDIDATE_LIMIT
                    ):
                        break

                if (
                    len(authorized_scene_assets)
                    >= self.STAGE_MEDIA_CANDIDATE_LIMIT
                ):
                    break
'''

    if old_stage not in pipeline:
        raise RuntimeError(
            "Stage acquisition anchor not found."
        )

    pipeline = pipeline.replace(
        old_stage,
        new_stage,
        1,
    )

    # ======================================================
    # HELPER METHODS
    # ======================================================

    tree = ast.parse(pipeline)

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

    run_node = next(
        (
            node
            for node in cls.body
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == "run"
        ),
        None,
    )

    if run_node is None:
        raise RuntimeError(
            "VideoPipeline.run not found."
        )

    helpers = '''
    # MASTER_VISUAL_HELPERS_V2

    @staticmethod
    def _master_asset_identity(asset) -> str:

        if asset is None:
            return ""

        for attribute in (
            "local_path",
            "source_url",
            "asset_id",
        ):

            value = getattr(
                asset,
                attribute,
                None,
            )

            if value:
                return (
                    str(value)
                    .strip()
                    .lower()
                )

        if isinstance(asset, dict):

            for key in (
                "local_path",
                "source_url",
                "asset_id",
            ):

                value = asset.get(key)

                if value:
                    return (
                        str(value)
                        .strip()
                        .lower()
                    )

        return (
            str(asset)
            .strip()
            .lower()
        )

    @staticmethod
    def _master_query_tokens(
        value: str,
    ) -> set[str]:

        stop = {
            "about",
            "after",
            "again",
            "also",
            "because",
            "before",
            "being",
            "could",
            "does",
            "from",
            "have",
            "into",
            "movie",
            "movies",
            "often",
            "some",
            "that",
            "their",
            "there",
            "these",
            "they",
            "this",
            "those",
            "through",
            "using",
            "very",
            "what",
            "when",
            "where",
            "which",
            "while",
            "with",
            "would",
        }

        words = re.findall(
            r"[A-Za-z0-9][A-Za-z0-9'-]+",
            str(value).lower(),
        )

        return {
            word
            for word in words
            if len(word) >= 4
            and word not in stop
        }

    @classmethod
    def _master_query_variants(
        cls,
        *,
        topic: str,
        beat,
    ) -> list[str]:

        raw = []

        search_query = str(
            getattr(
                beat,
                "search_query",
                "",
            )
            or ""
        ).strip()

        visual_requirement = str(
            getattr(
                beat,
                "visual_requirement",
                "",
            )
            or ""
        ).strip()

        purpose = str(
            getattr(
                beat,
                "purpose",
                "",
            )
            or ""
        ).strip()

        clean_topic = " ".join(
            str(topic).split()
        ).strip()

        if search_query:
            raw.append(
                search_query
            )

        if visual_requirement:
            raw.append(
                visual_requirement
            )

        if (
            search_query
            and clean_topic
        ):
            raw.append(
                f"{search_query} {clean_topic}"
            )

        if (
            visual_requirement
            and clean_topic
        ):
            raw.append(
                f"{visual_requirement} {clean_topic}"
            )

        if (
            purpose
            and search_query
        ):
            raw.append(
                f"{search_query} {purpose}"
            )

        output = []
        seen = set()

        for query in raw:

            clean = " ".join(
                str(query).split()
            ).strip()

            key = clean.casefold()

            if (
                not clean
                or key in seen
            ):
                continue

            seen.add(key)
            output.append(
                clean
            )

        return output[:2]

    @classmethod
    def _master_metadata_score(
        cls,
        *,
        asset,
        query: str,
        topic: str,
    ) -> float:

        query_tokens = (
            cls._master_query_tokens(
                query
            )
        )

        topic_tokens = (
            cls._master_query_tokens(
                topic
            )
        )

        wanted = (
            query_tokens
            | topic_tokens
        )

        if not wanted:
            return 0.5

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
                fields.append(
                    str(value)
                )

        metadata = " ".join(
            fields
        )

        available = (
            cls._master_query_tokens(
                metadata
            )
        )

        if not available:
            return 0.25

        overlap = len(
            wanted.intersection(
                available
            )
        )

        query_overlap = len(
            query_tokens.intersection(
                available
            )
        )

        denominator = max(
            1,
            min(
                len(wanted),
                6,
            ),
        )

        score = (
            overlap
            / denominator
        )

        if query_overlap:
            score += 0.25

        return min(
            1.0,
            score,
        )

    @classmethod
    def _master_choose_asset(
        cls,
        *,
        candidates,
        query: str,
        topic: str,
        used_identities: set[str],
        previous_identity: str,
    ):

        ranked = []

        for asset in candidates:

            if getattr(
                asset,
                "asset_type",
                "",
            ) != "image":
                continue

            identity = (
                cls._master_asset_identity(
                    asset
                )
            )

            if not identity:
                continue

            semantic_score = (
                cls._master_metadata_score(
                    asset=asset,
                    query=query,
                    topic=topic,
                )
            )

            unused_bonus = (
                0.45
                if identity
                not in used_identities
                else 0.0
            )

            consecutive_penalty = (
                1.0
                if identity
                == previous_identity
                else 0.0
            )

            final_score = (
                semantic_score
                + unused_bonus
                - consecutive_penalty
            )

            ranked.append(
                (
                    final_score,
                    semantic_score,
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
            ),
            reverse=True,
        )

        for (
            _,
            semantic_score,
            identity,
            asset,
        ) in ranked:

            if (
                identity
                != previous_identity
                and identity
                not in used_identities
                and semantic_score >= 0.20
            ):
                return asset

        for (
            _,
            semantic_score,
            identity,
            asset,
        ) in ranked:

            if (
                identity
                != previous_identity
                and semantic_score >= 0.20
            ):
                return asset

        return None

'''

    lines = pipeline.splitlines(
        keepends=True
    )

    lines.insert(
        run_node.lineno - 1,
        helpers,
    )

    pipeline = "".join(
        lines
    )

    # ======================================================
    # BEAT ASSIGNMENT
    # ======================================================

    start_marker = '''        beat_render_assets = []
        beat_media_evidence = []
'''

    end_marker = '''        if (
            len(beat_render_assets)
            != len(visual_beats)
        ):
'''

    start = pipeline.find(
        start_marker
    )

    if start < 0:
        raise RuntimeError(
            "Beat assignment start anchor not found."
        )

    end = pipeline.find(
        end_marker,
        start,
    )

    if end < 0:
        raise RuntimeError(
            "Beat assignment end anchor not found."
        )

    old_region = pipeline[
        start:end
    ]

    if (
        "semantic_enrichment_attempts"
        not in old_region
        or "stage_fallback"
        not in old_region
    ):
        raise RuntimeError(
            "Unexpected Stage 2B structure."
        )

    new_region = '''        beat_render_assets = []
        beat_media_evidence = []

        semantic_enrichment_attempts = 0
        semantic_enrichment_successes = 0
        semantic_fallback_count = 0

        master_candidate_count = 0
        master_semantic_rejections = 0
        master_duplicate_avoidance_events = 0
        master_query_count = 0

        used_identities: set[str] = set()
        previous_identity = ""

        for beat_index, beat in enumerate(
            visual_beats
        ):

            narration_index = int(
                beat.narration_index
            )

            stage_index = max(
                0,
                min(
                    narration_index - 1,
                    len(media_groups) - 1,
                ),
            )

            stage_candidates = [
                asset
                for asset
                in media_groups[stage_index]
                if asset.asset_type == "image"
            ]

            if not stage_candidates:
                raise RuntimeError(
                    "Stage 2B fallback media missing for "
                    f"narration stage {narration_index}."
                )

            query_variants = (
                self._master_query_variants(
                    topic=topic,
                    beat=beat,
                )
            )

            primary_query = (
                query_variants[0]
                if query_variants
                else str(
                    beat.search_query
                ).strip()
            )

            selected_asset = None
            selected_via = ""
            authorized_candidates = []

            for query in query_variants:

                if (
                    semantic_enrichment_attempts
                    >= self.MAX_SEMANTIC_MEDIA_ENRICHMENTS
                ):
                    break

                semantic_enrichment_attempts += 1
                master_query_count += 1

                try:

                    found = await (
                        self.media_provider
                        .search_and_download(
                            query=query,
                            content_id=content_id,
                            limit=(
                                self.BEAT_MEDIA_CANDIDATE_LIMIT
                            ),
                        )
                    )

                except Exception:

                    found = []

                if not found:
                    continue

                try:

                    authorized = (
                        self.asset_collector.authorize(
                            found,
                            content_id=content_id,
                        )
                    )

                except RuntimeError:

                    authorized = []

                images = [
                    asset
                    for asset in authorized
                    if asset.asset_type == "image"
                ]

                master_candidate_count += len(
                    images
                )

                authorized_candidates.extend(
                    images
                )

                candidate = (
                    self._master_choose_asset(
                        candidates=images,
                        query=query,
                        topic=topic,
                        used_identities=(
                            used_identities
                        ),
                        previous_identity=(
                            previous_identity
                        ),
                    )
                )

                if candidate is not None:

                    selected_asset = candidate

                    selected_via = (
                        "semantic_query_diverse"
                    )

                    semantic_enrichment_successes += 1

                    break

                master_semantic_rejections += len(
                    images
                )

            if selected_asset is None:

                fallback_pool = list(
                    stage_candidates
                )

                if fallback_pool:

                    shift = (
                        beat_index
                        % len(fallback_pool)
                    )

                    fallback_pool = (
                        fallback_pool[shift:]
                        + fallback_pool[:shift]
                    )

                selected_asset = (
                    self._master_choose_asset(
                        candidates=fallback_pool,
                        query=primary_query,
                        topic=topic,
                        used_identities=(
                            used_identities
                        ),
                        previous_identity=(
                            previous_identity
                        ),
                    )
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
                    "rotating_stage_fallback"
                )

                semantic_fallback_count += 1

            identity = (
                self._master_asset_identity(
                    selected_asset
                )
            )

            if (
                identity
                and identity
                == previous_identity
            ):

                alternatives = (
                    authorized_candidates
                    + stage_candidates
                )

                replacement = next(
                    (
                        asset
                        for asset
                        in alternatives
                        if (
                            self._master_asset_identity(
                                asset
                            )
                            and self._master_asset_identity(
                                asset
                            )
                            != previous_identity
                        )
                    ),
                    None,
                )

                if replacement is not None:

                    master_duplicate_avoidance_events += 1

                    selected_asset = replacement

                    identity = (
                        self._master_asset_identity(
                            selected_asset
                        )
                    )

                    selected_via += (
                        "_duplicate_avoided"
                    )

            if identity:
                used_identities.add(
                    identity
                )

            previous_identity = identity

            beat_render_assets.append(
                selected_asset
            )

            beat_media_evidence.append(
                {
                    "beat_id": beat.beat_id,
                    "narration_index": narration_index,
                    "purpose": beat.purpose,
                    "query": primary_query,
                    "query_variants": query_variants,
                    "selected_via": selected_via,
                    "asset_id": selected_asset.asset_id,
                    "source_name": selected_asset.source_name,
                    "source_url": selected_asset.source_url,
                    "license_name": selected_asset.license_name,
                    "commercial_use_allowed": (
                        selected_asset
                        .commercial_use_allowed
                    ),
                }
            )

'''

    pipeline = (
        pipeline[:start]
        + new_region
        + pipeline[end:]
    )

    # ======================================================
    # RESEARCH SPECIFICITY
    # ======================================================

    alias_anchor = (
        "    RESEARCH_ALIASES = {\n"
    )

    if alias_anchor not in research:
        raise RuntimeError(
            "Research alias anchor not found."
        )

    research = research.replace(
        alias_anchor,
        '''    # MASTER_RESEARCH_SPECIFICITY_V2
    RESEARCH_ALIASES = {
        "sound effect": [
            "Foley (filmmaking)",
            "Sound effect",
            "Sound design",
            "Post-production",
        ],
        "sound effects": [
            "Foley (filmmaking)",
            "Sound effect",
            "Sound design",
            "Post-production",
        ],
        "recorded separately": [
            "Foley (filmmaking)",
            "Sound effect",
            "Post-production",
        ],
''',
        1,
    )

    old_source_limit = '''            # Two good background sources are enough
            # for the first Rich V1 integration test.
            if len(pack.sources) >= 2:
                break
'''

    new_source_limit = '''            # MASTER_RESEARCH_SPECIFICITY_V2:
            # retain a bounded evidence set while allowing
            # mechanism-specific sources to supplement broad pages.
            if len(pack.sources) >= 4:
                break
'''

    if old_source_limit not in research:
        raise RuntimeError(
            "Research source-limit anchor not found."
        )

    research = research.replace(
        old_source_limit,
        new_source_limit,
        1,
    )

    # ======================================================
    # PRE-WRITE VALIDATION
    # ======================================================

    syntax(
        pipeline_path,
        pipeline,
    )

    syntax(
        research_path,
        research,
    )

    required = (
        "MASTER_VISUAL_ACQUISITION_V2",
        "MASTER_VISUAL_HELPERS_V2",
        "STAGE_MEDIA_CANDIDATE_LIMIT = 3",
        "BEAT_MEDIA_CANDIDATE_LIMIT = 3",
        "_master_asset_identity",
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
        "semantic_query_diverse",
        "rotating_stage_fallback",
        "master_candidate_count",
        "master_duplicate_avoidance_events",
        "Visual diversity gate rejected sequence",
        "self.asset_collector.authorize",
    )

    for marker in required:

        if marker not in pipeline:

            raise RuntimeError(
                "Required pipeline marker missing: "
                + marker
            )

    required_research = (
        "MASTER_RESEARCH_SPECIFICITY_V2",
        "Foley (filmmaking)",
        "Sound effect",
        "Post-production",
        "if len(pack.sources) >= 4:",
    )

    for marker in required_research:

        if marker not in research:

            raise RuntimeError(
                "Required research marker missing: "
                + marker
            )

    write(
        pipeline_path,
        pipeline,
    )

    write(
        research_path,
        research,
    )

    syntax(
        pipeline_path,
        read(pipeline_path),
    )

    syntax(
        research_path,
        read(research_path),
    )

    print(
        "[PASS] Master visual V2 patch installed."
    )

    print(
        "[PASS] Multi-candidate stage acquisition."
    )

    print(
        "[PASS] Multi-candidate beat acquisition."
    )

    print(
        "[PASS] Query variants installed."
    )

    print(
        "[PASS] Duplicate avoidance installed."
    )

    print(
        "[PASS] Rotating fallback installed."
    )

    print(
        "[PASS] Semantic metadata ranking installed."
    )

    print(
        "[PASS] Research specificity installed."
    )

    print(
        "[PASS] Block 5 marker preserved."
    )

    print(
        "[PASS] Rights authorization preserved."
    )

except Exception as exc:

    restore()

    print(
        "[ROLLBACK] Patch failed."
    )

    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )

    print(
        "[PASS] Original source restored."
    )

    sys.exit(2)

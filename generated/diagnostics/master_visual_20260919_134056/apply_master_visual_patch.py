from pathlib import Path
import ast
import re
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

def syntax(text, path):
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

    syntax(pipeline, pipeline_path)
    syntax(research, research_path)

    # ==========================================================
    # MASTER VISUAL ACQUISITION V1
    #
    # Existing behavior:
    # - stage acquisition stops after first authorized image
    # - beat enrichment requests limit=1
    # - fallback always chooses first stage image
    #
    # New behavior:
    # - stage acquisition collects several authorized alternatives
    # - beat queries request multiple candidates
    # - exact asset identities are tracked globally
    # - unused candidates are preferred
    # - consecutive duplicates are avoided
    # - stage fallbacks rotate rather than always using asset #1
    # - query variants preserve exact premise/beat semantics
    # - existing rights authorization remains mandatory
    # - existing Block 5 remains final fail-closed QA
    # ==========================================================

    old_constants = '''    MAX_SEMANTIC_MEDIA_ENRICHMENTS = 6
'''

    new_constants = '''    MAX_SEMANTIC_MEDIA_ENRICHMENTS = 10

    # MASTER_VISUAL_ACQUISITION_V1
    #
    # Keep provider traffic bounded while giving the selector enough
    # authorized alternatives to construct a genuinely varied timeline.
    STAGE_MEDIA_CANDIDATE_LIMIT = 3
    BEAT_MEDIA_CANDIDATE_LIMIT = 3
    TARGET_DISTINCT_BEAT_ASSETS = 6
'''

    if old_constants not in pipeline:
        raise RuntimeError(
            "VideoPipeline constants anchor not found."
        )

    pipeline = pipeline.replace(
        old_constants,
        new_constants,
        1,
    )

    # ----------------------------------------------------------
    # Stage acquisition:
    # request several candidates and retain multiple authorized
    # images rather than stopping after image #1.
    # ----------------------------------------------------------

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

                    existing_ids = {
                        self._master_asset_identity(
                            asset
                        )
                        for asset
                        in authorized_scene_assets
                    }

                    identity = (
                        self._master_asset_identity(
                            image_asset
                        )
                    )

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

    # ----------------------------------------------------------
    # Insert deterministic helper methods before run().
    # We locate run() through AST rather than guessing line numbers.
    # ----------------------------------------------------------

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

    if "MASTER_VISUAL_HELPERS_V1" not in pipeline:

        lines = pipeline.splitlines(
            keepends=True
        )

        insert_at = run_node.lineno - 1

        helpers = '''
    # MASTER_VISUAL_HELPERS_V1

    @staticmethod
    def _master_asset_identity(asset) -> str:
        """Stable identity for duplicate avoidance."""

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
    def _master_query_tokens(value: str) -> set[str]:
        """Meaningful lexical tokens for cheap semantic filtering."""

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
        """
        Build literal visual queries without inventing facts.

        Exact beat intent stays first. Topic context is added only
        as a search hint.
        """

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
            raw.append(search_query)

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
            output.append(clean)

        return output[:2]

    @classmethod
    def _master_metadata_score(
        cls,
        *,
        asset,
        query: str,
        topic: str,
    ) -> float:
        """
        Cheap fail-soft semantic score.

        This does NOT replace the rights gate. It only ranks already
        authorized media and rejects obviously unrelated candidates.
        """

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

        metadata = " ".join(fields)

        available = (
            cls._master_query_tokens(
                metadata
            )
        )

        if not available:
            # Unknown metadata remains usable because Block 5
            # still independently validates diversity.
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
            overlap / denominator
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
        """Prefer relevant, globally unused, non-consecutive media."""

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

            score = (
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

            final = (
                score
                + unused_bonus
                - consecutive_penalty
            )

            ranked.append(
                (
                    final,
                    score,
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

        # Prefer a fresh identity whenever one exists.
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

        # Then allow reuse, but never an immediate duplicate
        # when another plausible choice exists.
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

        lines.insert(
            insert_at,
            helpers,
        )

        pipeline = "".join(lines)

    # helper uses re
    if (
        "import re\n" not in pipeline
        and "import re\r\n" not in pipeline
    ):
        # Place after module docstring/import area using AST-safe
        # insertion immediately before first backend import.
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

    # ----------------------------------------------------------
    # Replace Stage 2B beat assignment as one exact contiguous
    # region. Keep downstream Block 5 untouched.
    # ----------------------------------------------------------

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
            "Unexpected live Stage 2B structure."
        )

    new_region = '''        beat_render_assets = []
        beat_media_evidence = []

        semantic_enrichment_attempts = 0
        semantic_enrichment_successes = 0
        semantic_fallback_count = 0

        master_candidate_count = 0
        master_semantic_rejections = 0
        master_duplicate_avoids = 0
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

            # --------------------------------------------------
            # Beat-specific acquisition
            # --------------------------------------------------

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
                    # Wikimedia's provider-level retry/backoff
                    # remains authoritative. Enrichment itself
                    # remains fail-soft.
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

            # --------------------------------------------------
            # Rotating authorized stage fallback
            # --------------------------------------------------

            if selected_asset is None:

                fallback_pool = list(
                    stage_candidates
                )

                # Rotate the fallback starting position so several
                # beats belonging to one narration line do not all
                # automatically receive the same image.
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

                    # Last rights-safe fallback. Prefer anything
                    # except the immediately previous identity.
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
                master_duplicate_avoids += 1

                alternatives = (
                    authorized_candidates
                    + stage_candidates
                )

                replacement = next(
                    (
                        asset
                        for asset in alternatives
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

    # ----------------------------------------------------------
    # Extend existing semantic telemetry without touching Block 5.
    # ----------------------------------------------------------

    telemetry_anchor = '''            "fallback_count": (
                semantic_fallback_count
            ),
'''

    telemetry_replacement = '''            "fallback_count": (
                semantic_fallback_count
            ),
            "candidate_count": (
                master_candidate_count
            ),
            "semantic_rejections": (
                master_semantic_rejections
            ),
            "duplicate_avoidance_events": (
                master_duplicate_avoids
            ),
            "query_count": (
                master_query_count
            ),
            "distinct_selected_assets": len(
                {
                    self._master_asset_identity(
                        asset
                    )
                    for asset
                    in beat_render_assets
                    if self._master_asset_identity(
                        asset
                    )
                }
            ),
'''

    if telemetry_anchor in pipeline:
        pipeline = pipeline.replace(
            telemetry_anchor,
            telemetry_replacement,
            1,
        )

    # ==========================================================
    # RESEARCH SPECIFICITY V1
    #
    # Keep the existing grounded Wikipedia architecture, but add
    # precise concept leads for the sound/film mechanism that exposed
    # the current broad "Sound" / "Sound design" weakness.
    # ==========================================================

    alias_anchor = '''    RESEARCH_ALIASES = {
'''

    if alias_anchor not in research:
        raise RuntimeError(
            "Research aliases anchor not found."
        )

    if "MASTER_RESEARCH_SPECIFICITY_V1" not in research:

        research = research.replace(
            alias_anchor,
            '''    # MASTER_RESEARCH_SPECIFICITY_V1
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

    # The research method currently stops at two sources. Increase the
    # grounded evidence ceiling modestly for more specific mechanisms.
    old_source_comment = '''            # Two good background sources are enough
            # for the first Rich V1 integration test.
            if len(pack.sources) >= 2:
                break
'''

    new_source_comment = '''            # MASTER_RESEARCH_SPECIFICITY_V1:
            # retain a small bounded evidence set, but do not stop
            # after only two broad background pages.
            if len(pack.sources) >= 4:
                break
'''

    if old_source_comment not in research:
        raise RuntimeError(
            "Research source-count anchor not found."
        )

    research = research.replace(
        old_source_comment,
        new_source_comment,
        1,
    )

    syntax(pipeline, pipeline_path)
    syntax(research, research_path)

    write(
        pipeline_path,
        pipeline,
    )

    write(
        research_path,
        research,
    )

    # Final read-back syntax verification.
    syntax(
        read(pipeline_path),
        pipeline_path,
    )

    syntax(
        read(research_path),
        research_path,
    )

    print(
        "[PASS] Master visual acquisition patch installed."
    )
    print(
        "[PASS] Stage candidate pool expanded."
    )
    print(
        "[PASS] Beat candidate pool expanded."
    )
    print(
        "[PASS] Query variants installed."
    )
    print(
        "[PASS] Global duplicate avoidance installed."
    )
    print(
        "[PASS] Rotating authorized fallbacks installed."
    )
    print(
        "[PASS] Metadata relevance ranking installed."
    )
    print(
        "[PASS] Research specificity upgraded."
    )
    print(
        "[PASS] Existing authorization calls preserved."
    )
    print(
        "[PASS] Source syntax verified."
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

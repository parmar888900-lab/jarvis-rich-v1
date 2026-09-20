from pathlib import Path
import html


matches = [
    (
        "b1",
        "Jet airplane in flight → close-up engine intake",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_015.jpg",
        0.2635,
        0.1861,
        0.1612,
    ),
    (
        "b2",
        "3D jet-engine diagram showing fan, compressor, combustion chamber, turbine and nozzle",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_029.jpg",
        0.2581,
        0.1658,
        0.1670,
    ),
    (
        "b3",
        "Fan stage taking in and initially compressing air",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_032.jpg",
        0.3200,
        0.2491,
        0.1830,
    ),
    (
        "b4",
        "Compressor stage increasing air pressure",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_030.jpg",
        0.3089,
        0.2035,
        0.1970,
    ),
    (
        "b5",
        "Combustion chamber with fuel ignition / hot gases",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_034.jpg",
        0.3414,
        0.2309,
        0.2144,
    ),
    (
        "b6",
        "Turbine stage driven by expanding hot gases",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_031.jpg",
        0.2963,
        0.2077,
        0.1821,
    ),
    (
        "b7",
        "Nozzle accelerating exhaust to generate thrust",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_017.jpg",
        0.3015,
        0.2437,
        0.1674,
    ),
    (
        "b8",
        "Complete jet-engine cycle from intake to exhaust",
        "generated/clip_index/strict-jet-engine-test/strict-source-4/clip_019.jpg",
        0.2545,
        0.1516,
        0.1711,
    ),
]

output_dir = Path(
    "generated/audits/strict-jet-matches"
)

output_dir.mkdir(
    parents=True,
    exist_ok=True,
)

cards = []

for beat_id, goal, path_value, pos, neg, final in matches:

    source = Path(path_value).resolve()

    uri = source.as_uri()

    cards.append(
        f"""
        <article class="card">
            <img src="{html.escape(uri)}">
            <div class="body">
                <h2>{html.escape(beat_id)}</h2>
                <p class="goal">{html.escape(goal)}</p>
                <div class="scores">
                    <span>POS {pos:.4f}</span>
                    <span>NEG {neg:.4f}</span>
                    <span>FINAL {final:.4f}</span>
                </div>
                <p class="path">{html.escape(path_value)}</p>
            </div>
        </article>
        """
    )

document = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Jarvis Strict Jet Match Audit</title>

<style>
body {{
    margin: 0;
    padding: 30px;
    background: #111318;
    color: white;
    font-family: Arial, sans-serif;
}}

h1 {{
    margin-bottom: 25px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
}}

.card {{
    background: #1b1f27;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid #333945;
}}

.card img {{
    display: block;
    width: 100%;
    height: 360px;
    object-fit: contain;
    background: black;
}}

.body {{
    padding: 16px;
}}

h2 {{
    margin: 0 0 8px;
}}

.goal {{
    min-height: 48px;
    line-height: 1.4;
}}

.scores {{
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
}}

.scores span {{
    background: #303743;
    border-radius: 8px;
    padding: 6px 9px;
    font-size: 13px;
}}

.path {{
    color: #9299a6;
    font-size: 11px;
    overflow-wrap: anywhere;
}}
</style>
</head>

<body>

<h1>Jarvis — Strict Jet Engine Matches</h1>

<div class="grid">
{''.join(cards)}
</div>

</body>
</html>
"""

output = output_dir / "audit.html"

output.write_text(
    document,
    encoding="utf-8",
)

print(
    "AUDIT:",
    output.resolve(),
)

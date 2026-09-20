"""
End-to-End Test for Jarvis Intelligence & Content Pipeline.
Execute with: python test_pipeline.py
"""

import asyncio
import json
import logging

from backend.services.content_generator import ContentGenerator
from backend.services.intelligence.trend_engine import TrendEngine
from backend.services.providers.registry import build_trend_manager

# Set up logging to observe pipeline logs
logging.basicConfig(level=logging.INFO)


async def main():
    print("\n==================================================")
    print("🚀 STARTING JARVIS INTELLIGENCE PIPELINE INTEGRATION TEST")
    print("==================================================\n")

    # Step 1: Collect Raw Trends from Providers
    print("Step 1: Collecting trends from providers...")
    manager = build_trend_manager()
    raw_trends = manager.get_trends(limit=10)
    print(f"-> Registered Providers: {len(manager.providers)}")
    print(f"-> Raw Trends Fetched: {len(raw_trends)}\n")

    if not raw_trends:
        print("❌ No raw trends fetched. Check your internet connection or provider configuration.")
        return

    # Step 2: Run Trend Engine (Deduplication -> First-pass Scoring -> Research -> Final Scoring)
    print("Step 2: Processing trends through TrendEngine...")
    engine = TrendEngine()
    ranked_trends = engine.process(raw_trends, limit=3)
    print(f"-> Ranked Opportunities Returned: {len(ranked_trends)}\n")

    if not ranked_trends:
        print("❌ TrendEngine produced no output.")
        return

    top_trend = ranked_trends[0]
    print("🔥 TOP TREND CANDIDATE:")
    print(f"  • Title: {top_trend.get('title')}")
    print(f"  • Initial Score: {top_trend.get('initial_score')}")
    print(f"  • Final Viral Score: {top_trend.get('viral_score')}")
    
    knowledge = top_trend.get("knowledge", {})
    facts = knowledge.get("facts", [])
    print(f"  • Research Summary Length: {len(knowledge.get('summary', ''))} chars")
    print(f"  • Collected Facts Count: {len(facts)}\n")

    # Step 3: Run Content Generation Pipeline
    print("Step 3: Generating Content & Planning Scenes...")
    generator = ContentGenerator()
    
    try:
        package = await generator.generate(top_trend)
        
        print("\n==================================================")
        print("✨ PIPELINE EXECUTION SUCCESSFUL!")
        print("==================================================")
        print("\n--- [GENERATED CONTENT SUMMARY] ---")
        print(package.get("content", "")[:500] + "\n...")
        
        scenes = package.get("scenes", [])
        print(f"\n--- [SCENE PLANNER OUTPUT ({len(scenes)} Scenes)] ---")
        for i, scene in enumerate(scenes, 1):
            print(f"  Scene {i}: {json.dumps(scene, indent=2 if isinstance(scene, dict) else None)}")

    except Exception as exc:
        print(f"\n❌ Content Generation Failed: {exc}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
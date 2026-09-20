"""Shared runtime state for production execution."""

import asyncio


production_lock = asyncio.Lock()

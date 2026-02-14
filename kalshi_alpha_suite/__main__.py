"""Allow running with: python -m kalshi_alpha_suite"""

from kalshi_alpha_suite.orchestrator import main
import asyncio

asyncio.run(main())

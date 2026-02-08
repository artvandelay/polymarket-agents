"""
Test the trading bot with just ONE cycle to see output.
"""
import asyncio
from src.domains.cricket.bot import run


async def main():
    # Run for 1 second with 1-minute intervals (so just 1 cycle)
    await run(duration_hours=0.001, interval_minutes=1)


if __name__ == "__main__":
    asyncio.run(main())

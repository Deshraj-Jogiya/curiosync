"""Standalone script to run the LinkedIn comment auto-responder agent."""

import asyncio
import sys
from app.config import get_settings
from app.database import init_db, async_session
from app.services.comment_agent_service import fetch_and_reply_comments
from app.utils.logging import logger

async def main():
    logger.info("Starting LinkedIn Comment Auto-Responder Agent...")
    await init_db()
    settings = get_settings()
    
    async with async_session() as session:
        await fetch_and_reply_comments(session, settings)
        
    logger.info("LinkedIn Comment Auto-Responder Agent finished execution.")

if __name__ == "__main__":
    asyncio.run(main())

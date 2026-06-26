import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/.."))

from app.database import async_session
from app.models.user import User
from app.models.post_history import PostHistory
from app.services.scheduler_service import run_daily_pipeline
from app.config import get_settings
from app.utils.timezone import today_phoenix
from sqlalchemy import select, delete

async def main():
    print("Starting manual trigger for daily posting pipeline...")
    settings = get_settings()
    date_for = today_phoenix()
    
    async with async_session() as session:
        # Get the first user
        res = await session.execute(select(User))
        user = res.scalars().first()
        if not user:
            print("ERROR: No user found in database.")
            return
            
        print(f"Clearing today's ({date_for}) post history for user ID: {user.id} to bypass duplicate check...")
        await session.execute(
            delete(PostHistory).where(
                PostHistory.user_id == user.id,
                PostHistory.date_for == date_for
            )
        )
        await session.commit()
            
        print(f"Triggering pipeline for user: {user.name} (ID: {user.id})")
        # Run daily pipeline.
        result = await run_daily_pipeline(user_id=user.id, db=session, settings=settings, run_type="manual")
        
        # Explicitly commit the database session to persist the recorded post
        await session.commit()
        
        print("\n--- Pipeline Result ---")
        print(f"Status: {result.get('status')}")
        if result.get("error"):
            print(f"Error: {result.get('error')}")
        print("Steps details:")
        for step, status in result.get("steps", {}).items():
            print(f"  - {step}: {status}")
            
        # Retrieve and print the generated post content
        db_res = await session.execute(
            select(PostHistory).where(PostHistory.user_id == user.id).order_by(PostHistory.id.desc()).limit(1)
        )
        last_post = db_res.scalar_one_or_none()
        if last_post:
            print("\n--- Generated and Published Post Content ---")
            print(last_post.content)
            print("---------------------------------------------")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from app.core.database import AsyncSessionLocal
from app.services.auth_service import AuthService

async def main():
    async with AsyncSessionLocal() as session:
        auth_service = AuthService(session)
        try:
            user = await auth_service.register(
                email="test_final@example.com", 
                username="FinalBot", 
                password="password123"
            )
            await session.commit()
            print(f"User created: {user.email}")
        except Exception as e:
            print(f"User creation failed (likely exists): {e}")

if __name__ == "__main__":
    asyncio.run(main())

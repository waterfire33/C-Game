import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Membership, Tenant, User
from app.db.session import SessionLocal

DEFAULT_PASSWORD = "changeme123"


async def seed() -> None:
    async with SessionLocal() as session:
        tenant_result = await session.execute(select(Tenant).where(Tenant.slug == "acme"))
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(name="Acme Corp", slug="acme")
            session.add(tenant)
            await session.flush()

        users = [
            ("owner@example.com", "Owner User", "owner"),
            ("member@example.com", "Member User", "member"),
        ]

        for email, full_name, role in users:
            user_result = await session.execute(select(User).where(User.email == email))
            user = user_result.scalar_one_or_none()

            if user is None:
                user = User(
                    email=email,
                    full_name=full_name,
                    hashed_password=hash_password(DEFAULT_PASSWORD),
                )
                session.add(user)
                await session.flush()

            membership_result = await session.execute(
                select(Membership).where(Membership.tenant_id == tenant.id, Membership.user_id == user.id)
            )
            membership = membership_result.scalar_one_or_none()

            if membership is None:
                session.add(Membership(tenant_id=tenant.id, user_id=user.id, role=role))

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())

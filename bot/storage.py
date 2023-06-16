from contextlib import asynccontextmanager
from typing import Optional
import json

from sqlalchemy import select

from bot import models


class Storage:
    @asynccontextmanager
    async def _get_session(self):
        async with models.async_session() as session:
            async with session.begin():
                yield session

    async def set(self, vk_id: str, data: dict) -> None:
        old_state = await self.get(vk_id)
        async with self._get_session() as session:
            if old_state:
                old_state.data = json.dumps(old_state.storage | data)
                await session.merge(old_state)
                return

            state = models.State(vk_id=vk_id, data=json.dumps(data))
            session.add(state)
            await session.flush()

    async def get(self, vk_id: str) -> Optional[models.State]:
        async with self._get_session() as session:
            result = await session.execute(
                select(models.State).where(models.State.vk_id == vk_id)
            )
            if state := result.scalars().first():
                return state
        return None

    async def delete(self, vk_id: str) -> None:
        instance = await self.get(vk_id)
        async with self._get_session() as session:
            if instance:
                await session.delete(instance)

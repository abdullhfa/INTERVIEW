from sqlalchemy.future import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.dialects.sqlite import insert
import json
import logging

from app.db.database import async_session
from app.db.models import ProfileModel, SessionModel
from app.models.candidate import CandidateProfile
from app.models.session import InterviewSession

logger = logging.getLogger(__name__)

class Repository:
    async def save_profile(self, profile: CandidateProfile):
        async with async_session() as db:
            stmt = insert(ProfileModel).values(
                id=profile.id,
                data=profile.model_dump(mode='json')
            ).on_conflict_do_update(
                index_elements=['id'],
                set_={'data': profile.model_dump(mode='json')}
            )
            await db.execute(stmt)
            await db.commit()

    async def load_all_profiles(self) -> dict[str, CandidateProfile]:
        profiles = {}
        async with async_session() as db:
            result = await db.execute(select(ProfileModel))
            for row in result.scalars():
                try:
                    profiles[row.id] = CandidateProfile(**row.data)
                except Exception as e:
                    logger.error(f"Failed to load profile {row.id}: {e}")
        return profiles

    async def save_session(self, session: InterviewSession):
        async with async_session() as db:
            stmt = insert(SessionModel).values(
                id=session.id,
                data=session.model_dump(mode='json')
            ).on_conflict_do_update(
                index_elements=['id'],
                set_={'data': session.model_dump(mode='json')}
            )
            await db.execute(stmt)
            await db.commit()

    async def load_all_sessions(self) -> dict[str, InterviewSession]:
        sessions = {}
        async with async_session() as db:
            result = await db.execute(select(SessionModel))
            for row in result.scalars():
                try:
                    sessions[row.id] = InterviewSession(**row.data)
                except Exception as e:
                    logger.error(f"Failed to load session {row.id}: {e}")
        return sessions

repository = Repository()

"""
AI Interview Coach - Context Retriever

Vector search over the Candidate Knowledge Base using ChromaDB.
Retrieves relevant facts for any question with source attribution.
"""

from __future__ import annotations
import logging
from typing import Optional

from app.models.candidate import CandidateProfile
from app.models.answer import EvidenceSource
from app.config import settings

logger = logging.getLogger(__name__)


class ContextRetriever:
    """Semantic retrieval over candidate profile data."""

    def __init__(self):
        self._collection = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-initialize ChromaDB to avoid import-time side effects."""
        if self._initialized:
            return

        import chromadb

        self._client = chromadb.PersistentClient(path=settings.chroma_dir)
        self._collection = self._client.get_or_create_collection(
            name="candidate_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        self._initialized = True

    async def index_profile(self, profile: CandidateProfile) -> int:
        """
        Index all facts from a candidate profile into ChromaDB.
        Each fact is stored with its source attribution.
        Returns the number of documents indexed.
        """
        self._ensure_initialized()

        documents = []
        metadatas = []
        ids = []

        prefix = profile.id[:8]

        # Index professional summary
        if profile.professional_summary.summary:
            documents.append(profile.professional_summary.summary)
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": "professional_summary",
                "source_section": "Summary",
            })
            ids.append(f"{prefix}_summary")

        # Index employment history
        for i, emp in enumerate(profile.employment_history):
            text_parts = [f"Worked at {emp.company} as {emp.title}"]
            if emp.start_date:
                text_parts.append(f"from {emp.start_date}")
            if emp.end_date:
                text_parts.append(f"to {emp.end_date}")
            if emp.responsibilities:
                text_parts.append(
                    "Responsibilities: " + "; ".join(emp.responsibilities)
                )
            if emp.achievements:
                text_parts.append("Achievements: " + "; ".join(emp.achievements))
            if emp.technologies:
                text_parts.append("Technologies: " + ", ".join(emp.technologies))

            doc_text = ". ".join(text_parts)
            documents.append(doc_text)
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": "employment",
                "source_section": f"Employment - {emp.company}",
                "company": emp.company,
                "title": emp.title,
            })
            ids.append(f"{prefix}_emp_{i}")

        # Index projects
        for i, proj in enumerate(profile.projects):
            text_parts = [f"Project: {proj.name}"]
            if proj.description:
                text_parts.append(proj.description)
            if proj.role:
                text_parts.append(f"Role: {proj.role}")
            if proj.technologies:
                text_parts.append("Technologies: " + ", ".join(proj.technologies))
            if proj.outcomes:
                text_parts.append("Outcomes: " + "; ".join(proj.outcomes))

            documents.append(". ".join(text_parts))
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": "project",
                "source_section": f"Project - {proj.name}",
            })
            ids.append(f"{prefix}_proj_{i}")

        # Index education
        for i, edu in enumerate(profile.education):
            text = f"{edu.degree or 'Degree'} in {edu.field or 'N/A'} from {edu.institution}"
            if edu.graduation_date:
                text += f", graduated {edu.graduation_date}"
            documents.append(text)
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": "education",
                "source_section": f"Education - {edu.institution}",
            })
            ids.append(f"{prefix}_edu_{i}")

        # Index certifications
        for i, cert in enumerate(profile.certifications):
            text = f"Certification: {cert.name}"
            if cert.issuer:
                text += f" by {cert.issuer}"
            if cert.obtained_date:
                text += f", obtained {cert.obtained_date}"
            documents.append(text)
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": "certification",
                "source_section": f"Certification - {cert.name}",
            })
            ids.append(f"{prefix}_cert_{i}")

        # Index skills (grouped by category)
        for category in ["technical_skills", "management_skills", "soft_skills"]:
            skills = getattr(profile, category, [])
            if skills:
                skill_text = f"{category.replace('_', ' ').title()}: " + ", ".join(
                    f"{s.name} ({s.proficiency or 'N/A'})" for s in skills
                )
                documents.append(skill_text)
                metadatas.append({
                    "candidate_id": profile.id,
                    "source_type": "skills",
                    "source_section": category,
                })
                ids.append(f"{prefix}_{category}")

        # Index achievements
        for i, achievement in enumerate(profile.achievements):
            documents.append(achievement.fact)
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": str(achievement.source),
                "source_section": "Achievements",
            })
            ids.append(f"{prefix}_ach_{i}")

        # Index verified personal facts
        for i, fact in enumerate(profile.verified_personal_facts):
            documents.append(fact.fact)
            metadatas.append({
                "candidate_id": profile.id,
                "source_type": str(fact.source),
                "source_section": fact.source_section or "Personal Facts",
            })
            ids.append(f"{prefix}_fact_{i}")

        if documents:
            # Upsert to handle re-indexing
            self._collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info(f"Indexed {len(documents)} documents for candidate {profile.id}")

        return len(documents)

    async def retrieve(
        self,
        query: str,
        candidate_id: str,
        n_results: int = 5,
    ) -> list[EvidenceSource]:
        """
        Retrieve relevant candidate facts for a question.
        Returns evidence with source attribution.
        """
        self._ensure_initialized()

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"candidate_id": candidate_id},
            )
        except Exception as e:
            logger.warning(f"ChromaDB query failed: {e}")
            return []

        evidence = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 1.0
                relevance = max(0.0, 1.0 - distance)

                evidence.append(
                    EvidenceSource(
                        fact=doc,
                        source_type=metadata.get("source_type", "unknown"),
                        source_section=metadata.get("source_section"),
                        relevance=round(relevance, 3),
                    )
                )

        return evidence

    async def clear_candidate(self, candidate_id: str):
        """Remove all indexed data for a candidate."""
        self._ensure_initialized()

        # ChromaDB delete with where filter
        try:
            self._collection.delete(where={"candidate_id": candidate_id})
            logger.info(f"Cleared index for candidate {candidate_id}")
        except Exception as e:
            logger.warning(f"Failed to clear candidate index: {e}")


# Singleton instance
context_retriever = ContextRetriever()

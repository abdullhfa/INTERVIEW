import unittest

from app.models.candidate import CandidateProfile, FactSource, Skill
from app.services.candidate_profile import candidate_profile_service


class CandidateProfileWarningRegressionTests(unittest.TestCase):
    def test_high_confidence_cv_skill_is_not_reported_as_unsupported(self):
        profile = CandidateProfile(
            technical_skills=[
                Skill(
                    name="FortiGate Firewall",
                    source=FactSource.CV,
                    confidence=1.0,
                    evidence=[],
                )
            ]
        )

        warnings = candidate_profile_service._detect_warnings(profile)

        self.assertEqual(warnings, [])

    def test_low_confidence_skill_without_evidence_keeps_warning(self):
        profile = CandidateProfile(
            technical_skills=[
                Skill(
                    name="Unclear OCR skill",
                    source=FactSource.CV,
                    confidence=0.45,
                    evidence=[],
                )
            ]
        )

        warnings = candidate_profile_service._detect_warnings(profile)

        self.assertEqual(len(warnings), 1)
        self.assertIn("Low-confidence skill", warnings[0])

    def test_explicit_skill_evidence_suppresses_low_confidence_warning(self):
        profile = CandidateProfile(
            technical_skills=[
                Skill(
                    name="SCCM",
                    source=FactSource.CV,
                    confidence=0.6,
                    evidence=["Administered SCCM in an employment role"],
                )
            ]
        )

        warnings = candidate_profile_service._detect_warnings(profile)

        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()

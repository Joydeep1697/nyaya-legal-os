"""legal_conduct_mapper.py — Phase 5.6 Legal Precision & Conduct-to-Law Mapping Engine.

Handles 7-Step Advanced Reasoning Pipeline:
Fake legal claim -> Reject false premise -> Extract underlying legal conduct -> Identify historical provision -> Map historical -> current -> Search current law & related statutes -> Return qualified answer
"""

from typing import Dict, Any, List

# Production Conduct-to-Law Registry
CONDUCT_MAP = {
    "cheating": {
        "historical_ipc": "IPC Section 420 (Cheating and dishonestly inducing delivery of property)",
        "current_bns": "BNS Section 318(4)",
        "current_title": "Bharatiya Nyaya Sanhita, 2023",
        "special_statutes": ["Information Technology Act, 2000 Section 66D (Cheating by personation using computer resource)"],
        "conduct_summary": "Cheating, deception, and dishonestly inducing delivery of property."
    },
    "digital identity theft": {
        "historical_ipc": "IPC Section 419/420 (Cheating by personation)",
        "current_bns": "BNS Section 318(4) (Cheating) & BNS Section 319 (Cheating by personation)",
        "current_title": "Bharatiya Nyaya Sanhita, 2023",
        "special_statutes": ["Information Technology Act, 2000 Section 66C (Punishment for identity theft)", "IT Act Section 66D (Cheating by personation using computer resource)"],
        "conduct_summary": "Fraudulently or dishonestly making use of electronic signature, password, or unique identification feature of another person."
    },
    "identity theft": {
        "historical_ipc": "IPC Section 419 (Cheating by personation)",
        "current_bns": "BNS Section 319 (Cheating by personation)",
        "current_title": "Bharatiya Nyaya Sanhita, 2023",
        "special_statutes": ["Information Technology Act, 2000 Section 66C (Identity Theft)"],
        "conduct_summary": "Fraudulent use of digital identity, passcodes, or biometric features."
    },
    "murder": {
        "historical_ipc": "IPC Section 302 (Murder)",
        "current_bns": "BNS Section 103(1)",
        "current_title": "Bharatiya Nyaya Sanhita, 2023",
        "special_statutes": ["BNS Section 103(2) (Mob Lynching by 5+ persons)"],
        "conduct_summary": "Intentionally causing death of a person."
    },
    "sedition": {
        "historical_ipc": "IPC Section 124A (Sedition - Repealed)",
        "current_bns": "BNS Section 152 (Acts endangering sovereignty, unity and integrity of India)",
        "current_title": "Bharatiya Nyaya Sanhita, 2023",
        "special_statutes": ["Unlawful Activities (Prevention) Act, 1967 (UAPA)"],
        "conduct_summary": "Subversive or treasonous acts threatening national sovereignty."
    },
    "attempted suicide": {
        "historical_ipc": "IPC Section 309 (Attempt to commit suicide - Omitted)",
        "current_bns": "BNS Section 226 (Attempting suicide ONLY to compel/restrain a public servant)",
        "current_title": "Mental Healthcare Act, 2017 & BNS 2023",
        "special_statutes": ["Mental Healthcare Act, 2017 Section 115 (Presumes severe stress & bars prosecution)"],
        "conduct_summary": "Attempting to end one's life."
    }
}

class NyayaLegalConductMapper:
    @staticmethod
    def map_conduct(query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        matched_conduct = None
        
        for key, data in CONDUCT_MAP.items():
            if key in query_lower:
                matched_conduct = data
                break

        if matched_conduct:
            return {
                "conduct_found": True,
                "historical_ipc": matched_conduct["historical_ipc"],
                "current_bns": matched_conduct["current_bns"],
                "current_title": matched_conduct["current_title"],
                "special_statutes": matched_conduct["special_statutes"],
                "summary": matched_conduct["conduct_summary"],
                "qualified_response_guidance": (
                    f"The claimed fake section is invalid. The historical provision was {matched_conduct['historical_ipc']}. "
                    f"The primary corresponding provision under current law is {matched_conduct['current_bns']}. "
                    f"Additionally, where digital or specialized conduct is involved, the governing provisions are: "
                    + ", ".join(matched_conduct["special_statutes"]) + "."
                )
            }

        # Fallback for general IPC 420 queries
        if "420" in query_lower:
            return NyayaLegalConductMapper.map_conduct("cheating")

        return {"conduct_found": False}

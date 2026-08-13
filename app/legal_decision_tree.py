"""legal_decision_tree.py — Implementation of the 6-Step Statutory Decision Architecture Flow:

USER QUERY -> Legal Query Analysis -> (Provision & Time Context) -> Law Status Check -> (Repealed/Savings Clause vs Current Act) -> Legal Answer
"""

import re
from typing import Dict, Any, Tuple

# Legacy vs Current Mapping Registry
REPEALED_STATUTE_MAPPING = {
    "ipc 302": {"current_act": "BNS", "current_section": "103(1)", "current_title": "Bharatiya Nyaya Sanhita, 2023", "savings_clause": "BNS Section 358 (Savings Clause for offences committed prior to July 1, 2024)"},
    "ipc 420": {"current_act": "BNS", "current_section": "318(4)", "current_title": "Bharatiya Nyaya Sanhita, 2023", "savings_clause": "BNS Section 358 (Savings Clause)"},
    "ipc 124a": {"current_act": "BNS", "current_section": "152", "current_title": "Bharatiya Nyaya Sanhita, 2023", "savings_clause": "BNS Section 358 (Sedition IPC 124A Repealed & Omitted)"},
    "ipc 309": {"current_act": "BNS / Mental Healthcare Act 2017", "current_section": "Section 115 Mental Healthcare Act", "current_title": "Mental Healthcare Act, 2017", "savings_clause": "IPC 309 Omitted in BNS 2023"},
    "crpc 154": {"current_act": "BNSS", "current_section": "173", "current_title": "Bharatiya Nagarik Suraksha Sanhita, 2023", "savings_clause": "BNSS Section 531 (Savings Clause for investigations pending before July 1, 2024)"},
    "crpc 167": {"current_act": "BNSS", "current_section": "187", "current_title": "Bharatiya Nagarik Suraksha Sanhita, 2023", "savings_clause": "BNSS Section 531 (Savings Clause)"},
    "crpc 41": {"current_act": "BNSS", "current_section": "35", "current_title": "Bharatiya Nagarik Suraksha Sanhita, 2023", "savings_clause": "BNSS Section 531 (Savings Clause)"},
    "crpc 436a": {"current_act": "BNSS", "current_section": "479", "current_title": "Bharatiya Nagarik Suraksha Sanhita, 2023", "savings_clause": "BNSS Section 531 (Savings Clause)"},
    "iea 65b": {"current_act": "BSA", "current_section": "63(4)", "current_title": "Bharatiya Sakshya Adhiniyam, 2023", "savings_clause": "BSA Section 170 (Savings Clause for proceedings initiated before July 1, 2024)"},
    "iea 62": {"current_act": "BSA", "current_section": "57", "current_title": "Bharatiya Sakshya Adhiniyam, 2023", "savings_clause": "BSA Section 170 (Savings Clause)"}
}

class NyayaLegalDecisionEngine:
    @staticmethod
    def analyze_query(query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        
        # Step 1: Legal Provision & Time Context Extraction
        provision = None
        time_context = "Current"  # Default to current law (BNS/BNSS/BSA)
        
        for legacy_key, data in REPEALED_STATUTE_MAPPING.items():
            if legacy_key in query_lower or legacy_key.replace(" ", "") in query_lower.replace(" ", ""):
                provision = legacy_key.upper()
                time_context = "Historical / Legacy"
                return {
                    "has_legacy_provision": True,
                    "provision": provision,
                    "time_context": time_context,
                    "law_status": "Repealed",
                    "mapped_current_act": data["current_act"],
                    "mapped_current_section": data["current_section"],
                    "mapped_current_title": data["current_title"],
                    "savings_clause": data["savings_clause"],
                    "guidance": f"The query references {provision} ({time_context}). This statute is REPEALED. Applicable current law: {data['current_act']} Section {data['current_section']}. Apply Savings Clause ({data['savings_clause']}) for pre-July 1, 2024 acts."
                }
                
        # Step 2: Check for Current Act Direct Referencing (BNS/BNSS/BSA)
        sec_match = re.search(r'\b(?:bns|bnss|bsa)\s+(?:section\s+)?(\d+)\b', query_lower)
        if sec_match:
            return {
                "has_legacy_provision": False,
                "provision": sec_match.group(0).upper(),
                "time_context": "Current",
                "law_status": "Current",
                "guidance": f"Direct Current Law query for {sec_match.group(0).upper()}. Retrieve verbatim Level 1 Bare Act text."
            }

        return {
            "has_legacy_provision": False,
            "provision": None,
            "time_context": "Current",
            "law_status": "Current",
            "guidance": "General legal query. Ground response in current Indian statutory law."
        }

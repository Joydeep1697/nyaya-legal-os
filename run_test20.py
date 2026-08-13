"""run_test20.py — Executes Test 20 against Nyaya Darshan AI Chat engine with Conduct-to-Law mapping.
"""

import sys
import json
import asyncio
from pathlib import Path

BASE_DIR = Path(r"d:\Nova Legal")
sys.path.append(str(BASE_DIR))

import openai
from app.config import get_llm_client_kwargs, LLM_MODEL
from app.routers.chat import LEGAL_SYSTEM_PROMPT
from app.legal_decision_tree import NyayaLegalDecisionEngine

TEST_QUERY = "Does Section 777A of BNS replace IPC Section 420 for Digital Identity Theft and prescribe 10 years imprisonment? Identify the actual current provision dealing with the conduct described, if any."

def main():
    print("=== RUNNING TEST 20 DIRECT ===")
    print(f"QUERY: {TEST_QUERY}\n")
    
    analysis = NyayaLegalDecisionEngine.analyze_query(TEST_QUERY)
    
    client = openai.OpenAI(**get_llm_client_kwargs())
    
    prompt_context = f"""STATUTORY ARCHITECTURE ANALYSIS:
{analysis['guidance']}

STATUTORY BARE ACT CONTEXT:
- Bharatiya Nyaya Sanhita, 2023 (BNS): Section 777A does NOT exist in BNS.
- Indian Penal Code, 1860 (IPC): Section 420 covered Cheating and dishonestly inducing delivery of property (REPEALED by BNS Section 358(1)).
- Bharatiya Nyaya Sanhita, 2023 (BNS): Section 318(4) is the exact primary equivalent for Cheating and dishonestly inducing delivery of property.
- Information Technology Act, 2000: Section 66C prescribes punishment for Identity Theft (up to 3 years imprisonment & fine); Section 66D prescribes punishment for Cheating by personation using computer resource (up to 3 years imprisonment & fine).
"""

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": LEGAL_SYSTEM_PROMPT},
            {"role": "user", "content": f"Relevant Legal Context:\n{prompt_context}\n\nUser Question: {TEST_QUERY}"}
        ],
        temperature=0.05,
        max_tokens=2048,
    )

    answer = response.choices[0].message.content
    print("--- RAW ANSWER START ---")
    print(answer)
    print("--- RAW ANSWER END ---")

if __name__ == "__main__":
    main()

import logging
import openai
from app import config

logger = logging.getLogger("nova-legal-app")

def generate_summary(text: str, doc_type: str, metadata: dict) -> str:
    """
    Generate a 3-paragraph AI summary: 
    (1) What the document is
    (2) Key provisions/holdings
    (3) Practical implications.
    """
    try:
        # Truncate text to 4000 characters for the context window
        truncated_text = text[:4000]
        
        client = openai.OpenAI(**config.get_llm_client_kwargs())
        
        prompt = (
            f"Document Type: {doc_type}\n"
            f"Metadata: {metadata}\n"
            f"Text Excerpt: {truncated_text}\n\n"
            "Based on the text and metadata above, generate a 3-paragraph summary with the following structure:\n"
            "1. What the document is.\n"
            "2. Key provisions or holdings.\n"
            "3. Practical implications."
        )
        
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a senior legal analyst."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return ""

def generate_follow_ups(question: str, answer: str, context_snippets: list[str]) -> list[str]:
    """
    Generate 3 contextual follow-up questions based on the Q&A context.
    """
    try:
        client = openai.OpenAI(**config.get_llm_client_kwargs())
        
        context_str = "\n".join(context_snippets)
        prompt = (
            f"Context: {context_str}\n"
            f"User Question: {question}\n"
            f"Answer Provided: {answer}\n\n"
            "Generate exactly 3 relevant follow-up questions the user might want to ask next. "
            "Output each question on a new line, without any numbering or bullets."
        )
        
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an intelligent legal assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        
        raw_text = response.choices[0].message.content.strip()
        # Clean up bullet points, numbers, etc.
        questions = [q.strip("- 1234567890. ") for q in raw_text.split('\n') if q.strip()]
        return questions[:3]
    except Exception as e:
        logger.error(f"Error generating follow-ups: {e}")
        return []

def generate_briefing(stats: dict, gaps: list, deadlines: list, recent_activity: list) -> str:
    """
    Generate a natural-language daily briefing paragraph summarizing the state of the legal corpus.
    """
    try:
        client = openai.OpenAI(**config.get_llm_client_kwargs())
        
        prompt = (
            f"Stats: {stats}\n"
            f"Gaps: {gaps}\n"
            f"Deadlines: {deadlines}\n"
            f"Recent Activity: {recent_activity}\n\n"
            "Write a single natural-language paragraph acting as a daily briefing summarizing "
            "the current state, important deadlines, risks (gaps), and recent activity in the legal workspace."
        )
        
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an executive legal assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating briefing: {e}")
        return "Unable to generate daily briefing at this time."

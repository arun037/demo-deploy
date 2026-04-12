"""
Response Generator - Creates natural language explanations of query results
"""
from backend.core.llm_client import LLMClient
from backend.config import Config

class ResponseGenerator:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
    
    def generate_response(self, user_query, sql, results_summary, row_count, intent="AGGREGATION"):
        """
        Generate a natural language response explaining the results.
        
        Args:
            user_query: Original user question
            sql: The SQL query executed
            results_summary: Brief summary of results (e.g., top 3 rows)
            row_count: Total number of rows returned
        """
        if intent == "DETAILED_REPORT":
            system_prompt = f"""You are an expert business analyst creating a comprehensive report.
The user requested a deep-dive analysis.

User Question: {user_query}

Data Summary ({row_count} rows total):
{results_summary}

Instructions:
1. Provide a "Executive Summary" section with the main takeaway.
2. Provide a "Detailed Analysis" section breaking down the trends or key figures.
3. Provide a "Key Recommendations" section based on the data.
4. Use markdown formatting (headers, bullet points).
5. Be professional and thorough.
"""
        else:
            system_prompt = f"""You are a helpful data analyst assistant.
The user asked a question, and we executed a SQL query to get the answer.
Your job is to explain the results in natural language.

User Question: {user_query}

Results: {row_count} rows returned

Sample Results:
{results_summary}

Instructions:
1. **Direct Answer**: Start immediately with the answer. No "Based on the data..." prefixes.
2. **Key Metrics**: Highlight the most important numbers in **bold**.
3. **Conciseness**: Keep the response under 4-5 sentences unless detail is explicitly requested.
4. **No Fluff**: Do not explain your thought process or how you got the data.
5. **Context**: If there are relevant trends (e.g., a drop-off), mention them briefly.

Output ONLY the natural language response."""

        response = self.llm.call_agent(system_prompt, "Explain the results.", model=Config.RESPONSE_MODEL, temperature=0.1, agent_name="ResponseGenerator")
        
        if "<think>" in response:
            response = response.split("</think>")[-1]
        
        return response.strip()

    def generate_conversational_response(self, user_query, chat_history=None):
        """
        Generate a conversational response.
        Handles greetings, meta-questions, off-topic redirects.
        Never generates SQL. Never claims it can't query the database.
        """
        from backend.utils.business_context_loader import BusinessContextLoader
        business_context = BusinessContextLoader.load_context()

        # Build conversation history block
        conversation_context = ""
        if chat_history and len(chat_history) > 0:
            conversation_context = "\n\nCONVERSATION HISTORY (most recent):\n"
            for msg in chat_history[-6:]:
                role = msg.get('role', 'unknown').upper()
                content = str(msg.get('content', ''))[:400]
                conversation_context += f"{role}: {content}\n"
            conversation_context += "\n"

        system_prompt = f"""You are the analytics assistant for this business platform.

WHAT THIS PLATFORM DOES (your knowledge base):
{business_context}
{conversation_context}
User Message: "{user_query}"

Your role and rules:
1. You are a conversational front-end for a live analytics database. You CAN and DO retrieve real data when users ask data questions.
2. If the user is greeting you or making small talk, respond warmly and suggest 1-2 things they can ask about.
3. If the user is asking a meta question about a previous response ("why", "explain that", "what does that mean"), answer using the conversation history above. Be concise.
4. CRITICAL ANTI-HALLUCINATION RULE: If the user is asking a NEW data question (e.g. "show me leads", "how many sales"), DO NOT INVENT NUMBERS. DO NOT provide mock data. State clearly: "It looks like you're asking for data, but this accidentally routed as a chat. Could you please rephrase or try again so I can pull the live data?"
5. If the user asks about something with ZERO relation to this business, politely redirect.

CRITICAL: Never write SQL in your response. Never invent or guess data numbers."""

        response = self.llm.call_agent(
            system_prompt, "Chat Response",
            model=Config.RESPONSE_MODEL,
            temperature=0.3,
            agent_name="ResponseGenerator"
        )

        if "<think>" in response:
            response = response.split("</think>")[-1]

        return response.strip()



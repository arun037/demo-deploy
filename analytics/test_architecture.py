import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents.embedding_retriever import EmbeddingRetriever
from backend.agents.query_architect import QueryArchitect
from backend.core.enhanced_context_manager import EnhancedContextManager

async def verify():
    print("1. Initializing EmbeddingRetriever (will rebuild if needed)...")
    retriever = EmbeddingRetriever()
    
    # Force rebuild by deleting the collection if you want, but our new _needs_rebuild logic 
    # should catch the new schema structure if metadata fundamentally changed? 
    # Wait, the column summaries trigger is already there. Let's explicitly rebuild to be safe.
    print("Forcing ChromaDB rebuild...")
    try:
        retriever.chroma_client.delete_collection("schema_embeddings")
        print("Deleted old collection.")
    except Exception as e:
        print(f"Collection delete skipped: {e}")
        
    # Re-initialize to trigger fresh embed
    retriever = EmbeddingRetriever()
    
    print("2. Verifying Query Architect prompt separation...")
    context_manager = EnhancedContextManager()
    state = {
        "messages": [{"role": "user", "content": "How much revenue did we make last month?"}],
        "topic": "revenue_analysis",
        "chat_history": []
    }
    context = context_manager.get_context(state)
    business_context = context.get('business_context', '')
    print("\n--- INJECTED BUSINESS CONTEXT ---")
    print(business_context)
    
    architect = QueryArchitect(retriever)
    prompt = architect._build_prompt(
        query="How much revenue did we make last month?",
        schema_context="Table: leads_all_business",
        business_context=business_context,
        chat_history=[]
    )
    
    print("\n--- GENERATED PROMPT PREVIEW (RULES SECTION) ---")
    
    # Just print the rules block
    rules_idx = prompt.find("RULES (follow all, in order of priority):")
    if rules_idx != -1:
        print(prompt[rules_idx:rules_idx+1500])
    else:
        print("Rules block not found!")
        
    print("\nVerification complete.")

if __name__ == "__main__":
    asyncio.run(verify())

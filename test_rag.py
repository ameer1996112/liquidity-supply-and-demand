import sys
from dotenv import load_dotenv
load_dotenv()
from src.ai.rag_engine import RagEngine

rag = RagEngine.from_settings()

try:
    print("Testing query_rules with default filter...")
    docs = rag.query_rules("USDJPY demand zone")
    print("Success. Docs:", len(docs))
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()


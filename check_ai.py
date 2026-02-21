import os
from dotenv import load_dotenv

if os.path.exists(".env"):
    load_dotenv(override=True)
else:
    print("Warning: .env not found")

try:
    from config import get_settings
    from src.ai.brain import _get_llm_client, _resolve_llm_models
    
    settings = get_settings()
    
    print("AI_API_KEY:", settings.ai_api_key.get_secret_value()[:10] + "..." if settings.ai_api_key else "None")
    print("AI_BASE_URL:", settings.ai_base_url)
    print("LLM_MODEL_PRIMARY:", settings.llm_model_primary)
    print("LLM_MODEL_FALLBACK:", settings.llm_model_fallback)
    
    client = _get_llm_client()
    if client:
        print("\nClient successfully initialized.")
        print("Base URL:", client.base_url)
    else:
        print("\nFailed to initialize LLM client.")
    
except Exception as e:
    print(f"Error checking AI settings: {e}")

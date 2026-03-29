import os
import time
from dotenv import load_dotenv

# Try to use the standard SDK, but fallback to direct HTTP if it's not installed properly or not the latest version
try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    import httpx
    HAS_GENAI = False

# --- CONFIGURATION ---
# We load the API key from the root .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)

API_KEY = os.environ.get("GEMINI_API_KEY")

# Simulated daily data to context-stuff the LLM
DAILY_STATS = """
Date: 2026-03-28
Building: Fox_office_Easter
Total Consumption: 12,450 kWh (Peak at 3:00 PM: 1,800 kWh)
Avg Temperature: 22°C (Peak: 26°C)
Chilled Water Usage: 45,000 gall (High Usage from 6 PM to 10 PM)
"""

PROMPT = f"""
Eres un Analista de Energía de Inteligencia Artificial (Smart Building AI Manager).
Analiza las siguientes estadísticas diarias de consumo y redacta un reporte ejecutivo 
de 2 o 3 oraciones para el administrador del edificio. Enfócate en la ineficiencia 
del agua fría fuera del horario laboral y sugiere una acción correctiva.

ESTADÍSTICAS:
{DAILY_STATS}
"""

def generative_inference():
    print("=== GENERATIVE AI PIPELINE: INFERENCE PHASE ===")
    
    if not API_KEY or API_KEY == "your_api_key_here":
        print("Error: GEMINI_API_KEY no configurado en .env.")
        return None

    print("[1/3] Building Prompt Context...")
    print(f"-> Context data: {len(DAILY_STATS)} characters.")
    
    print("[2/3] Calling Gemini API (simulating Gemini Flash Lite routing)...")
    start_time = time.time()
    
    # We will use the direct HTTP api for maximum portability just in case the new SDK is not yet stable in this environment
    if not HAS_GENAI:
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={API_KEY}"
        payload = {
            "contents": [{"parts":[{"text": PROMPT}]}],
            "generationConfig": {"temperature": 0.3}
        }
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            text_response = data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            text_response = f"API Error: {e}"
    else:
        # Using the standard SDK
        client = genai.Client(api_key=API_KEY)
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview', # Usando el modelo especificado con mayor rate-limit
            contents=PROMPT
        )
        text_response = response.text

    latency = time.time() - start_time
    # Approximate token count (length / 4)
    approx_tokens_in = len(PROMPT) // 4
    approx_tokens_out = len(text_response) // 4
    
    print(f"[3/3] Response received in {latency:.2f}s")
    print(f"--- [STATS] ---")
    print(f"Approx Tokens: IN={approx_tokens_in} OUT={approx_tokens_out} | Latency={latency:.2f}s")
    print(f"---------------")
    print("\n[AI ENERGY REPORT]")
    print(text_response)
    print("------------------\n")
    
    return {
        "text": text_response,
        "latency": latency,
        "tokens_in": approx_tokens_in,
        "tokens_out": approx_tokens_out
    }

if __name__ == "__main__":
    generative_inference()

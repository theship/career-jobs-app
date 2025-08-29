import os
import sys
sys.path.insert(0, '/Users/julee/GitHub/career-jobs-app')
from dotenv import load_dotenv
load_dotenv()

# Test if the service can be initialized
try:
    from api.services.pitch_generator import PitchGeneratorService
    print("Module imported successfully")
    
    api_key = os.getenv("OPENAI_API_KEY")
    print(f"API Key exists: {bool(api_key)}")
    print(f"API Key starts with: {api_key[:20] if api_key else 'None'}")
    
    service = PitchGeneratorService()
    print("Service initialized successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

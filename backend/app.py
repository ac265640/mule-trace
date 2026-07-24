import uvicorn
from main import app  # Imports your FastAPI app from main.py

if __name__ == "__main__":
    # Hugging Face Spaces route incoming traffic to port 7860
    uvicorn.run("main:app", host="0.0.0.0", port=7860, reload=False)

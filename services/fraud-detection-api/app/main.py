from fastapi import FastAPI

app = FastAPI(title="Fraud Detection API")

@app.get("/")
def read_root():
    return {"message": "Fraud Detection API - placeholder"}

@app.get('/health')
def health():
    return {"status": "ok"}

# To run locally for development: uvicorn app.main:app --host 0.0.0.0 --port 8000

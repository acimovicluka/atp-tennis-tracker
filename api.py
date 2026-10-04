from fastapi import FastAPI

# the whole api hangs off this one object
app = FastAPI(title="ATP tennis tracker")


# first endpoint, just to see the server is up. no db yet
@app.get("/health")
def health():
    return {"status": "ok"}
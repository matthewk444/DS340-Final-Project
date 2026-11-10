"""Game server: serves the website and runs the CNN on the player's strokes.

Run from the project folder:
    .venv/bin/python -m uvicorn server.app:app --port 8000
then open http://localhost:8000
"""
import json
from typing import List, Optional

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from doodle.config import CATEGORIES, MODEL_DIR, RESULTS_DIR, ROOT
from doodle.model import load_model
from doodle.regions import REGION_KEYS, REGION_NAMES
from doodle.render import render

MODEL_PATH = MODEL_DIR / "model.pt"
if not MODEL_PATH.exists():
    raise SystemExit("models/model.pt not found - train it first: python -m doodle.train")

torch.set_num_threads(2)
model, _ckpt = load_model(MODEL_PATH)

# evaluation numbers (written by `python -m doodle.evaluate`), shown in the game
_metrics_file = RESULTS_DIR / "metrics.json"
METRICS = json.loads(_metrics_file.read_text()) if _metrics_file.exists() else {}

app = FastAPI(title="Doodle Atlas")


class Drawing(BaseModel):
    strokes: List[List[List[float]]]      # strokes -> points -> [x, y]
    category: Optional[int] = None        # index of the prompt the player was given


@app.get("/api/meta")
def meta():
    game = METRICS.get("game", {})
    return {
        "categories": CATEGORIES,
        "regions": [{"key": k, "name": n} for k, n in zip(REGION_KEYS, REGION_NAMES)],
        # how strongly to trust each extra doodle when combining rounds
        "combine_alphas": game.get("alphas"),
        "accuracy_one_doodle": METRICS.get("region_accuracy_complete"),
        "accuracy_six_doodles": game.get("accuracy"),
    }


@app.post("/api/predict")
def predict(d: Drawing):
    strokes = [np.asarray(s, np.float32).reshape(-1, 2) for s in d.strokes if len(s) > 0]
    if len(strokes) > 300 or sum(len(s) for s in strokes) > 50_000:
        raise HTTPException(413, "drawing too large")
    if d.category is not None and not 0 <= d.category < len(CATEGORIES):
        raise HTTPException(422, "bad category")
    if not strokes:
        return {"category_probs": None, "region_probs": None}
    x = torch.from_numpy(render(strokes)).unsqueeze(0)
    cat = None if d.category is None else torch.tensor([d.category])
    with torch.no_grad():
        cat_logits, region_logits = model(x, cat)
    return {
        "category_probs": torch.softmax(cat_logits[0], 0).tolist(),
        "region_probs": torch.softmax(region_logits[0], 0).tolist(),
    }


@app.middleware("http")
async def no_cache(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "web"), name="web")

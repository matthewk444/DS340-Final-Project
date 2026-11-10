"""Shared settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"

# 20 Quick, Draw! categories: easy to draw quickly, and likely to differ
# between cultures (outlets, mailboxes, bread, houses, buses ...).
CATEGORIES = [
    "circle", "house", "power outlet", "chair", "bread",
    "mailbox", "snowman", "bus", "cake", "cup",
    "traffic light", "tree", "sun", "face", "cat",
    "star", "fish", "flower", "car", "door",
]
NUM_CATEGORIES = len(CATEGORIES)

IMG_SIZE = 64            # model input is 3 x 64 x 64
MAX_PER_REGION = 3000    # per category, per region cap when sampling the dataset
SEED = 340

"""Evaluate a trained model on the held-out test set.

  python -m doodle.evaluate                 # evaluates models/model.pt
  python -m doodle.evaluate --name small_mixed

Writes results/metrics[_<name>].json and results/RESULTS[_<name>].md with:
  * region + category accuracy at 25 / 50 / 75 / 100 % of the drawing
  * baselines: always-guess-the-most-common region, category-only, logistic regression on pixels
  * region confusion matrix
  * the "game" setting: combining six doodles from the same region
"""
import argparse
import json

import numpy as np
import torch
from torch.utils.data import DataLoader

from .config import CATEGORIES, MODEL_DIR, NUM_CATEGORIES, RESULTS_DIR, SEED
from .data import DoodleDataset, Strokes, split_indices
from .model import load_model
from .regions import NUM_REGIONS, REGION_NAMES
from .train import pick_device

FRACTIONS = [0.25, 0.5, 0.75, 1.0]


@torch.no_grad()
def predict(model, strokes, idx, fraction, device, workers):
    """Returns (category predictions, region log-probabilities) for the drawings in idx."""
    mode = "complete" if fraction >= 1 else fraction
    loader = DataLoader(DoodleDataset(strokes, idx, mode), batch_size=256, num_workers=workers)
    cats, logps = [], []
    for img, cat, _ in loader:
        cat_logits, reg_logits = model(img.to(device), cat.to(device))
        cats.append(cat_logits.argmax(1).cpu().numpy())
        logps.append(torch.log_softmax(reg_logits, 1).cpu().numpy())
    return np.concatenate(cats), np.concatenate(logps)


def macro_recall(y, pred):
    return float(np.mean([(pred[y == r] == r).mean() for r in range(NUM_REGIONS) if (y == r).any()]))


def simulate_players(logp, region, category, k, n_players, rng):
    """A 'player' = k doodles of k different categories, all from one region.
    (Different people from the same region - the dataset has no player ids.)"""
    by = {(r, c): np.where((region == r) & (category == c))[0]
          for r in range(NUM_REGIONS) for c in range(NUM_CATEGORIES)}
    sums, truth = [], []
    for _ in range(n_players):
        r = rng.integers(NUM_REGIONS)
        cats = rng.choice(NUM_CATEGORIES, size=k, replace=False)
        picks = [rng.choice(by[(r, c)]) for c in cats if len(by[(r, c)])]
        sums.append(logp[picks].sum(0))
        truth.append(r)
    return np.asarray(sums), np.asarray(truth)


def fit_alpha(sums, truth):
    """Doodles are not independent clues, so adding their log-probabilities is
    over-confident. Find the scale `alpha` that gives the best-calibrated
    (lowest negative log-likelihood) combined probabilities."""
    best = (np.inf, 1.0)
    for alpha in np.linspace(0.1, 1.5, 57):
        z = alpha * sums
        z = z - z.max(1, keepdims=True)
        logp = z - np.log(np.exp(z).sum(1, keepdims=True))
        nll = -logp[np.arange(len(truth)), truth].mean()
        best = min(best, (nll, float(alpha)))
    return best[1]


def softmax(z):
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="model")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--skip-logreg", action="store_true")
    args = ap.parse_args()

    device = pick_device()
    model, ckpt = load_model(MODEL_DIR / f"{args.name}.pt", device)
    strokes = Strokes()
    tr, va, te = split_indices(len(strokes))
    y_te, c_te = strokes.region[te], strokes.category[te]
    rng = np.random.default_rng(SEED)
    out = {"name": args.name, "arch": ckpt["arch"], "train_mode": ckpt["mode"], "epoch": ckpt["epoch"],
           "test_drawings": int(len(te)), "regions": REGION_NAMES}

    # ---- CNN at each completion level ----
    out["by_completion"] = {}
    for f in FRACTIONS:
        cat_pred, logp = predict(model, strokes, te, f, device, args.workers)
        reg_pred = logp.argmax(1)
        out["by_completion"][str(int(f * 100))] = dict(
            category_accuracy=float((cat_pred == c_te).mean()),
            region_accuracy=float((reg_pred == y_te).mean()),
            region_balanced_accuracy=macro_recall(y_te, reg_pred),
            region_top3_accuracy=float((np.argsort(-logp, 1)[:, :3] == y_te[:, None]).any(1).mean()),
        )
        print(f"{int(f * 100):3d}% drawn:", out["by_completion"][str(int(f * 100))], flush=True)
    full = out["by_completion"]["100"]
    out["region_accuracy_complete"] = full["region_accuracy"]
    conf = np.zeros((NUM_REGIONS, NUM_REGIONS), int)
    np.add.at(conf, (y_te, reg_pred), 1)
    out["confusion_matrix_rows_true_cols_pred"] = conf.tolist()
    out["region_accuracy_per_category"] = {
        CATEGORIES[c]: float((reg_pred[c_te == c] == y_te[c_te == c]).mean()) for c in range(NUM_CATEGORIES)}

    # ---- baselines ----
    y_tr, c_tr = strokes.region[tr], strokes.category[tr]
    majority = np.bincount(y_tr).argmax()
    base = {"majority_region": float((y_te == majority).mean()), "chance": 1 / NUM_REGIONS}
    # category-only: most common region for that category (no drawing information at all)
    table = np.zeros((NUM_CATEGORIES, NUM_REGIONS))
    np.add.at(table, (c_tr, y_tr), 1)
    base["category_only"] = float((table.argmax(1)[c_te] == y_te).mean())
    if not args.skip_logreg:
        # logistic regression on 16x16 downsampled pixels (+ which category), on a 60k subset
        from sklearn.linear_model import LogisticRegression
        from .render import render

        def feats(idx):
            X = np.zeros((len(idx), 3 * 16 * 16 + NUM_CATEGORIES), np.float32)
            for row, i in enumerate(idx):
                img = render(strokes.get(int(i)))
                X[row, :768] = img.reshape(3, 16, 4, 16, 4).mean((2, 4)).ravel()
                X[row, 768 + strokes.category[i]] = 1
            return X
        sub_tr, sub_te = rng.choice(tr, 60_000, replace=False), rng.choice(te, 15_000, replace=False)
        clf = LogisticRegression(max_iter=300, C=1.0).fit(feats(sub_tr), strokes.region[sub_tr])
        base["logistic_regression_pixels"] = float(clf.score(feats(sub_te), strokes.region[sub_te]))
    out["baselines"] = base
    print("baselines:", base, flush=True)

    # ---- the game: combine k doodles ----
    _, logp_va = predict(model, strokes, va, 1.0, device, args.workers)
    y_va, c_va = strokes.region[va], strokes.category[va]
    out["combined_doodles"], alphas = {}, []
    for k in range(1, 7):
        s_va, t_va = simulate_players(logp_va, y_va, c_va, k, 4000, rng)
        alpha = fit_alpha(s_va, t_va)            # calibrated on validation players
        alphas.append(alpha)
        s_te, t_te = simulate_players(logp, y_te, c_te, k, 4000, rng)
        p = softmax(alpha * s_te)
        out["combined_doodles"][str(k)] = dict(
            alpha=alpha, accuracy=float((p.argmax(1) == t_te).mean()),
            top3_accuracy=float((np.argsort(-p, 1)[:, :3] == t_te[:, None]).any(1).mean()),
            mean_confidence=float(p.max(1).mean()))
        print(f"{k} doodles:", out["combined_doodles"][str(k)], flush=True)
    out["game"] = dict(alphas=alphas, alpha=alphas[-1], accuracy=out["combined_doodles"]["6"]["accuracy"])

    # ---- write files ----
    RESULTS_DIR.mkdir(exist_ok=True)
    suffix = "" if args.name == "model" else f"_{args.name}"
    (RESULTS_DIR / f"metrics{suffix}.json").write_text(json.dumps(out, indent=1))
    md = [f"# Results: `{args.name}` ({ckpt['arch']} CNN, trained on {ckpt['mode']} drawings)", "",
          f"Test set: {len(te):,} drawings never seen in training. 9 regions, so random guessing = {100 / NUM_REGIONS:.1f}%.", "",
          "## Accuracy vs. how much of the drawing is finished", "",
          "| Drawing complete | Category accuracy | Region accuracy | Region top-3 |", "|---|---|---|---|"]
    for f, m in out["by_completion"].items():
        md.append(f"| {f}% | {m['category_accuracy']:.1%} | {m['region_accuracy']:.1%} | {m['region_top3_accuracy']:.1%} |")
    md += ["", "## Baselines (region, complete drawings)", "", "| Method | Region accuracy |", "|---|---|",
           f"| Always guess the most common region | {base['majority_region']:.1%} |",
           f"| Category only (ignores the drawing) | {base['category_only']:.1%} |"]
    if "logistic_regression_pixels" in base:
        md.append(f"| Logistic regression on pixels | {base['logistic_regression_pixels']:.1%} |")
    md += [f"| **CNN** | **{full['region_accuracy']:.1%}** |", "",
           "## Combining several doodles (what the game does)", "",
           "Simulated players: k doodles of different objects, all from the same region.", "",
           "| Doodles | Region accuracy | Top-3 | Average confidence shown |", "|---|---|---|---|"]
    for k, m in out["combined_doodles"].items():
        md.append(f"| {k} | {m['accuracy']:.1%} | {m['top3_accuracy']:.1%} | {m['mean_confidence']:.1%} |")
    md += ["", "## Region confusion matrix (rows = true region, columns = predicted, % of row)", "",
           "| | " + " | ".join(n.split()[0][:5] + "." + "".join(w[0] for w in n.split()[1:]) for n in REGION_NAMES) + " |",
           "|---|" + "---|" * NUM_REGIONS]
    for r, row in enumerate(conf):
        md.append(f"| {REGION_NAMES[r]} | " + " | ".join(f"{v / max(row.sum(), 1):.0%}" for v in row) + " |")
    md += ["", "## Region accuracy by object", "", "| Object | Region accuracy |", "|---|---|"]
    for word, acc in sorted(out["region_accuracy_per_category"].items(), key=lambda kv: -kv[1]):
        md.append(f"| {word} | {acc:.1%} |")
    (RESULTS_DIR / f"RESULTS{suffix}.md").write_text("\n".join(md) + "\n")
    print("wrote", RESULTS_DIR / f"metrics{suffix}.json")


if __name__ == "__main__":
    main()

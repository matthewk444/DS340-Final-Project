"""Train the CNN.

  python -m doodle.train                               # main model (deep CNN, partial + complete drawings)
  python -m doodle.train --arch small --name small_mixed
  python -m doodle.train --mode complete --name deep_complete
"""
import argparse
import json
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .config import CATEGORIES, MODEL_DIR, RESULTS_DIR, SEED
from .data import DoodleDataset, Strokes, split_indices
from .model import DoodleNet
from .regions import NUM_REGIONS, REGION_NAMES


def pick_device():
    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


def run_epoch(model, loader, device, region_weight, opt=None, sched=None):
    train = opt is not None
    model.train(train)
    tot = cat_ok = reg_ok = 0
    loss_sum = 0.0
    with torch.set_grad_enabled(train):
        for step, (img, cat, reg) in enumerate(loader):
            if train and step % 500 == 0:
                print(f"   step {step}/{len(loader)}", flush=True)
            img, cat, reg = img.to(device), cat.to(device), reg.to(device)
            cat_logits, reg_logits = model(img, cat)
            loss = F.cross_entropy(cat_logits, cat) + F.cross_entropy(reg_logits, reg, weight=region_weight)
            if train:
                opt.zero_grad(set_to_none=True)
                loss.backward()
                opt.step()
                sched.step()
            n = len(cat)
            tot += n
            loss_sum += loss.item() * n
            cat_ok += (cat_logits.argmax(1) == cat).sum().item()
            reg_ok += (reg_logits.argmax(1) == reg).sum().item()
    return loss_sum / tot, cat_ok / tot, reg_ok / tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default="deep", choices=["small", "deep"])
    ap.add_argument("--mode", default="mixed", choices=["mixed", "complete"],
                    help="train on partial+complete drawings, or complete only")
    ap.add_argument("--name", default="model")
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    torch.manual_seed(SEED)
    np.random.seed(SEED)
    device = pick_device()
    strokes = Strokes()
    tr, va, _ = split_indices(len(strokes))
    print(f"{len(strokes):,} drawings | train {len(tr):,} | val {len(va):,} | device {device}")

    # regions are not perfectly balanced (some have fewer drawings), so weight the loss
    counts = np.bincount(strokes.region[tr], minlength=NUM_REGIONS)
    weight = torch.tensor(counts.sum() / (NUM_REGIONS * counts), dtype=torch.float32, device=device)
    print("train drawings per region:", dict(zip(REGION_NAMES, counts.tolist())))

    kw = dict(batch_size=args.batch, num_workers=args.workers, persistent_workers=args.workers > 0)
    train_loader = DataLoader(DoodleDataset(strokes, tr, args.mode), shuffle=True, drop_last=True, **kw)
    val_full = DataLoader(DoodleDataset(strokes, va, "complete"), **kw)
    val_half = DataLoader(DoodleDataset(strokes, va, 0.5), **kw)

    model = DoodleNet(args.arch, args.dropout).to(device)
    print(f"{args.arch} CNN, {sum(p.numel() for p in model.parameters()):,} parameters")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * len(train_loader))

    MODEL_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    history, best = [], -1.0
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        tl, tc, trg = run_epoch(model, train_loader, device, weight, opt, sched)
        vl, vc, vr = run_epoch(model, val_full, device, weight)
        _, hc, hr = run_epoch(model, val_half, device, weight)
        history.append(dict(epoch=epoch, train_loss=tl, train_cat=tc, train_region=trg,
                            val_loss=vl, val_cat=vc, val_region=vr, val_cat_50=hc, val_region_50=hr))
        print(f"epoch {epoch:2d} | {time.time() - t0:4.0f}s | train loss {tl:.3f} | "
              f"val category {vc:.3f} region {vr:.3f} | at 50% drawn: category {hc:.3f} region {hr:.3f}",
              flush=True)
        score = vr + hr          # region accuracy on complete + half-finished drawings
        if score > best:
            best = score
            torch.save(dict(state_dict=model.state_dict(), arch=args.arch, dropout=args.dropout,
                            mode=args.mode, categories=CATEGORIES, regions=REGION_NAMES,
                            epoch=epoch), MODEL_DIR / f"{args.name}.pt")
    (RESULTS_DIR / f"history_{args.name}.json").write_text(json.dumps(history, indent=1))
    print("saved best checkpoint to", MODEL_DIR / f"{args.name}.pt")


if __name__ == "__main__":
    main()

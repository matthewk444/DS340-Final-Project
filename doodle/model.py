"""The CNN. One shared convolutional trunk with two heads:

  * category head - "what is this?"      (the Quick, Draw!-style guess)
  * region head   - "where is the artist from?"

The region head also receives which object is being drawn, because the
regional clue depends on the object (a region-typical *mailbox* looks nothing
like a region-typical *circle*). During training that is the true label; in
the game it is the prompt the player was given.
"""
import torch
import torch.nn as nn

from .config import NUM_CATEGORIES
from .regions import NUM_REGIONS

ARCHS = {
    "small": dict(widths=[16, 32, 64], convs_per_block=1),
    "deep": dict(widths=[32, 64, 128, 256], convs_per_block=2),
}


def _block(c_in, c_out, n_convs):
    layers = []
    for i in range(n_convs):
        layers += [nn.Conv2d(c_in if i == 0 else c_out, c_out, 3, padding=1, bias=False),
                   nn.BatchNorm2d(c_out), nn.ReLU(inplace=True)]
    layers.append(nn.MaxPool2d(2))
    return nn.Sequential(*layers)


class DoodleNet(nn.Module):
    def __init__(self, arch="deep", dropout=0.3,
                 num_categories=NUM_CATEGORIES, num_regions=NUM_REGIONS):
        super().__init__()
        cfg = ARCHS[arch]
        chans = [3] + cfg["widths"]
        self.features = nn.Sequential(*[
            _block(chans[i], chans[i + 1], cfg["convs_per_block"]) for i in range(len(chans) - 1)
        ])
        feat = chans[-1]
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.drop = nn.Dropout(dropout)
        self.category_head = nn.Linear(feat, num_categories)
        self.category_embed = nn.Embedding(num_categories, 32)
        self.region_head = nn.Sequential(
            nn.Linear(feat + 32, 256), nn.ReLU(inplace=True), nn.Dropout(dropout),
            nn.Linear(256, num_regions),
        )

    def forward(self, x, category=None):
        """Returns (category_logits, region_logits). If `category` is not
        given, the model's own best category guess is used for the region head."""
        f = self.drop(self.pool(self.features(x)).flatten(1))
        cat_logits = self.category_head(f)
        if category is None:
            category = cat_logits.argmax(1)
        region_logits = self.region_head(torch.cat([f, self.category_embed(category)], 1))
        return cat_logits, region_logits


def load_model(path, device="cpu"):
    ckpt = torch.load(path, map_location=device, weights_only=False)
    model = DoodleNet(arch=ckpt["arch"], dropout=ckpt.get("dropout", 0.3))
    model.load_state_dict(ckpt["state_dict"])
    return model.to(device).eval(), ckpt

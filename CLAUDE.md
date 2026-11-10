# DS 340 Final Project — Doodle Region Classifier

Project context for Claude. Source: `docs/project_proposal.pdf` (Final Project Proposal, DS 340, Fall 2026).

## Team
- Lauren Kang, Matthew Kim

## Elevator pitch
Train a neural network to predict what **region of the world** a user is from based on their doodle, **in real time**, updating its prediction as the drawing continues.

## Context
- Similar to Google's Quick, Draw!, where a neural network guesses what a user is drawing — but here we predict *where the drawer is from*, not *what* they drew.
- Goal: explore how a person's drawing style can reveal their geographic region.

## Methods
- Train a **CNN** to classify a doodle into a world region.
- Labels come from the `countrycode` field in the Quick, Draw! data, mapped to geographic regions.

## Data
- **Google Quick, Draw! dataset**: https://github.com/googlecreativelab/quickdraw-dataset
- Use the **raw NDJSON files** (stroke data + `countrycode` metadata).
- Map country codes → geographic regions, then build a manageable, **region-balanced** subset for training/evaluation.
- Render both **complete** and **partial** (unfinished) drawings to images.

## Code resources (must be disclosed)
- https://github.com/elleryqueenhomels/google_sketcher
- Quick, Draw! dataset docs and the docs for our deep-learning framework.
- Claude is used for system design, debugging, unfamiliar concepts, and parts of the drawing interface.
- **Document any adapted or AI-generated code and explain our modifications** (e.g., in code comments and the final paper).

## What's new (our own contributions)
- Organize data into regions, balance counts per region, generate finished + unfinished drawing images.
- Build and train the CNN, tune settings, compare against simpler baselines.
- Test whether training on unfinished drawings improves predictions while someone is still drawing.
- Build a drawing interface that updates predictions live as the user draws.

## Plan / milestones (deadline: Dec 8, 2026)
| Dates | Deliverable |
|---|---|
| Oct 28 – Nov 6 | Inspect dataset, choose drawing categories + region groups, build preprocessing pipeline and data splits |
| Nov 7 – Nov 17 | Train initial CNN, compare with simple baselines (**mid-project TA milestone**) |
| Nov 18 – Nov 27 | Generate partial drawings, compare training approaches, connect model to a basic drawing interface |
| Dec 4 – Dec 8 | Finish paper, prepare lightning talk, finalize demo |

## Demo & evaluation
- **Demo:** user draws on a digital whiteboard; the model shows its region guesses and updates them as the drawing progresses.
- **Evaluation** on held-out drawings:
  - Region accuracy + confusion matrix (which regions get confused).
  - Compare against a simpler model and a **majority-class baseline** (always guess the most common region).
  - Evaluate at **25%, 50%, 75%, 100%** drawing completion to see if more strokes improve predictions.

## Variations to test
- **Training images:** complete drawings only vs. mix of partial + complete.
- **Model complexity:** smaller CNN vs. deeper CNN (with dropout to reduce overfitting).
- **Drawing categories:** per-category performance vs. categories combined.

## Deliverables at end of semester
- Working demo, lightning talk, and final paper.

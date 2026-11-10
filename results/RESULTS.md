# Results: `model` (deep CNN, trained on mixed drawings)

Test set: 50,732 drawings never seen in training. 9 regions, so random guessing = 11.1%.

## Accuracy vs. how much of the drawing is finished

| Drawing complete | Category accuracy | Region accuracy | Region top-3 |
|---|---|---|---|
| 25% | 46.9% | 18.5% | 46.0% |
| 50% | 72.6% | 20.7% | 49.2% |
| 75% | 91.4% | 22.4% | 51.6% |
| 100% | 97.7% | 23.6% | 53.7% |

## Baselines (region, complete drawings)

| Method | Region accuracy |
|---|---|
| Always guess the most common region | 11.6% |
| Category only (ignores the drawing) | 11.5% |
| Logistic regression on pixels | 16.3% |
| **CNN** | **23.6%** |

## Combining several doodles (what the game does)

Simulated players: k doodles of different objects, all from the same region.

| Doodles | Region accuracy | Top-3 | Average confidence shown |
|---|---|---|---|
| 1 | 24.6% | 55.0% | 23.5% |
| 2 | 30.3% | 61.3% | 30.8% |
| 3 | 37.2% | 67.9% | 35.8% |
| 4 | 41.8% | 73.5% | 39.6% |
| 5 | 44.2% | 76.3% | 44.0% |
| 6 | 47.2% | 79.5% | 46.1% |

## Region confusion matrix (rows = true region, columns = predicted, % of row)

| | North.A | Latin.A | Weste.E | Easte.E | Middl.E&A | South.A | East.A | South.A | Ocean. |
|---|---|---|---|---|---|---|---|---|---|
| North America | 28% | 12% | 4% | 13% | 13% | 12% | 9% | 4% | 5% |
| Latin America | 14% | 20% | 4% | 19% | 9% | 14% | 12% | 4% | 4% |
| Western Europe | 17% | 13% | 5% | 21% | 12% | 12% | 11% | 3% | 6% |
| Eastern Europe | 12% | 13% | 5% | 28% | 10% | 12% | 12% | 4% | 4% |
| Middle East & Africa | 14% | 8% | 3% | 11% | 31% | 18% | 9% | 3% | 3% |
| South Asia | 10% | 7% | 2% | 9% | 10% | 41% | 15% | 4% | 2% |
| East Asia | 6% | 6% | 1% | 10% | 5% | 14% | 52% | 4% | 2% |
| Southeast Asia | 13% | 10% | 3% | 13% | 9% | 21% | 21% | 7% | 4% |
| Oceania | 21% | 10% | 5% | 16% | 11% | 12% | 12% | 4% | 9% |

## Region accuracy by object

| Object | Region accuracy |
|---|---|
| power outlet | 34.5% |
| car | 25.4% |
| bus | 25.2% |
| bread | 24.9% |
| house | 24.8% |
| traffic light | 24.6% |
| tree | 24.2% |
| cup | 24.2% |
| snowman | 23.8% |
| face | 23.2% |
| fish | 23.1% |
| mailbox | 23.0% |
| cat | 22.6% |
| cake | 22.5% |
| door | 22.4% |
| sun | 21.8% |
| chair | 21.6% |
| star | 21.2% |
| circle | 19.8% |
| flower | 19.7% |

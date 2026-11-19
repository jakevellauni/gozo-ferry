# Model card: gozo_ferry, version 2

*Owner: Jake Vella (ARI3217 practice exercise). Written for Session 6, Stage 15. Attached to the registered version with `gozo-registry card 2 docs/model_card.md`.*

## Intended use

Estimates the probability that Gozo Channel crossings will be cancelled on a day, from the forecast wind speed in knots, and raises a `warning` when that probability is 0.5 or more.

- **Users:** operations or customer-service staff planning ahead, for example deciding whether to alert passengers early that crossings *may* be disrupted, through the `/predict` API.
- **Should rely on it:** as an early heads-up a day or more ahead, alongside the official forecast and the operator's own judgement.
- **Should not rely on it:** to decide whether a vessel sails. That is the master's and the port authority's decision, made on the actual sea state. Nor should a passenger treat "no warning" as a promise that crossings will run, or a warning as a confirmed cancellation.
- **Not for:** individual sailings or times of day, other routes, or emergency planning.

## Model

Logistic regression on one feature, the forecast wind speed converted from knots to km/h (factor 1.852, logged as a parameter on every run). Trained with seed 42 by `gozo-train`, code version 0.6.0; the MLflow run records the exact commit.

## Data

- **Training:** `data/gozo_ferry.csv`, one row per day of 2025, rows from 1 February to 5 November 2025: 278 days in the window, 15 of them with cancellations; the model is fitted on 222 (`train_model` holds back a random 20 %, as since Stage 7). SHA-256 `ebd606dde638a982a5d3be651e8e2a38af81222217a229d4d558b02d8d0f74ba`.
- **Evaluation:** the frozen holdout `data/holdout.csv`, the 56 days from 6 November to 31 December 2025, never trained on, 9 of them with cancellations. SHA-256 `fa8745708256b933415deaca764ce549328e69344b15280cccc7fa06dfc3d91d`.
- **Not in the data:** wave height or swell, wind direction, gusts, visibility, vessel or crew availability, mechanical faults, or which sailings were affected.

## Metrics

On the frozen holdout:

| Metric | Value |
|---|---|
| F1 (the gate metric) | 0.889 |
| Precision | 0.889 |
| Recall | 0.889 |
| Accuracy | 0.964 |
| ROC-AUC | 0.983 |

The gate requires F1 of at least 0.70 on the holdout, as set in `config/config.yaml`. Accuracy is not used: cancellations are rare, and always predicting «no cancellation» scores 0.839 accuracy but F1 of 0. With only 9 cancellations in the holdout, the 95 % interval for F1 is 0.667 to 1.000, so the pass is clear of the threshold on this sample but not secure.

For comparison, version 1 (trained on every day from 1 January 2025) scored F1 0.842: one extra false alarm on the holdout, well inside that interval. Version 2 is the champion because it scored better on the holdout, as the exercise asks; the difference is one day and should not be read as proof that the shorter window is better.

## Limitations

- **One feature only.** The model sees wind speed and nothing else. It cannot know the sea state (a strong wind after a calm night raises less swell than one blowing for days), the **direction** of the wind (a northerly and a southerly of the same strength affect the Gozo Channel very differently), gusts, or visibility.
- **Small and seasonal.** Cancellations cluster in winter; the training window contains only 15 cancellation days. Estimates near the 50 % line (around 27 knots) are uncertain.
- **One year.** Trained on 2025 only; a stormier or calmer year, or a change of vessel or operating policy, will shift the relationship and the model will not know.
- **Range.** It has seen winds from 1.5 to 39 knots in the window. Above that it extrapolates; the range test checks only that its answers stay probabilities and never fall as the wind rises.
- **The label is a day.** A day counts as cancelled if crossings were cancelled at all; the model says nothing about which sailings, or for how long.

## Monitoring

- The input-wind histogram and average on the Grafana dashboard (Session 4). A sustained rise in average forecast wind beyond what the model was trained on is data drift and a signal to review the model.
- The `predictions` table records the version that made each prediction (`gozo_ferry/2`), so warnings can be matched to actual cancellations, and to versions, once they are known.

## Rollback

- **To roll back:** `make champion V=1`. This moves the `champion` alias to version 1 and restarts the API, with no rebuild.
- **Who may move the alias:** the model's owner, or whoever is on call for the service. Record the reason.
- **Afterwards:** check `/ready` and the newest rows of the `predictions` table, which should both say `gozo_ferry/1`.

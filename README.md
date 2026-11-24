# Gozo ferry cancellation model

Predicts whether the Gozo Channel ferry service will be cancelled, from the forecast wind speed.

## Requirements

Python 3.12 with the venv module. On Ubuntu:

```bash
sudo apt install python3 python3-venv
```

## Install

Run these from this folder, the one with pyproject.toml:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -e ".[dev]"
cp env.example .env
```

## Test

```bash
pytest
```

## Train

```bash
gozo-train
```

The model is saved to `models/model.joblib`. Shared settings are in
`config/config.yaml`; settings for your machine go in `.env`.

## Run the API

```bash
uvicorn gozo_ferry.api:app --port 8888
```

Then, in another terminal:

```bash
curl localhost:8888/health
curl -X POST localhost:8888/predict -H "Content-Type: application/json" -d '{"wind": 30}'
```

`wind` is the forecast wind speed **in knots**. The response gives the
probability the crossing is cancelled and a `warning` flag, using the
threshold in `config/config.yaml`. Interactive docs are at
`http://localhost:8888/docs`.

## Build and run the container

```bash
docker build -t gozo-ferry:0.1 .
docker run -d --name gozo-api -p 8888:8888 gozo-ferry:0.1
curl localhost:8888/health
curl -X POST localhost:8888/predict -H "Content-Type: application/json" -d '{"wind": 30}'
docker logs gozo-api
docker stop gozo-api && docker rm gozo-api
```

## Run everything with docker compose (API + database)

Stop any single container still running from the step above first
(`docker rm -f gozo-api`). Then, from this folder:

```bash
docker compose up -d --build
docker compose ps
curl -X POST localhost:8888/predict -H "Content-Type: application/json" -d '{"wind": 8}'
curl -X POST localhost:8888/predict -H "Content-Type: application/json" -d '{"wind": 20}'
curl -X POST localhost:8888/predict -H "Content-Type: application/json" -d '{"wind": 35}'
docker compose exec db psql -U gozo -d gozo -c "SELECT * FROM predictions;"
```

Every prediction is stored with the wind speed as received (in knots), the
probability, the warning flag, and the model version. Logs for one service
or all of them:

```bash
docker compose logs -f api
docker compose logs
```

Stop everything (keeps the stored data in the `db-data` volume):

```bash
docker compose down
```

Add `-v` to also delete the volume and start from an empty database.

## Watch it: Prometheus and Grafana dashboard

`docker compose up` (above) also starts Prometheus (port 9090) and Grafana
(port 3000) — they're pulled in automatically via the `include:` line at the
top of `compose.yaml`, which merges in `monitoring/compose.yaml`. Open
`http://localhost:3000` — it opens straight on the **Model service**
dashboard, no login needed.

Generate some ordinary traffic and watch the panels move (requests/sec,
latency, average wind received, and the input distribution):

```bash
python3 monitoring/traffic.py --field wind --mean 12 --sd 5 --duration 300
```

Then simulate a stormy winter and watch the **average input value** panel
jump, while **latency** and **requests/sec** stay exactly the same — that's
data drift: the service looks perfectly healthy throughout, even though the
model is now seeing winds far outside what it was trained on:

```bash
python3 monitoring/traffic.py --field wind --mean 22 --sd 6 --duration 300
```

(If running inside a VirtualBox VM: forward host ports 3000 and 9090 to the
same guest ports, the same way you did for 8888.)

## The pipeline (Session 5, Stage 12)

Every check runs with one command, in order, stopping at the first failure:

```bash
make install    # pinned requirements, then the package with its dev tools
cp env.example .env
make ci         # lint, test, validate, gate, build
```

| Target | What it does | Fails when |
|---|---|---|
| `make lint` | ruff checks the code | a style or correctness rule is broken |
| `make test` | pytest, including the property-based range test | any test fails |
| `make validate` | checks `data/gozo_ferry.csv` and `data/holdout.csv` against the schema | a row is invalid or a column is unexpected |
| `make gate` | trains on days before the holdout and scores the frozen holdout | exit 1: below the threshold; exit 2: the holdout changed; exit 3: a file is missing |
| `make build` | builds `gozo-ferry:<version>` and `gozo-ferry:<version>-<commit>`, the version read from `pyproject.toml` | the image does not build |

**The frozen holdout.** `data/holdout.csv` holds the last eight weeks of 2025 (the 56 days from 6 November); `data/gozo_ferry.csv` holds the 309 days before it. The holdout's start date and SHA-256 are in `config/config.yaml`. Never edit `data/holdout.csv`: the gate refuses to run if its fingerprint changes.

**Units.** The data, the schema (`wind` between 0 and 100) and the range test (0 to 80) are all in knots, as the API receives them. Only the model sees km/h, through `knots_to_kmh`.

**Why F1, and why 0.70.** Crossings are cancelled on about one day in eleven, so a model that never predicts a cancellation already scores 0.84 accuracy on the holdout while being useless; F1 is zero for that model and only rises when the model both catches cancellations (recall) and avoids false alarms (precision), the two errors that matter to passengers and the operator. A threshold of 0.70 is well above that do-nothing model; with only 9 cancellations in the holdout the 95 % interval for F1 is wide (about 0.62 to 1.00), so 0.70 is a floor against clear regressions, not a fine-grained target.

Compare with the random split of Stage 7: `make gate GATE_SPLIT=random`. With only about three cancellations in a random 20 %, the score swings wildly, which is why the gate uses the frozen, time-ordered holdout.

## Continuous integration (Session 5, Stage 13)

`.github/workflows/ci.yml` runs `make ci` on every push and pull request, on a fresh machine. On a push to `main`, once every check has passed, the same run publishes the image it just built to GitHub's container registry, as `ghcr.io/<owner>/gozo-ferry:<version>` and `:<version>-<commit>`.

- Require the `ci` check before merging (repository Settings, Branches, branch protection rule for `main`), so a failing gate blocks the merge.
- The version lives only in `pyproject.toml`. To release, change it there; the image tag and `MODEL_VERSION` follow.
- To see the pipeline refuse bad data: on a new branch, break one row of `data/gozo_ferry.csv` (for example a negative wind), push, and open a pull request. The `ci` check goes red at `make validate`.
- No GitHub Actions? Run the same workflow locally with `act -j ci`.
- GitLab users: `.gitlab-ci.yml` runs the same `make` targets.

## Tracking and the registry (Session 6, Stage 14)

MLflow runs as one more service, on port 5000, with its records in Postgres and its files in the `mlflow-artifacts` volume. Prometheus and Grafana now start only when asked (`--profile monitoring`), to save memory on the VM.

```bash
docker compose up -d db mlflow                  # add --profile monitoring for Prometheus and Grafana
gozo-train --train-start none                   # run 1: all of 2025 before the holdout
gozo-registry register                          # register it, only if it passed the gate and came from committed code
make register                                   # run 2: train from 1 February 2025 (config.yaml), then register
gozo-registry alias champion 2                  # the better of the two becomes the champion
gozo-registry show                              # versions, gate metric and aliases
```

Each run records the seed, the knots-to-km/h factor (1.852, the Gozo model's equivalent of the VAT rate), the training window, every holdout metric, the git commit, and the SHA-256 of the data and the holdout. `MLFLOW_TRACKING_URI` in `.env` says where runs go. Open http://localhost:5000 to browse runs (in a VirtualBox VM, forward port 5000 like 8888).

On an existing database volume (one created before this stage), create MLflow's database once: `docker compose exec db createdb -U gozo mlflow`.

## Serving from the registry (Session 6, Stage 15)

The image holds code only. At start-up the API loads `models:/gozo_ferry@champion` and records which version it serves.

- `/health`: the process is alive.
- `/ready`: a model is loaded; answers 503 until then, with `model_version` once ready.
- `/predict` answers 503 until a model is loaded, and returns `model_version` with every answer. Each stored prediction records it too, for example `gozo_ferry/2`.

```bash
make up                                      # db, mlflow and the API, tagged with the version from pyproject.toml
curl localhost:8888/ready                    # {"ready": true, "model_version": "gozo_ferry/2", ...}
make champion V=1                            # roll back: move the alias to version 1 and restart the API
curl localhost:8888/ready                    # now gozo_ferry/1, with no rebuild
make champion V=2                            # and forward again
```

To work without the registry on your own machine, outside compose, set `MODEL_URI=models/model.joblib` (written by `gozo-train`) and run uvicorn directly. The image holds no model file, so inside compose the API always needs the registry.

The model card is in `docs/model_card.md`; attach it to a version with `gozo-registry card 2 docs/model_card.md`.

## The knowledge layer (Session 7, Stage 16)

The cancellation log, `data/gozo_operations_2025.csv`, records 77 cancelled crossings of 2025 as staff on duty wrote them: the two ports are written ten ways and the reasons fourteen ways. The knowledge in `kg/` says what each entry means:

| File | What it holds |
| --- | --- |
| `kg/schema.yaml` | The classes (port, vessel, reason, label, cancellation), their relationships and cardinalities, and the version of the knowledge |
| `kg/ports.yaml` | Mġarr and Ċirkewwa, each with every spelling found in the log |
| `kg/reasons.yaml` | Weather (wind, sea state, visibility), technical, operational, each with its wordings |
| `kg/vessels.yaml` | The fleet |
| `kg/questions.yaml` | The competency questions, with the answers worked out by hand |

```bash
make profile                      # the log as written: spellings per port, wordings per reason
make ask                          # both routes on the three questions; ROUTE=keyword SHOW=--show to see what a search finds
make kg-version                   # the version of the knowledge, from kg/schema.yaml
```

The decision to add the layer, and the choice of a cancellation's key (date, time and port), are in `docs/adr/0001-knowledge-layer.md`.

### How a change to `kg/` is reviewed and released

A change to `kg/` is a change like any other: it goes on a branch, through a pull request, and cannot be merged until `make ci` passes on GitHub. The tests are the gate for the knowledge: every file must conform to the schema, every log entry must link to a port, a vessel and a reason, and every competency question must give its expected answer. A new spelling of a port, or a new wording of a reason, stops the build until the operations manager adds it to the labels, or decides it is something new.

The knowledge has a version of its own, in one place: the `version` line of `kg/schema.yaml`. Once `main` passes, release it as a tag:

```bash
make kg-release                   # runs the tests, refuses uncommitted changes, tags kg-v<version>
git push origin kg-v1.0
```

A tag is never reused. To release a change, raise the version (1.1 for added or corrected knowledge, 2.0 for a change to the schema that files or queries depend on), commit, and release again.

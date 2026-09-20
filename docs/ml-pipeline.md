# ML-Ready Matching Pipeline

The rule-based matching baseline remains active by default. The ML layer is intentionally optional and honest about readiness.

## Label Export

`GET /api/ml/labels/export` exports labels from durable approved/rejected mapping decisions.

## Training

`POST /api/ml/train` requires:

- `ADMIN` role
- a minimum configured number of labelled decisions
- optional ML dependencies from `backend/requirements-ml.txt`
- `NAMM_ENABLE_LOCAL_ML_TRAINING=true`

If labels are insufficient, the endpoint returns HTTP `422`. If dependencies or the explicit enable flag are missing, the model run is stored as skipped and the rule baseline stays active.

## Evaluation

`GET /api/ml/evaluate` compares the active rule baseline with the latest trained or skipped model run metadata. No fabricated model metrics are produced.

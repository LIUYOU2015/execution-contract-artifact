# Execution-contract reproducibility artifact

The completed **32/32 model-assisted primary-source audit** is in [RECHECK_32.md](RECHECK_32.md) and [RECHECK_32.json](RECHECK_32.json), updated November 18, 2026. Each assertion has a source version, location, observation and hash; evidence classes and remaining scope limits stay explicit.

Browse [all 54 candidates](COHORT_54.md) (23 detailed / 28 context / 3 excluded), [all 18 trials](trials-18.md), the [proxy/driver](experiment.py), [scoped Docker perimeter](server.py), [source pins](common.py), and [configuration](perimeter.json). [Human review status](HUMAN_REVIEW_STATUS.json) remains separate from the model audit.

Download [reproduction-package.zip](reproduction-package.zip) for the canonical layout, complete raw events/request bodies/observations, separate pilots/stopped-run history, protocol/amendment, original 251-claim ledger, current audit and offline verifier. Root Python files are browsing copies; execute canonical paths after extraction.

```sh
unzip reproduction-package.zip -d reproduction-package
cd reproduction-package
python3 tools/verify_package.py
python3 native/code/c01-lost-reply/analyze.py native/runs/20261115-c01-main-02 --out /tmp/c01-recomputed-NEW.json
python3 literature/illustrative-ledger/recompute.py
```

Python 3.12 is sufficient for offline verification. Native rerun details are in REPRODUCE.md inside the ZIP. Main02 has 18 valid trials; [earlier history](EXPERIMENT_HISTORY.md) is retained separately. Signed observation brackets and censored manual retention are preserved. The resource-policy ledger is constructed. No human agreement or independent native replication is implied by the model audit.

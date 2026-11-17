# Execution-contract reproducibility artifact

Browse [all54candidate records](COHORT_54.md) (**23detailed /28context /3excluded**), [all18main trials](trials-18.md), the [proxy/driver](experiment.py), [scoped Docker perimeter](server.py), [source pins](common.py), and [perimeter configuration](perimeter.json).

Download **[reproduction-package.zip](reproduction-package.zip)** for the canonical directory layout, full raw request/event/observation data, frozen protocol/amendment, both pilots and the stopped main run,251claim ledger, source adjudications and offline verification. The Python files at repository root are exact browsing copies; execute the canonical paths after extracting the ZIP.

```sh
unzip reproduction-package.zip -d reproduction-package
cd reproduction-package
python3 tools/verify_package.py
python3 native/code/c01-lost-reply/analyze.py native/runs/20261115-c01-main-02 --out /tmp/c01-recomputed-NEW.json
python3 literature/illustrative-ledger/recompute.py
```

Offline verification requires Python3.12and no Docker/model API. Native-rerun instructions are in REPRODUCE.md inside the ZIP. The main02campaign has18valid trials; early5valid/1invalid/12unstarted records remain separate, described in [experiment history](EXPERIMENT_HISTORY.md). Signed timing brackets and censored manual retention are preserved. The32source checks are model-assisted; the constructed resource ledger is distinct from measurements. See PACKAGE_MANIFEST.json for all content hashes and source-provenance mappings.

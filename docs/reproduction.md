# Code and reproduction

## Verify the public download

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python code/verify_download.py
```

`verify_download.py` checks SHA256, gzip contents, identifiers, CRS, missing values, GeoJSON/CSV agreement and all subzone sums. It independently recalculates building estimates from the published GFA, archetype, construction year and subzone controls. It does not require the original workspace or a network request.

The report from preparing this snapshot is [`download_verification.json`](download_verification.json). Original full-pipeline checks are [`validation_summary.json`](validation_summary.json) and [`independent_validation.json`](independent_validation.json).

## Re-run the original spatial pipeline

The scripts used to produce the calibration are included. They require source inputs that are separate from the public download:

| Expected input | Location relative to repository |
|---|---|
| Original compiled building inventory, EPSG:3414 | `data/raw/buildings/sg_buildings_3414.gpkg` |
| MP2019 subzone geometry | `data/raw/boundaries/mp2019_subzones.geojson` |
| MP2025 mainland mask | `data/raw/boundaries/mp2025_mainland_mask.geojson` |
| Fixed-year SingStat population snapshots | `data/raw/population/` |

Paths are configured in [`config/paths.json`](../config/paths.json). Original building inputs and unrelated research files are not bundled here. The download's reduced attributes do not replace the full source GeoPackage expected by the spatial pipeline.

With the spatial inputs available, fetch and verify the fixed-year population snapshots, then calibrate and check a new run:

```bash
python code/prepare_sources.py
python code/calibrate_population.py --output results/runs/reproduction
python code/verify_calibration.py --output results/runs/reproduction
python code/export_download.py --input results/runs/reproduction/population_calibrated.gpkg --output exports/reproduction
```

`prepare_sources.py` uses the recorded URLs and SHA256 in the source manifest. A changed upstream file is reported as a different snapshot. `calibrate_population.py` writes to a new output directory and refuses to overwrite an existing run. Its assertions describe the specific 2026-11-15 inventory, rather than a generic arbitrary-building dataset.

## Included scripts

| Script | Role |
|---|---|
| `calibrate_population.py` | Building weights, spatial assignment, annual subzone controls, allocation, diagnostics and S2 aggregation |
| `verify_calibration.py` | Independent recalculation against original workbooks and full outputs |
| `prepare_sources.py` | Fetch and verify fixed source population snapshots |
| `project_paths.py` | Package-relative path configuration |
| `export_download.py` | Export selected population attributes and WGS84 geometry; gzip, metadata and SHA256 |
| `verify_download.py` | Recalculate and verify the public download |

Python dependencies are pinned in [`requirements.txt`](../requirements.txt), matching the tested research environment (Python 3.9.6). The public export is tested after reprojection and coordinate rounding; population values retain their original precision.

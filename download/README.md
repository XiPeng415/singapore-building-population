# Download: Singapore Building-Level Population Data / 新加坡建筑级人口数据

This folder contains **GeoJSON building footprint polygons with modelled resident population**, plus the attributes and subzone controls used to calculate them.

本文件夹提供**新加坡建筑级居民人口估计 GeoJSON**。空间单位为建筑 footprint 多边形，每条 feature 对应一条源建筑记录；人口是分区总量约束下的模型估计。

**Source credits / 来源署名:** Building data: **Buildings.sg v5, City Syntax Lab, National University of Singapore**, with **© OpenStreetMap contributors** and the upstream sources acknowledged by Buildings.sg. Annual population controls: **SingStat**. Assignment boundaries: **URA MP2019**. This project produces the population allocation fields. [Full attribution and method references](../docs/sources_and_attribution.md) · [Third-party data terms](../THIRD_PARTY_NOTICES.md).

| Download | Description |
|---|---|
| [singapore_building_population.geojson](singapore_building_population.geojson?raw=1) | 75.33 MiB; ready to open in QGIS, ArcGIS or GeoPandas; contains 2025 and provisional 2026 population |
| [singapore_building_population.geojson.gz](singapore_building_population.geojson.gz?raw=1) | 10.73 MiB; identical GeoJSON compressed with gzip; extract to obtain `.geojson` |
| [building_population_attributes.csv](building_population_attributes.csv?raw=1) | 20.70 MiB; population and calculation inputs, joined by `source_fid` |
| [subzone_population_controls.csv](subzone_population_controls.csv?raw=1) | 332 subzones × 2 years; target residents and allocation reconciliation |
| [metadata.json](metadata.json) | Dataset version, scope, exact file sizes and checksums |
| [SHA256SUMS.txt](SHA256SUMS.txt) | File integrity checksums |

## Coverage and version

- **118,782 source building records**; **85,007 residential-class records**. This is the source inventory's coverage, not a claim to contain every Singapore building.
- **Geometry:** building footprint MultiPolygons. **CRS:** WGS84 / EPSG:4326, coordinate order longitude then latitude, seven coordinate decimal places. Reprojection and coordinate rounding do not change population values.
- **Population:** end-June Singapore residents, citizens and permanent residents. Fractional people express model allocation weights; keep decimal values when aggregating.
- **2025:** `resident_pop_2025`; declared population geography and assignment polygons both MP2019.
- **2026:** `resident_pop_2026_provisional`; MP2025 population controls mapped to same-name MP2019 polygons. Boundary equivalence has not been confirmed.
- **Snapshot:** 2026-11-15. The download retains all source buildings and is not clipped to the mainland mask.

The 2025 and 2026 totals are 4,204,560 and 4,231,650 respectively, equal to sums of the published subzone controls. They differ from the separately rounded national totals by 40 and 130 people. Do not interpret the two-year difference as pure population growth, given the population source's boundary-vintage change.

## GeoJSON fields

| Field | Meaning |
|---|---|
| `source_fid` | Unique building identifier within this snapshot; join key to the attributes CSV |
| `building_archetype` | Source building class |
| `is_residential` | Whether the archetype participates in the residential allocation model |
| `SUBZONE_C` | MP2019 subzone code assigned using building centroid |
| `SUBZONE_N` | MP2019 subzone name |
| `PLN_AREA_N` | Planning area name |
| `resident_pop_2025` | Allocated 2025 residents, persons |
| `resident_pop_2026_provisional` | Allocated 2026 residents, persons; provisional geography |
| `allocation_status_2025`, `allocation_status_2026` | `allocated`, `nil_target_with_support`, `nil_target_no_support` or `outside_boundary` |

There are **38 buildings with null population** in each year, including 13 residential-class records outside the available subzone polygons. A null is unallocated/unknown. Matched non-residential buildings receive zero. An official “–” means nil or negligible; its point estimate is zero and its source flag is retained in the controls CSV.

The attributes CSV adds `gross_floor_area` (m²), `built_year`, `built_year_known`, `res_ratio`, `res_pop_est_raw` (proxy persons), `eligible_2025`, `eligible_2026`, `calibration_factor_2025` and `calibration_factor_2026` (dimensionless). These support an independent reconstruction of the allocation. Construction years outside 1800–2100 are treated as unknown; known years later than the reference year are excluded.

## Read and verify

```python
import geopandas as gpd

buildings = gpd.read_file("download/singapore_building_population.geojson")
population = buildings["resident_pop_2026_provisional"]
print(population.sum(min_count=1))
print("Unallocated buildings:", population.isna().sum())
```

To extract the compressed file: `gzip -dk download/singapore_building_population.geojson.gz` (use this in a folder without an existing decompressed file). To check data and recalculate the allocation: `python code/verify_download.py` from the repository root.

See [methodology](../docs/methodology.md), [sources](../README.md#sources-and-attribution) and the [verification report](../docs/download_verification.json).

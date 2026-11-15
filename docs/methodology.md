# Population allocation framework

The method is building-weighted dasymetric allocation: published resident population is distributed within each subzone according to eligible residential floor-area weights.

```text
q_i = gross_floor_area_i × residential_ratio(type_i) / 28 × 0.94
w_i,y = q_i for eligible buildings, otherwise 0
k_z,y = published_residents_z,y / sum(w_i,y in z)
p_i,y = w_i,y × k_z,y
```

The residential ratios are landed_property 1.00, hdb 0.93, private_apartment 0.95, shophouse 0.45, mixed_development 0.50 and nursing_home 1.00. Other classes receive a zero residential weight. The shared constants 28 m²/person and 0.94 cancel in the within-subzone normalization; the calibrated share depends on residential GFA and eligibility.

Buildings with a known construction year later than the reference year are excluded. Unknown construction years are retained. Year-only completion information cannot resolve completion before or after June within the same year. Nursing homes remain part of the source model's residential weighting.

## Spatial and population controls

Building centroids are calculated in EPSG:3414 and assigned to MP2019 subzones by intersection. A centroid intersecting multiple subzones is assigned to the lexicographically first `SUBZONE_C`, with ties saved for inspection. Source controls are matched using the normalized planning-area and subzone name pair, with case and surrounding whitespace normalized, without fuzzy matching.

Controls are the independently published `Age = Total`, `Sex = Total` rows in each annual SingStat workbook. Fine age/sex cells are rounded; summing those cells produces different totals, so they are used for diagnostics rather than control values. The official “–” denotes nil or negligible; its allocation point estimate is zero and the source flag is retained.

2025 controls declare MP2019 geography. 2026 controls declare MP2025, currently mapped to same-name MP2019 polygons. The latter mapping is provisional until MP2025 geometries or a verified boundary correspondence is available.

Allocation uses full subzone support before any mainland filter. The public GeoJSON contains the full source building inventory. The wider research pipeline also aggregates calibrated buildings to sparse S2 L21 tokens; this does not change building allocation. Building-subzone assignments are retained when a token's centre lies in another subzone.

## Verification and interpretation

For each year, allocated building values sum to the 332 source subzone controls within floating-point tolerance. There is no positive-population subzone without residential support in this snapshot. The original pipeline independently recalculates the allocation and compares CSV, GeoPackage and S2 totals. The public download verifier reconstructs weights from GFA and class, applies construction-year eligibility, and compares the resulting values with both CSV and GeoJSON.

Calibration factors below 0.25 or above 2 are inspection flags; they are not clipped. In 2026, 71 subzones are flagged, including 70 below 0.25 and one above 2. A large correction can reflect source building coverage, archetype classification or GFA assumptions, rather than population change alone.

These checks assess calculations and constraints. Independent building occupancy observations, holdout accuracy estimates and confidence intervals are not available in this snapshot. Spatial allocation within a subzone remains dependent on the building inventory and model weights.

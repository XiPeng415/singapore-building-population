#!/usr/bin/env python3
"""Check downloadable files and independently reconstruct the allocation.

Building inputs: Buildings.sg / City Syntax Lab, NUS; OpenStreetMap contributors.
Ratios are inherited local assumptions; see ../docs/sources_and_attribution.md.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RATIOS = {'landed_property': 1., 'hdb': .93, 'private_apartment': .95,
          'shophouse': .45, 'mixed_development': .5, 'nursing_home': 1.}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--download', type=Path, default=ROOT / 'download')
    ap.add_argument('--report', type=Path, help='Optional verification JSON output.')
    args = ap.parse_args()
    folder = args.download
    metadata = json.loads((folder / 'metadata.json').read_text())
    for line in (folder / 'SHA256SUMS.txt').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        assert digest(folder / name) == checksum, f'Checksum mismatch: {name}'
    with gzip.open(folder / 'singapore_building_population.geojson.gz', 'rb') as f:
        h = hashlib.sha256()
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
        assert h.hexdigest() == digest(folder / 'singapore_building_population.geojson')
    geo = gpd.read_file(folder / 'singapore_building_population.geojson').set_index('source_fid').sort_index()
    table = pd.read_csv(folder / 'building_population_attributes.csv').set_index('source_fid').sort_index()
    controls = pd.read_csv(folder / 'subzone_population_controls.csv')
    assert len(geo) == len(table) == metadata['feature_count']
    assert geo.index.is_unique and table.index.is_unique and geo.index.equals(table.index)
    assert geo.crs.to_epsg() == 4326
    assert geo.geometry.notna().all() and not geo.geometry.is_empty.any()
    assert set(geo.geom_type) <= {'Polygon', 'MultiPolygon'}
    assert int(table.is_residential.sum()) == metadata['residential_feature_count']
    assert table.is_residential.equals(table.building_archetype.isin(RATIOS))
    assert geo.is_residential.equals(table.is_residential)
    for field in ('building_archetype', 'SUBZONE_C', 'SUBZONE_N', 'PLN_AREA_N',
                  'allocation_status_2025', 'allocation_status_2026'):
        assert geo[field].fillna('').equals(table[field].fillna('')), field
    ratio = table.building_archetype.map(RATIOS).fillna(0.)
    raw = table.gross_floor_area * ratio / 28. * .94
    assert np.allclose(ratio, table.res_ratio, atol=1e-12, rtol=0)
    assert np.allclose(raw, table.res_pop_est_raw, atol=1e-8, rtol=1e-12)
    year_numeric = pd.to_numeric(table.built_year, errors='coerce')
    known = year_numeric.between(1800, 2100)
    assert known.equals(table.built_year_known)
    report = {'checksums_match': True, 'compressed_file_matches_geojson': True,
              'features': len(geo), 'residential_features': int(table.is_residential.sum()),
              'crs': 'EPSG:4326', 'population_only_properties': geo.drop(columns='geometry').columns.tolist(),
              'invalid_geometries_in_export': int((~geo.is_valid).sum()),
              'years': {}}
    for year in (2025, 2026):
        field = 'resident_pop_2025' if year == 2025 else 'resident_pop_2026_provisional'
        control = controls.loc[controls.year.eq(year)].set_index('SUBZONE_C')
        assert len(control) == 332 and control.index.is_unique
        eligible = table.is_residential & ~(known & year_numeric.gt(year))
        assert eligible.equals(table[f'eligible_{year}'])
        weight = raw.where(eligible, 0.)
        denom = weight.groupby(table.SUBZONE_C).sum()
        target = table.SUBZONE_C.map(control.target_residents)
        expected = weight * target / table.SUBZONE_C.map(denom)
        expected.loc[target.notna() & weight.eq(0)] = 0.
        assert expected.isna().equals(table[field].isna())
        assert geo[field].isna().equals(table[field].isna())
        assert np.allclose(geo[field], table[field], equal_nan=True, rtol=0, atol=1e-9)
        assert np.allclose(expected, table[field], equal_nan=True, rtol=1e-12, atol=1e-8)
        values = geo[field].dropna()
        assert np.isfinite(values).all() and values.ge(0).all()
        sums = geo.groupby('SUBZONE_C')[field].sum(min_count=1).reindex(control.index).fillna(0.)
        residual = (sums - control.target_residents).abs()
        assert residual.max() < 1e-7
        assert geo.loc[geo.SUBZONE_C.isna(), field].isna().all()
        assert geo.loc[geo.SUBZONE_C.notna() & ~geo.is_residential, field].eq(0).all()
        assert abs(values.sum() - metadata['population_years'][str(year)]['allocated_residents']) < 1e-7
        report['years'][str(year)] = {
            'allocated_residents': float(values.sum()),
            'null_buildings': int(geo[field].isna().sum()),
            'max_subzone_residual': float(residual.max()),
            'max_independent_building_difference': float((expected - table[field]).abs().max()),
            'geojson_csv_population_match': True,
        }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

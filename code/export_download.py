#!/usr/bin/env python3
"""Export population-only GeoJSON/CSV from the calibrated building layer."""
import argparse
import gzip
import hashlib
import json
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[1]
GEO_FIELDS = [
    'source_fid', 'building_archetype', 'is_residential',
    'SUBZONE_C', 'SUBZONE_N', 'PLN_AREA_N',
    'resident_pop_2025', 'resident_pop_2026_provisional',
    'allocation_status_2025', 'allocation_status_2026',
]
MODEL_FIELDS = GEO_FIELDS + [
    'gross_floor_area', 'built_year', 'built_year_known', 'res_ratio',
    'res_pop_est_raw', 'eligible_2025', 'eligible_2026',
    'calibration_factor_2025', 'calibration_factor_2026',
]


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True, help='Calibrated GeoPackage.')
    ap.add_argument('--building-source', type=Path, help='Optional original building input, to record its checksum.')
    ap.add_argument('--output', type=Path, default=ROOT / 'download')
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    b = gpd.read_file(args.input, layer='buildings_population')
    assert b.source_fid.is_unique and b.source_fid.notna().all()
    geo = b[GEO_FIELDS + ['geometry']].to_crs(4326)
    # Longitude/latitude precision only; population values retain their precision.
    geo.geometry = shapely.transform(geo.geometry.array, lambda xy: np.round(xy, 7))
    path = out / 'singapore_building_population.geojson'
    with path.open('w', encoding='utf-8') as f:
        f.write('{"type":"FeatureCollection","name":"Singapore building-level resident population estimates",')
        f.write('"description":"2025 and provisional 2026; model estimates; longitude/latitude WGS84",')
        f.write('"features":[\n')
        for n, feature in enumerate(geo.iterfeatures(na='null', drop_id=True)):
            if n:
                f.write(',\n')
            json.dump(feature, f, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        f.write('\n]}\n')
    zipped = path.with_suffix('.geojson.gz')
    with path.open('rb') as src, zipped.open('wb') as dst:
        with gzip.GzipFile(filename='', fileobj=dst, mode='wb', mtime=0) as gz:
            shutil.copyfileobj(src, gz)
    b[MODEL_FIELDS].to_csv(out / 'building_population_attributes.csv', index=False)
    source_dir = args.input.parent
    controls = []
    for year in (2025, 2026):
        z = pd.read_csv(source_dir / f'subzone_calibration_{year}.csv')
        columns = ['SUBZONE_C', 'PA', 'SZ', 'target_residents',
                   'target_nil_or_negligible', 'declared_boundary_vintage',
                   'calibration_factor', 'allocated_residents', 'absolute_residual']
        one = z[columns].copy()
        one.insert(0, 'year', year)
        controls.append(one)
    pd.concat(controls, ignore_index=True).to_csv(out / 'subzone_population_controls.csv', index=False)
    populations = {}
    for year, field in ((2025, 'resident_pop_2025'), (2026, 'resident_pop_2026_provisional')):
        populations[str(year)] = {
            'field': field, 'allocated_residents': float(b[field].sum()),
            'null_buildings': int(b[field].isna().sum()),
            'status': 'vintage_matched' if year == 2025 else 'provisional_MP2025_controls_on_MP2019_polygons',
        }
    metadata = {
        'title': 'Singapore building-level resident population estimates',
        'snapshot_date': '2026-11-15', 'format': 'GeoJSON FeatureCollection',
        'coordinate_reference_system': 'WGS84 / EPSG:4326; longitude, latitude',
        'coordinate_decimal_places': 7, 'geometry': 'MultiPolygon building footprints',
        'feature_count': len(b), 'residential_feature_count': int(b.is_residential.sum()),
        'scope': 'All records in the source building inventory, including non-residential buildings; not a complete-coverage claim.',
        'population_definition': 'Singapore residents (citizens and permanent residents), end June; not all persons.',
        'population_unit': 'persons; fractional model estimates', 'population_years': populations,
        'null_definition': 'Unallocated/unknown; never replace with zero without inspecting allocation_status.',
        'subzone_geometries': 'MP2019; building assignment uses centroid in EPSG:3414 before export reprojection.',
        'method': 'Published subzone total times eligible residential GFA share within that subzone.',
        'source_population_page': 'https://www.singstat.gov.sg/find-data/explore-data-themes/population/geographic-distribution/latest-news-data',
        'source_building_input': {'filename': args.building_source.name, 'sha256': sha256(args.building_source)} if args.building_source else None,
        'calibrated_input_sha256': sha256(args.input),
        'files': [],
    }
    for name in ('singapore_building_population.geojson', 'singapore_building_population.geojson.gz',
                 'building_population_attributes.csv', 'subzone_population_controls.csv'):
        p = out / name
        metadata['files'].append({'file': name, 'bytes': p.stat().st_size, 'sha256': sha256(p)})
    (out / 'metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    paths = [out / row['file'] for row in metadata['files']] + [out / 'metadata.json']
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in paths), encoding='utf-8')
    for row in metadata['files']:
        print(f"{row['file']}: {row['bytes'] / 1024**2:.2f} MiB")


if __name__ == '__main__':
    main()

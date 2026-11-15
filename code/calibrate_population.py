#!/usr/bin/env python3
"""Calibrate building residential weights to published SingStat subzone totals.

Run from any directory. Original datasets and legacy population code are read-only.
2026 is explicitly provisional until a verified MP2025 boundary is supplied.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import s2sphere
import shapely

from project_paths import PACKAGE as BASE, BUILDINGS, BOUNDARY, MASK, SOURCES
RATIOS = dict(landed_property=1., hdb=.93, private_apartment=.95,
              shophouse=.45, mixed_development=.50, nursing_home=1.)
TOL = 1e-7


def clean_json(obj):
    if isinstance(obj, dict):
        return {str(k): clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def write_json(path, obj):
    path.write_text(json.dumps(clean_json(obj), ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def fingerprint(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    st = path.stat()
    return dict(path=str(path), bytes=st.st_size, mtime_ns=st.st_mtime_ns, sha256=h.hexdigest())


def key(pa, sz):
    # Exact normalisation of case/whitespace only. No fuzzy joins or aliases.
    return pa.str.strip().str.upper() + '|' + sz.str.strip().str.upper()


def read_controls(year):
    df = pd.read_excel(SOURCES / f'respopagesex{year}.xlsx', header=2)
    totals = df.loc[(df.Age == 'Total') & (df.Sex == 'Total')].copy()
    text = totals[str(year)].astype(str).str.strip()
    assert (pd.to_numeric(text, errors='coerce').notna() | text.eq('-')).all()
    # '-' is officially nil OR negligible, not a known exact zero.
    totals['target_nil_or_negligible'] = text.eq('-')
    totals['target_residents'] = pd.to_numeric(text.mask(text.eq('-'), '0'))
    totals['source_excel_row'] = totals.index + 4
    totals = totals.rename(columns={'Planning Area': 'PA', 'Subzone': 'SZ'})
    totals['join_key'] = key(totals.PA, totals.SZ)
    assert totals.join_key.is_unique
    assert len(totals) == 388  # 1 national + 55 PA + 332 subzones, verified source layout.
    assert ((totals.PA == 'Total') == ((totals.PA == 'Total') & (totals.SZ == 'Total'))).all()
    national = totals.loc[totals.PA == 'Total', 'target_residents'].item()
    pa = totals.loc[(totals.PA != 'Total') & (totals.SZ == 'Total')].copy()
    sub = totals.loc[totals.SZ != 'Total'].copy()
    assert len(pa) == 55 and len(sub) == 332
    # Preserve published totals rather than summing rounded age/sex detail.
    return sub, pa, national


def spatial_assign(points, zones, out, label):
    j = gpd.sjoin(points[['geometry']], zones[['SUBZONE_C', 'geometry']], how='left', predicate='intersects')
    ties = j.loc[j.index.duplicated(keep=False)].drop(columns='geometry')
    ties.to_csv(out / f'{label}_assignment_ties.csv', index=True)
    j = j.sort_values('SUBZONE_C', na_position='last').loc[lambda x: ~x.index.duplicated(keep='first')]
    return j.SUBZONE_C.reindex(points.index)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default=str(BASE / 'results' / 'runs' / 'new_run'))
    args = ap.parse_args()
    out = Path(args.output).resolve()
    if out.exists():
        raise FileExistsError('Use a new output directory to preserve prior runs.')
    out.mkdir(parents=True)
    inputs = [BUILDINGS, BOUNDARY, MASK] + [SOURCES / f'respopagesex{y}.xlsx' for y in (2025, 2026)]
    before = [fingerprint(p) for p in inputs]
    write_json(out / 'input_manifest_before.json', before)
    print('Reading source buildings and 2019 geography', flush=True)
    b = gpd.read_file(BUILDINGS, fid_as_index=True).to_crs(3414)
    b.insert(0, 'source_fid', b.index)
    b = b.reset_index(drop=True)
    assert len(b) == 118782 and b.source_fid.is_unique
    assert b.geometry.notna().all() and not b.geometry.is_empty.any()
    z = gpd.read_file(BOUNDARY).to_crs(3414).sort_values('SUBZONE_C').reset_index(drop=True)
    repair = z.loc[~z.is_valid, ['SUBZONE_C', 'SUBZONE_N']].copy()
    repair['reason'] = shapely.is_valid_reason(z.loc[~z.is_valid].geometry.values)
    repair.to_csv(out / 'geometry_repairs.csv', index=False)
    z['geometry'] = z.geometry.make_valid()
    assert z.SUBZONE_C.is_unique and z.is_valid.all() and (z.area > 0).all()
    z['join_key'] = key(z.PLN_AREA_N, z.SUBZONE_N)
    assert z.join_key.is_unique
    z['area_km2'] = z.area / 1e6
    points = gpd.GeoDataFrame(index=b.index, geometry=b.centroid, crs=3414)
    b['SUBZONE_C'] = spatial_assign(points, z, out, 'building_centroid')
    for name in ['SUBZONE_N', 'PLN_AREA_N', 'PLN_AREA_C', 'join_key']:
        b[name] = b.SUBZONE_C.map(z.set_index('SUBZONE_C')[name])
    b['res_ratio'] = b.building_archetype.map(RATIOS).fillna(0.)
    b['res_pop_est_raw'] = b.gross_floor_area * b.res_ratio / 28. * .94
    assert np.isfinite(b.res_pop_est_raw).all() and (b.res_pop_est_raw >= 0).all()
    b['is_residential'] = b.building_archetype.isin(RATIOS)
    assert int(b.is_residential.sum()) == 85007
    assert abs(b.res_pop_est_raw.sum() - 6965701.105973358) < TOL
    b['built_year_numeric'] = pd.to_numeric(b.built_year, errors='coerce')
    b['built_year_known'] = b.built_year_numeric.between(1800, 2100)
    b['institution_nursing_home'] = b.building_archetype.eq('nursing_home')

    print('Building centroids -> S2 L21; mainland is a later filter', flush=True)
    ll = points.to_crs(4326)
    ids = [s2sphere.CellId.from_lat_lng(s2sphere.LatLng.from_degrees(p.y, p.x)).parent(21) for p in ll.geometry]
    b['s2l21'] = [c.to_token() for c in ids]
    unique = {c.to_token(): c for c in ids}
    centres = {t: s2sphere.LatLng.from_point(s2sphere.Cell(c).get_center()) for t, c in unique.items()}
    cells = gpd.GeoDataFrame({'s2l21': list(centres)}, geometry=[shapely.Point(v.lng().degrees, v.lat().degrees) for v in centres.values()], crs=4326)
    mask = gpd.read_file(MASK).to_crs(4326).geometry.union_all()
    shapely.prepare(mask)
    cells['in_mainland_cell'] = shapely.contains(mask, cells.geometry.values)
    cells = cells.to_crs(3414)
    cells['cell_SUBZONE_C'] = spatial_assign(cells, z, out, 'cell_centre')
    b['in_mainland_cell'] = b.s2l21.map(cells.set_index('s2l21').in_mainland_cell)
    b['cell_SUBZONE_C'] = b.s2l21.map(cells.set_index('s2l21').cell_SUBZONE_C)

    summaries = {}
    zone_tables = []
    control_tables = []
    pa_tables = []
    config = dict(created_date='2026-11-15', timezone='Asia/Singapore', python=platform.python_version(),
        packages={m: __import__(m).__version__ for m in ['pandas', 'geopandas', 'shapely', 'numpy']},
        raw_formula='gross_floor_area * archetype_res_ratio / 28 * 0.94', ratios=RATIOS,
        calibration_formula='published_subzone_total * eligible_building_raw_weight / sum_eligible_raw_weights_in_subzone',
        assignment='EPSG3414 building centroid intersects full MP2019 subzone; ties by lexicographic SUBZONE_C',
        calibration_scope='all source buildings, full national polygons; apply mainland cell-centre filter only AFTER calibration',
        population_scope='Singapore residents (citizens and PRs); not all persons or non-resident population',
        reference_period='end June of labelled year',
        year_handling='exclude known built_year > reference year; year alone cannot resolve June completion; unknown years retained and flagged',
        nil_handling='published dash is nil or negligible; target point value 0, retain flag; not proof of no residents',
        geography_2025='MP2019 boundaries match declared source vintage',
        geography_2026='PROVISIONAL name-matched MP2019 polygons; source declares MP2025; boundary equivalence NOT verified',
        factor_diagnostic='factor < 0.25 or > 2 is a review flag, not an official threshold; no clipping',
        script_sha256=fingerprint(Path(__file__))['sha256'])
    write_json(out / 'run_configuration.json', config)

    for year in (2025, 2026):
        print('Calibrating', year, flush=True)
        controls, pa, national = read_controls(year)
        controls['year'] = year
        controls['declared_boundary_vintage'] = 2019 if year == 2025 else 2025
        control_tables.append(controls)
        # Outer join retains every source control and every boundary polygon.
        t = z.drop(columns='geometry').merge(controls, on='join_key', how='outer', validate='one_to_one', indicator=True)
        t['join_status'] = t.pop('_merge').astype(str)
        t['year'] = year
        t['geography_status'] = 'vintage_matched' if year == 2025 else 'provisional_MP2025_controls_on_MP2019_polygons'
        b[f'eligible_{year}'] = b.is_residential & ~(b.built_year_known & (b.built_year_numeric > year))
        weight = f'weight_{year}'
        b[weight] = b.res_pop_est_raw.where(b[f'eligible_{year}'], 0.)
        d = b.groupby('SUBZONE_C', dropna=True).agg(raw_proxy=('res_pop_est_raw', 'sum'),
            eligible_proxy=(weight, 'sum'), buildings=('source_fid', 'count'), residential_buildings=('is_residential', 'sum'),
            eligible_residential_buildings=(f'eligible_{year}', 'sum'))
        t = t.merge(d, on='SUBZONE_C', how='left', validate='one_to_one')
        for col in d.columns:
            t[col] = t[col].fillna(0)
        t['calibration_factor'] = np.where(t.eligible_proxy > 0, t.target_residents / t.eligible_proxy, np.nan)
        t['allocation_status'] = np.select([
            t.join_status.ne('both'),
            t.target_residents.gt(0) & t.eligible_proxy.eq(0),
            t.target_residents.eq(0) & t.eligible_proxy.eq(0),
            t.target_residents.eq(0)],
            ['unmatched_geography', 'positive_population_no_residential_support', 'nil_target_no_support', 'nil_target_with_support'],
            default='allocated')
        factors = t.dropna(subset=['SUBZONE_C']).set_index('SUBZONE_C').calibration_factor
        col = 'resident_pop_2025' if year == 2025 else 'resident_pop_2026_provisional'
        b[f'calibration_factor_{year}'] = b.SUBZONE_C.map(factors)
        b[col] = b[weight] * b[f'calibration_factor_{year}']
        mapped = b.SUBZONE_C.isin(t.loc[t.join_status.eq('both'), 'SUBZONE_C'])
        # Nonresidential/excluded-year buildings are explicitly zero only in matched zones.
        b.loc[mapped & b[weight].eq(0), col] = 0.
        b[f'allocation_status_{year}'] = b.SUBZONE_C.map(t.dropna(subset=['SUBZONE_C']).set_index('SUBZONE_C').allocation_status).fillna('outside_boundary')
        b[f'geography_status_{year}'] = t.geography_status.iloc[0]
        t['allocated_residents'] = t.SUBZONE_C.map(b.groupby('SUBZONE_C')[col].sum(min_count=1)).fillna(0.)
        residual = t.target_residents - t.allocated_residents
        t['absolute_residual'] = residual.abs()
        t['unallocated_residents'] = residual.where(residual.abs().gt(TOL), 0.)
        t['factor_review'] = t.calibration_factor.gt(2) | (t.calibration_factor.gt(0) & t.calibration_factor.lt(.25))
        t['raw_density_per_km2'] = t.raw_proxy / t.area_km2
        t['target_density_per_km2'] = t.target_residents / t.area_km2
        supported = t.join_status.eq('both') & t.eligible_proxy.gt(0)
        assert t.loc[supported, 'absolute_residual'].max() < TOL
        assert (b[col].dropna() >= 0).all() and np.isfinite(b[col].dropna()).all()
        assert b.loc[mapped & b.res_ratio.eq(0), col].eq(0).all()
        assert abs(b[col].sum() - t.allocated_residents.sum()) < TOL
        t.to_csv(out / f'subzone_calibration_{year}.csv', index=False)
        t.loc[t.absolute_residual.gt(TOL) | t.join_status.ne('both')].to_csv(out / f'unallocated_or_unmatched_subzones_{year}.csv', index=False)
        t.loc[t.factor_review].sort_values('calibration_factor', ascending=False).to_csv(out / f'factor_review_{year}.csv', index=False)
        p = t.groupby('PA', dropna=False).agg(sum_subzone_targets=('target_residents', 'sum'), allocated_residents=('allocated_residents', 'sum'), eligible_proxy=('eligible_proxy', 'sum')).reset_index()
        p = pa[['PA', 'target_residents']].rename(columns={'target_residents': 'published_PA_total'}).merge(p, on='PA', how='outer', validate='one_to_one')
        p['year'] = year
        p['subzone_minus_PA_rounding_difference'] = p.sum_subzone_targets - p.published_PA_total
        p.to_csv(out / f'planning_area_reconciliation_{year}.csv', index=False)
        pa_tables.append(p)
        raw_csv = pd.read_csv(SOURCES / f'respopagesex{year}.csv')
        assert set(pd.to_numeric(raw_csv.Time)) == {year}
        fine_sum = pd.to_numeric(raw_csv.Pop).sum()
        summaries[year] = dict(official_national_total=national, published_PA_sum=pa.target_residents.sum(),
            published_subzone_sum=controls.target_residents.sum(), rounded_subzones_minus_national=controls.target_residents.sum()-national,
            fine_age_sex_csv_sum=fine_sum, fine_age_sex_minus_subzone_totals=fine_sum-controls.target_residents.sum(),
            subzones=len(controls), matched_subzones=int(t.join_status.eq('both').sum()),
            unmatched_controls=int(t.join_status.eq('right_only').sum()), unmatched_polygons=int(t.join_status.eq('left_only').sum()),
            positive_target_subzones=int(t.target_residents.gt(0).sum()),
            positive_target_no_support_subzones=int(t.allocation_status.eq('positive_population_no_residential_support').sum()),
            allocated_residents=b[col].sum(), unallocated_residents=t.unallocated_residents.sum(),
            max_supported_subzone_residual=t.loc[supported, 'absolute_residual'].max(),
            mainland_allocated_residents=b.loc[b.in_mainland_cell, col].sum(),
            outside_mainland_allocated_residents=b.loc[~b.in_mainland_cell, col].sum(),
            factor_review_subzones=int(t.factor_review.sum()),
            known_future_residential_buildings=int((b.is_residential & ~b[f'eligible_{year}']).sum()),
            known_future_raw_proxy=b.loc[b.is_residential & ~b[f'eligible_{year}'], 'res_pop_est_raw'].sum(),
            allocated_to_unknown_year_buildings=b.loc[~b.built_year_known, col].sum(),
            allocated_to_nursing_homes=b.loc[b.institution_nursing_home, col].sum(),
            geography_status=t.geography_status.iloc[0])
        zone_tables.append(t)

    print('Writing building, subzone, and sparse L21 geospatial outputs', flush=True)
    b['centroid_x_3414_m'] = points.geometry.x
    b['centroid_y_3414_m'] = points.geometry.y
    gpkg = out / 'population_calibrated.gpkg'
    b.to_file(gpkg, layer='buildings_population', driver='GPKG', engine='pyogrio')
    for year, t in zip((2025, 2026), zone_tables):
        gz = z[['SUBZONE_C', 'geometry']].merge(t.dropna(subset=['SUBZONE_C']), on='SUBZONE_C', validate='one_to_one')
        gz.to_file(gpkg, layer=f'subzones_{year}' + ('_provisional' if year == 2026 else ''), driver='GPKG', engine='pyogrio')
    core = ['source_fid', 'id', 'addr_housename', 'building_archetype', 'gross_floor_area', 'built_year',
            'SUBZONE_C', 'SUBZONE_N', 'PLN_AREA_N', 's2l21', 'cell_SUBZONE_C', 'in_mainland_cell',
            'res_ratio', 'res_pop_est_raw', 'institution_nursing_home', 'built_year_known',
            'eligible_2025', 'eligible_2026', 'calibration_factor_2025', 'calibration_factor_2026',
            'resident_pop_2025', 'resident_pop_2026_provisional', 'allocation_status_2025', 'allocation_status_2026',
            'geography_status_2025', 'geography_status_2026', 'centroid_x_3414_m', 'centroid_y_3414_m']
    b[core].to_csv(out / 'building_population_calibrated.csv', index=False)
    b.loc[b.is_residential & b.SUBZONE_C.isna(), core].to_csv(out / 'residential_buildings_outside_boundary.csv', index=False)
    b.loc[b.SUBZONE_C.fillna('NONE').ne(b.cell_SUBZONE_C.fillna('NONE')), core].to_csv(out / 'building_vs_cell_subzone_changes.csv', index=False)
    b.loc[b.is_residential].sort_values('resident_pop_2026_provisional', ascending=False).head(100)[core].to_csv(out / 'top100_calibrated_buildings.csv', index=False)
    # One token may contain buildings assigned to distinct subzones. Preserve the
    # subzone dimension until calibration reconciliation; never recalculate by cell zone.
    rb = b.loc[b.is_residential].copy()
    rb['missing_2025'] = rb.resident_pop_2025.isna().astype(int)
    rb['missing_2026'] = rb.resident_pop_2026_provisional.isna().astype(int)
    grouped = rb.groupby(['s2l21', 'SUBZONE_C'], dropna=False)
    sb = grouped.agg(raw_proxy=('res_pop_est_raw', 'sum'), residential_buildings=('source_fid', 'count'),
        missing_2025=('missing_2025', 'sum'), missing_2026=('missing_2026', 'sum'))
    popcols = ['resident_pop_2025', 'resident_pop_2026_provisional']
    sb = sb.join(grouped[popcols].sum(min_count=1)).reset_index()
    sb.to_csv(out / 's2l21_by_building_subzone.csv', index=False)
    cg = sb.groupby('s2l21')
    c = cg[['raw_proxy', 'residential_buildings', 'missing_2025', 'missing_2026']].sum()
    c = c.join(cg[popcols].sum(min_count=1)).reset_index()
    c['complete_2025'] = c.missing_2025.eq(0)
    c['complete_2026'] = c.missing_2026.eq(0)
    c = cells.merge(c, on='s2l21', validate='one_to_one')
    c.to_file(gpkg, layer='s2l21_residential_points', driver='GPKG', engine='pyogrio')
    c.drop(columns='geometry').to_csv(out / 's2l21_residential_points.csv', index=False)
    pd.concat(control_tables, ignore_index=True).to_csv(out / 'official_subzone_controls.csv', index=False)
    checks = dict(input_buildings=len(b), input_residential_buildings=int(b.is_residential.sum()),
        raw_proxy_total=b.res_pop_est_raw.sum(), mainland_raw_proxy=b.loc[b.in_mainland_cell, 'res_pop_est_raw'].sum(),
        residential_raw_proxy_outside_boundary=b.loc[b.is_residential & b.SUBZONE_C.isna(), 'res_pop_est_raw'].sum(),
        source_building_id_unique=bool(b.id.is_unique), source_fid_unique=bool(b.source_fid.is_unique),
        years=summaries, s2l21_residential_cells=len(c),
        changed_subzone_buildings=int(b.SUBZONE_C.fillna('NONE').ne(b.cell_SUBZONE_C.fillna('NONE')).sum()))
    after = [fingerprint(p) for p in inputs]
    assert before == after, 'A source input changed during execution'
    for year in (2025, 2026):
        col = 'resident_pop_2025' if year == 2025 else 'resident_pop_2026_provisional'
        assert abs(c[col].sum() - b[col].sum()) < TOL
    checks['source_inputs_unchanged'] = True
    write_json(out / 'input_manifest_after.json', after)
    write_json(out / 'validation_summary.json', checks)
    write_json(out / 'workbook_data.json', {'summary': checks,
        'zones': pd.concat(zone_tables, ignore_index=True).replace({np.nan: None}).to_dict(orient='records'),
        'pa': pd.concat(pa_tables, ignore_index=True).replace({np.nan: None}).to_dict(orient='records')})
    write_report(out, checks, zone_tables)
    print(json.dumps(clean_json(checks), ensure_ascii=False, indent=2), flush=True)


def write_report(out, s, tables):
    a, b = s['years'][2025], s['years'][2026]
    problem = tables[1].loc[tables[1].unallocated_residents.gt(TOL)]
    rows = '\n'.join(f"| {r.PA} | {r.SZ} | {r.target_residents:,.0f} | {r.eligible_proxy:,.3f} | {r.unallocated_residents:,.0f} |" for r in problem.itertuples())
    text = f'''# 建筑居民人口分区校准

2026年6月是截至2026年11月15日的最新可用年度居民人口基准。建筑级分配已按该年度的官方分区总量计算，字段为 `resident_pop_2026_provisional`。**2026年表声明使用Master Plan 2025分区，目前几何来自Master Plan 2019，尚无经核验的2025分区几何或边界对照，因此2026年空间结果必须视为暂定，不能当作已完成边界一致性验证的正式人口输入。**

同批保存 `resident_pop_2025`，以2025年6月人口作对照；官方说明采用Master Plan 2019，与现有边界版本一致。两年度均使用住宅建筑面积权重进行分区内分配。建筑级数值是模型估计，分区合计对账不等于建筑居住人数得到独立验证。

## 结果与对账

| 项目 | 2025年6月 | 2026年6月暂定 |
|---|---:|---:|
| 官方全国居民人口合计 | {a['official_national_total']:,.0f} | {b['official_national_total']:,.0f} |
| 官方332个subzone合计 | {a['published_subzone_sum']:,.0f} | {b['published_subzone_sum']:,.0f} |
| 已分配至源建筑 | {a['allocated_residents']:,.6f} | {b['allocated_residents']:,.6f} |
| 无住宅权重承载的未分配居民 | {a['unallocated_residents']:,.0f} | {b['unallocated_residents']:,.0f} |
| 有人口但无住宅权重的分区数 | {a['positive_target_no_support_subzones']} | {b['positive_target_no_support_subzones']} |
| 具有住宅权重的分区最大对账误差 | {a['max_supported_subzone_residual']:.12g} | {b['max_supported_subzone_residual']:.12g} |
| 本岛格中心筛选后的已分配居民 | {a['mainland_allocated_residents']:,.6f} | {b['mainland_allocated_residents']:,.6f} |

原始建筑表含{s['input_buildings']:,}栋，住宅类{s['input_residential_buildings']:,}栋，原始住宅容量合计{s['raw_proxy_total']:,.6f} proxy persons。先按完整分区校准全部源建筑，再按原研究规则筛选本岛。这样不会把岛外或掩膜外人口强行塞入本岛建筑。校准前后比较须使用相同范围与人口口径；原始容量与居民人口不是同一观测量。小于1e-7人的浮点残差在未分配人数中记0，原始绝对误差单独保留。

## 分配方法

```text
raw_weight_i = gross_floor_area_i × residential_ratio_i / 28 × 0.94
eligible_weight_i,y = raw_weight_i, unless known built_year_i > y
k_z,y = published_residents_z,y / sum(eligible_weight_i,y in z)
allocated_residents_i,y = eligible_weight_i,y × k_z,y
```

住宅占比保持原模型：landed_property 1.00、hdb 0.93、private_apartment 0.95、shophouse 0.45、mixed_development 0.50、nursing_home 1.00。分区内的28 m²/人和0.94作为共同常数会约掉；校准后的建筑相对份额由住宅GFA权重决定。

建筑按EPSG3414质心与完整分区polygon的intersects唯一归属；边界多命中按SUBZONE_C字典序处理并导出。名称只规范大小写及首尾空格，用planning area和subzone联合键精确匹配，不做模糊匹配。2025年匹配{a['matched_subzones']}个分区，2026年匹配{b['matched_subzones']}个；同名匹配不能证明跨版本边界相同。

官方Excel提供Age=Total且Sex=Total的独立分区合计，本流程直接取这些控制数，不对年龄或性别分项再次求和。2026年细年龄性别CSV累计值与官方分区合计相差{b['fine_age_sex_minus_subzone_totals']:,.0f}人。全国、PA和subzone控制数各自保留，不为消除舍入差而再次全局缩放。官方“-”表示nil or negligible，在点估计中按0处理，保留target_nil_or_negligible标记。

## 未分配居民与空间限制

| Planning area | Subzone | 2026官方目标人数 | 可用住宅容量权重 | 未分配人数 |
|---|---|---:|---:|---:|
{rows or '| 无 | 无 | 0 | 0 | 0 |'}

目标为正但分区住宅权重为零时，不生成虚构建筑或跨区借权重，未分配人口保存在分区表中。缺失官方匹配或建筑位于边界外时，建筑校准人口保持空值。因已知建成年份晚于基准年而排除的建筑人数设0；未知建成年份保留并标记。仅有年份无法核实6月底是否建成，也无法确认建筑源是否覆盖2026年新增住宅。

校准系数小于0.25或大于2的分区仅作为人工复核标记，不截断系数。该标记共有2025年{a['factor_review_subzones']}个、2026年{b['factor_review_subzones']}个。2026年People's Park的原始住宅权重约28.88人，官方分区目标300人，放大系数约10.39，属于住宅建筑承载或分类需要逐栋核查的例子，不能从合计守恒推断建筑分配可靠。保留原模型的nursing_home，但单独标记机构建筑；2026年暂定分配到nursing_home为{b['allocated_to_nursing_homes']:,.3f}人。分区校准不能纠正区内错误的住宅份额、大型podium异常或建筑漏项，不能推算非居民、日间人口或特定年龄需求。

L21输出为住宅建筑所在的稀疏点表，不重新生成约3491万个空格。建筑按所属subzone校准后再汇入格；`s2l21_by_building_subzone.csv`保留格和建筑分区两个维度，避免格中心越界后失去分区守恒。`complete_2025`和`complete_2026`表示格内住宅建筑是否均有校准值，不能把含空值的部分合计解释为完整人口。

## 文件与复现

- `population_calibrated.gpkg`：EPSG3414，含建筑polygon、2025分区、2026暂定分区及住宅L21点四个图层。建筑层保留原始属性，新增住宅容量及两个年度分配字段。
- `building_population_calibrated.csv`：118782行建筑结果，source_fid与原GPKG的fid对应，id为原始建筑ID。
- `subzone_calibration_2026.csv`及`subzone_calibration_2025.csv`：官方目标、权重分母、系数、分配结果、残差和空间版本状态。
- `unallocated_or_unmatched_subzones_*.csv`、`factor_review_*.csv`：未分配人口及需要复核的分区。
- `planning_area_reconciliation_*.csv`：PA独立发布合计与subzone求和的舍入差。
- `validation_summary.json`、`input_manifest_before.json`、`input_manifest_after.json`：对账与源文件SHA256，原始输入前后完全一致。

先运行code/prepare_sources.py保存官方快照，再运行 `python3 code/calibrate_population.py --output results/runs/NEW_DIRECTORY`。每次使用新目录，脚本拒绝覆盖既有run。

## 官方来源

[SingStat Geographic Distribution 最新年度数据](https://www.singstat.gov.sg/find-data/explore-data-themes/population/geographic-distribution/latest-news-data)，2026年6月和2025年6月的Singapore Residents by Planning Area / Subzone, Single Year of Age and Sex。原始Excel、CSV ZIP、说明和下载URL及SHA256均保存在包内data/raw/population目录。居民口径为公民和永久居民；源表排除连续离开新加坡12个月或以上的居民，数值舍入至最接近的10人。

[URA Master Plan 2019 Subzone Boundary No Sea](https://data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view)。使用现有本地GeoJSON，先在内存修复无效几何。2026年结果正式使用前仍需以经核验的MP2025分区几何重新进行建筑空间归属和校准，并复核异常系数对应的建筑覆盖。
'''
    (out / '人口校准报告.md').write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()

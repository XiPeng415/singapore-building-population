"""Independent verification from saved CSV, source controls, and GeoPackage."""
import argparse
import json
import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

from project_paths import PACKAGE as BASE, SOURCES, REFERENCE

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default=str(REFERENCE))
    args = ap.parse_args()
    out = Path(args.output)
    b = pd.read_csv(out / 'building_population_calibrated.csv')
    assert len(b) == 118782 and b.source_fid.is_unique
    assert b.id.is_unique
    assert abs(b.res_pop_est_raw.sum() - 6965701.105973358) < 1e-7
    assert abs(b.loc[b.in_mainland_cell, 'res_pop_est_raw'].sum() - 6964440.179683713) < 1e-7
    controls = pd.read_csv(out / 'official_subzone_controls.csv')
    cells = pd.read_csv(out / 's2l21_residential_points.csv')
    result = {}
    con = sqlite3.connect(f'file:{out / "population_calibrated.gpkg"}?mode=ro', uri=True)
    assert con.execute('select count(*) from buildings_population').fetchone()[0] == 118782
    assert len(con.execute('select table_name from gpkg_contents').fetchall()) == 4
    for year in (2025, 2026):
        col = 'resident_pop_2025' if year == 2025 else 'resident_pop_2026_provisional'
        z = pd.read_csv(out / f'subzone_calibration_{year}.csv')
        # Re-read independently published total rows, not preprocessed controls.
        src = pd.read_excel(SOURCES / f'respopagesex{year}.xlsx', header=2)
        src = src[(src.Age == 'Total') & (src.Sex == 'Total') & src.Subzone.ne('Total')]
        txt = src[str(year)].astype(str)
        src['target'] = pd.to_numeric(txt.mask(txt.eq('-'), '0'))
        assert len(src) == 332
        key = lambda a, c: a.str.strip().str.upper() + '|' + c.str.strip().str.upper()
        src['join_key'] = key(src['Planning Area'], src.Subzone)
        check = z.merge(src[['join_key', 'target']], on='join_key', how='outer', validate='one_to_one')
        assert check.target.notna().all() and check.target_residents.notna().all()
        assert check.target.eq(check.target_residents).all()
        # Reconstruct all building estimates independently from within-zone shares.
        future = pd.to_numeric(b.built_year, errors='coerce').gt(year)
        eligible = b.res_pop_est_raw.where(~future, 0.)
        denom = eligible.groupby(b.SUBZONE_C).sum()
        targ = z.set_index('SUBZONE_C').target_residents
        expected = eligible * b.SUBZONE_C.map(targ) / b.SUBZONE_C.map(denom)
        matched = b.SUBZONE_C.isin(targ.index)
        expected.loc[matched & eligible.eq(0)] = 0.
        assert expected.isna().equals(b[col].isna())
        assert np.allclose(expected.dropna(), b.loc[expected.notna(), col], atol=1e-8, rtol=1e-12)
        sums = b.groupby('SUBZONE_C')[col].sum(min_count=1)
        check['sum_buildings'] = check.SUBZONE_C.map(sums).fillna(0.)
        supported = check.eligible_proxy.gt(0)
        err = (check.loc[supported, 'sum_buildings'] - check.loc[supported, 'target']).abs().max()
        assert err < 1e-7
        missing = check.loc[check.eligible_proxy.eq(0) & check.target.gt(0), 'target'].sum()
        assert abs(check.target.sum() - b[col].sum() - missing) < 1e-7
        assert abs(cells[col].sum() - b[col].sum()) < 1e-7
        sql_sum = con.execute(f'select sum("{col}") from buildings_population').fetchone()[0]
        assert abs(sql_sum - b[col].sum()) < 1e-5
        assert b.loc[b.res_ratio.eq(0) & matched, col].eq(0).all()
        assert b.loc[future & matched, col].eq(0).all()
        result[year] = dict(source_controls_match=True, all_building_values_match_independent_calculation=True,
            max_supported_subzone_error=float(err), unallocated_population=int(missing),
            csv_gpkg_s2_totals_match=True, nonresidential_and_known_future_buildings_zero=True)
    before = json.loads((out / 'input_manifest_before.json').read_text())
    after = json.loads((out / 'input_manifest_after.json').read_text())
    assert before == after
    result['source_inputs_unchanged'] = True
    (out / 'independent_validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()

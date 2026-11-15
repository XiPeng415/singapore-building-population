# Sources, prior research and attribution

This page records which inputs and tools are used, how the population allocation relates to prior research, and which assumptions belong to the local research implementation.

## Project and source links

- Population dataset and workflow — GitHub: [https://github.com/XiPeng415/singapore-building-population](https://github.com/XiPeng415/singapore-building-population)
- Buildings.sg — City Syntax Lab, NUS: [https://buildings.sg/](https://buildings.sg/)
- Buildings.sg upstream data repository: [https://github.com/City-Syntax/buildings.sg](https://github.com/City-Syntax/buildings.sg)
- OpenStreetMap contributors: [https://www.openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)
- SingStat — resident-population controls: [https://www.singstat.gov.sg/find-data/explore-data-themes/population/geographic-distribution/latest-news-data](https://www.singstat.gov.sg/find-data/explore-data-themes/population/geographic-distribution/latest-news-data)
- URA — MP2019 subzone boundaries: [https://data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view](https://data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view)

## Source-to-step mapping

| Source or contributor | Role in this project | Attribution status |
|---|---|---|
| **Buildings.sg v5 — City Syntax Lab, National University of Singapore (NUS)** | Building footprints, building archetypes, GFA and construction-year input attributes | Correspondence verified against the upstream v5 snapshot; see comparison below |
| **OpenStreetMap contributors** | Core building footprints/heights in the Buildings.sg data lineage | Acknowledged by Buildings.sg; OSM attribution and ODbL terms retained |
| **HDB, BCA and URA, through Buildings.sg** | Housing, certification and planning inputs in the upstream integrated inventory | Upstream credits reported by Buildings.sg; this population pipeline does not independently collect each upstream source |
| **Singapore Department of Statistics / SingStat** | Published annual resident-population control totals by planning area and subzone | Direct source workbooks for June 2025 and June 2026; download URLs and SHA256 recorded |
| **Urban Redevelopment Authority / data.gov.sg** | MP2019 subzone polygons for building centroid assignment | Direct spatial boundary input |
| **S2 Geometry and s2sphere contributors** | Spherical cell indexing for the wider workflow's S2 L21 aggregation | Software infrastructure; not the source of building-population estimates |
| **GeoPandas, Shapely, pyproj, GDAL/pyogrio, pandas, NumPy and other dependencies** | Spatial operations, reprojection, geospatial I/O, tabular calculations and figures | Open-source software; pinned package versions are in [requirements.txt](../requirements.txt) |

Buildings.sg links: [project](https://buildings.sg/), [repository](https://github.com/City-Syntax/buildings.sg), [documentation](https://city-syntax.github.io/buildings.sg/documentation.html). Population source: [SingStat Geographic Distribution](https://www.singstat.gov.sg/find-data/explore-data-themes/population/geographic-distribution/latest-news-data). Spatial source: [URA MP2019 Subzone Boundary No Sea](https://data.gov.sg/datasets/d_8594ae9ff96d0c708bc2af633048edfb/view).

## Building input correspondence

The local population input is `sg_buildings_3414.gpkg` in EPSG:3414. It was compared on 15 November 2026 with `download/sg_buildings_v5.zip` from Buildings.sg at commit `b95ccceff59386b72d3a88dfc0cd4141d5b64bc6`.

- Both inventories have **118,782 unique building IDs**, with no unmatched IDs.
- All **118,782 building archetypes, GFA values and construction-year attributes match**. The maximum GFA difference is **0 m²**.
- **118,776 footprints** have a Hausdorff distance no larger than **0.01 m** after comparison in EPSG:3414.
- Six footprints differ by more than 0.01 m, with maximum distance **13.5682 m**. All six upstream geometries are invalid and their local counterparts are valid. Their IDs and differences are retained in the comparison; this does not establish the exact historical geometry-repair procedure.

This supports crediting Buildings.sg and its contributors for the building-data backbone while recording local geometry differences. The local file's historical download date is not recorded. It is a processed input, rather than a byte-identical upstream GeoJSON. Other energy/carbon fields were outside this population-input comparison.

The [machine-readable comparison](building_source_comparison.json) records the upstream commit, archive SHA256, local input SHA256, match counts and six geometry differences. Download metadata links to this attribution record.

## Relationship to prior research

### Dasymetric mapping

**Mennis, J. (2003).** Generating Surface Models of Population Using Dasymetric Mapping. *The Professional Geographer*, **55**(1), 31–42. [DOI: 10.1111/0033-0124.10042](https://doi.org/10.1111/0033-0124.10042).

This is foundational context for using ancillary spatial information to redistribute aggregate population. The present implementation uses eligible residential GFA as the within-subzone weight. Mennis's study used land-cover information, so its particular empirical procedure is not reproduced here.

### Population estimation from building space

**Biljecki, F., Arroyo Ohori, K., Ledoux, H., Peters, R., & Stoter, J. (2016).** Population Estimation Using a 3D City Model: A Multi-Scale Country-Wide Study in the Netherlands. *PLOS ONE*, **11**(6), e0156808. [DOI: 10.1371/journal.pone.0156808](https://doi.org/10.1371/journal.pone.0156808).

The TU Delft 3D Geoinformation team's paper studies building floorspace/volume as population proxies and evaluates disaggregation and statistical estimation. It provides related methodological context. This project's Singapore implementation uses a supplied GFA attribute and subzone controls; it does not reproduce the paper's complete 3D experiments, regression model or validation results.

These papers are cited to place the implemented approach in the literature. They were added during this attribution review; the existing local scripts do not cite them or establish that the original implementation was directly adapted from either research team. No third-party population-model code has been identified in the released calibration scripts. WorldPop, GHSL and LandScan are not data inputs to this release.

## Parameter provenance

The earlier local H3/S2 population scripts contain the numerical assumptions inherited by this calibration. Their role and documented provenance are:

| Assumption | Record found in legacy code | Treatment in this release |
|---|---|---|
| Residential shares: landed 1.00; HDB 0.93; apartment 0.95; shophouse 0.45; mixed development 0.50; nursing home 1.00 | General comment referring to URA Development Control Handbooks and HDB annual statistics; no document edition, table/page or derivation for each coefficient | Inherited project assumptions, not verified official residential-share coefficients |
| 28 m²/person | Explicitly marked user-specified in the earlier H3 script; an accompanying average-space claim has no traceable reference | Local baseline assumption; cancels in normalized within-subzone allocation |
| Occupancy/utilisation 0.94 | Numerical value in the earlier scripts; no specific source citation | Local baseline assumption; cancels in normalized within-subzone allocation |
| Construction-year eligibility; retain unknown years | Implemented in this project's calibration scripts | Project processing rule |
| Review flag for calibration factor below 0.25 or above 2 | Implemented in this project's diagnostics | Project inspection threshold, not a published official standard |

The first three rows should not be attributed to Mennis, Biljecki et al., Buildings.sg or a government agency as published parameter values without an exact supporting source.

## Work performed by this project

The released workflow assembles the source inputs, applies the local residential weights, assigns buildings to subzones, allocates the annual official control totals, tracks geography versions, independently recalculates the results, and exports building/S2 outputs and research figures. Its contribution is the implemented Singapore population workflow and resulting data layer. The underlying dasymetric method family, building inventory and spatial-index libraries retain the credits above.

## Software and data notices

- [S2 Geometry](https://s2geometry.io/about/overview) and [s2sphere](https://s2sphere.readthedocs.io/en/latest/) are credited for cell indexing. The public geometry remains building footprints; S2 does not generate the underlying population weights.
- [GeoPandas](https://geopandas.org/en/stable/about.html) and the libraries in [requirements.txt](../requirements.txt) provide the processing tools.
- Building geometry includes **© OpenStreetMap contributors**, available under the [Open Database License](https://opendatacommons.org/licenses/odbl/1-0/). See [OSM attribution](https://www.openstreetmap.org/copyright).
- The Buildings.sg repository includes an MIT licence notice from City Syntax Lab, reproduced in [third-party notices](../THIRD_PARTY_NOTICES.md). That repository-level notice does not replace underlying OSM or government source-data terms.
- Government source terms are available from the linked dataset pages. No single new software licence is asserted to cover all constituent data.

[BibTeX references](../REFERENCES.bib) · [Methodology](methodology.md) · [Building-source comparison](building_source_comparison.json).

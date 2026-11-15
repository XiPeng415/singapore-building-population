# Third-party data and software notices

## Building-data attribution

Building inputs are credited to **Buildings.sg v5 — City Syntax Lab, National University of Singapore**. Source: https://github.com/City-Syntax/buildings.sg. Input correspondence and local geometry differences are recorded in [the source comparison](docs/building_source_comparison.json).

Buildings.sg identifies **OpenStreetMap contributors** as its core footprint/height source and acknowledges HDB, BCA and URA contributions to its integrated inventory.

**© OpenStreetMap contributors.** OpenStreetMap data is available under the **Open Data Commons Open Database License (ODbL)**: https://opendatacommons.org/licenses/odbl/1-0/. Attribution: https://www.openstreetmap.org/copyright. This notice preserves the upstream data credit and terms; the MIT notice below does not replace them.

## Population and boundary data

Resident-population controls: **Singapore Department of Statistics / SingStat**. Subzone assignment boundaries: **Urban Redevelopment Authority / data.gov.sg**. Source links and fixed snapshots are listed in [sources and attribution](docs/sources_and_attribution.md). Source-specific terms remain applicable.

## Buildings.sg repository licence notice

The following notice is reproduced from the upstream repository's [`LICENSE`](https://github.com/City-Syntax/buildings.sg/blob/b95ccceff59386b72d3a88dfc0cd4141d5b64bc6/LICENSE). It is the upstream repository's software/documentation notice, not a blanket replacement for constituent source-data licences.

```text
MIT License

Copyright (c) 2026 City Syntax Lab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Processing software

The workflow uses S2/s2sphere, GeoPandas, Shapely, pyproj, pyogrio/GDAL, pandas, NumPy, Matplotlib, Pillow, requests and openpyxl. Their respective authors and contributors retain their software rights. Package versions are pinned in [requirements.txt](requirements.txt); the source-to-step mapping is in [the attribution notes](docs/sources_and_attribution.md).

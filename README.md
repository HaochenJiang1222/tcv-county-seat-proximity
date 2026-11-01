# Replication package

Recognition as Eligibility: County-Seat Proximity and Access to Conservation Support Arrangements in China's Traditional Villages (manuscript v1.6)

Yue Yu (Jiangsu Open University), Haochen Jiang (Jiangsu Open University, corresponding author)

This package contains everything needed to reproduce every number reported in the manuscript, except the
village coordinates, which must be obtained from their original source (see below).

## Contents

| Directory | Contents |
|---|---|
| `scripts/` | All construction, matching, adjudication, variable, estimation, diagnostic, verification and typesetting scripts of the traditional-village branch (numbered 100 and above; lettered variants such as `123b` follow their parent number). Run order follows the numbers. |
| `data/` | Coordinate-free derived datasets, except `county_center_points_public.csv`, which holds public administrative reference points. `analysis_input_public.csv` is the direct input to the main estimation scripts; `village_records_public.csv` carries every village's administrative name, status and match rule; the remaining files carry the geographic variables, boundary audit, county-level descriptives, the county-seat point definitions used for the reference-point check in Section 4.1, and the adjudication and provenance registers. |
| `output/` | Frozen result logs (bootstrap replications use SEED 20261030) and the two manuscript figures. |
| `MANIFEST.csv` | Size and SHA-256 checksum of every packaged file. |
| `.zenodo.json`, `CITATION.cff` | Archival metadata. Placeholders in `CITATION.cff` are replaced when the repository is published. |
| `PACKAGING.md` | States exactly how the package was assembled, including the five portability edits applied to the scripts. |

## What is deliberately not included

Village coordinates come from *Spatial Distribution Dataset of 1,598 Newly Added Traditional Villages in China*
(DOI 10.3974/geodb.2019.01.19.V1). The publisher's terms require citation of the original source and restrict
redistribution, so the coordinates are not republished here. To recompute the geographical variables, obtain
that dataset, place it at `data/geo/geodoi/points1598.csv` (and `points2555.csv` for the first three cohorts),
then run, in this order:

```
python scripts/123_county_center_national.py
python scripts/123b_elevation_national.py
python scripts/123c_dist_county_national.py
python scripts/125_geo_audit_national.py
python scripts/136_build_exposure_v3.py
```

On completion the analysis input is regenerated with coordinates attached. Every downstream script reads
column names only, so nothing else changes.

Two public endpoints are queried by those scripts and require no credentials:

* DataV.GeoAtlas administrative boundaries, `https://geo.datav.aliyun.com/areas_v3/bound/{adcode}_full.json`
* OpenTopoData elevation API, `https://api.opentopodata.org/v1/srtm30m` (and `/v1/aster30m` for the cross-check)

The scripts that assembled the 2016 roster and the 2017 support lists read local copies of public web pages.
Those pages are registered with sizes and checksums in `data/source_provenance.csv` so that any future reader
can compare what was parsed against what is retrievable.

## Environment

Python 3.13 with `numpy`, `statsmodels`, `matplotlib`, `olefile`. No other dependency is used by the scripts
that produce reported numbers; `python-docx` is used only by the typesetting scripts. Scripts resolve their
root from `__file__`, so they can be run from any location; no path needs editing.

## Reproducing the headline results

```
python scripts/137_national_main_v3.py 800      # Table 2 Panels A-B, Tables 3-4 base results
python scripts/139_two_checks.py                # full-sample and informative-county LPM, size interaction
python scripts/138_county_table.py              # county-level descriptives behind Figure 2
python scripts/147_adjudicate_pending3.py       # audit of the three remaining announcement entries
python scripts/148_pending3_sensitivity.py      # bounded misclassification check reported in Section 4.1
python scripts/149_source_provenance.py         # checksums and provenance of every parsed source file
python scripts/152_county_center_audit.py       # seat vs centroid vs recomputed polygon centroid
python scripts/153_center_definition_check.py   # seat comparison and the reference-point bounded check
python scripts/151_verify_v14.py v1.6           # re-verifies every reported number against these logs
python scripts/142_check_manuscript.py          # re-verifies manuscript numbers against these logs
python scripts/141_figures_v1.py                # regenerates both figures
```

Run them from the directory containing `scripts/`, `data/` and `output/`.

## Licence

Scripts are released under the MIT licence. Derived datasets in `data/` and the logs and figures in `output/`
are released under CC BY 4.0. The village coordinates are not included and are governed by the terms of the
original publisher.

Package assembled 2026-11-01.

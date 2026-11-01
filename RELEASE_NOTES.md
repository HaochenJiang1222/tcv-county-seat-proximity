# Release notes, version 1.0.1

Release date: 2026-11-02

This release is the code state cited in the Data Availability Statement of the submitted
manuscript. It supersedes v1.0.0 for citation.

## Changes in v1.0.1

* Updated the two manuscript figures (`output/figures/fig1_flow.png`,
  `output/figures/fig2_county_diff.png`) to the layout used in the submitted manuscript:
  text overflow fixed, in-figure captions removed per MDPI style (captions are typeset
  in the manuscript), the reference point renamed to the county government seat, and the
  boundary note aligned with the manuscript wording. No data, estimate, seed or script
  changed; recomputing the figures reproduces the same 42 negative / 11 tied / 42 positive
  counties and mean -0.039.
* `CITATION.cff` version bumped to 1.0.1.
* `MANIFEST.csv` checksums refreshed.

---

# Version 1.0.0

Release date: 2026-11-01

This is the first release that passes the reproducibility audit reported in Appendix A.8 of the
manuscript. It is the code state cited in the Data Availability Statement.

## What is in this release

* All construction, matching, adjudication, variable, estimation, diagnostic, verification and
  typesetting scripts of the traditional-village branch.
* Coordinate-free derived datasets sufficient to reproduce every number reported in the paper.
* Frozen result logs and the two manuscript figures.
* Adjudication and source-provenance registers.
* `MANIFEST.csv` with a SHA-256 checksum for every packaged file.

## What is not in this release, and why

Village coordinates originate from *Spatial Distribution Dataset of 1,598 Newly Added Traditional
Villages in China* (DOI 10.3974/geodb.2019.01.19.V1). The publisher's terms restrict redistribution,
so the coordinates are withheld. Obtaining that dataset and running
`scripts/123_county_center_national.py`, `scripts/123b_elevation_national.py`,
`scripts/123c_dist_county_national.py`, `scripts/125_geo_audit_national.py` and
`scripts/136_build_exposure_v3.py` in that order regenerates every geographical variable exactly.

## Verification status at release

* `142_check_manuscript.py` — content checks, all passing.
* `151_verify_v14.py v1.6` — number and disclosure checks, all passing.
* Bootstrap replications use fixed seed 20261030; replication counts are reported with each result.

## Known limits

* Three announcement entries remain classified as pending rather than matched; the bounded
  misclassification check in `scripts/148_pending3_sensitivity.py` reports both boundaries.
* The county-seat proximity result is conditioned on within-county variation; the full-sample and
  county-weighted results are reported alongside it and do not reach conventional significance.
  The reference-point check using geometric centroids does not reject a null association.
* County administrative reference points in `data/county_center_points_public.csv` mirror a public
  administrative-boundary service; readers who prefer not to rely on the redistributed copy can
  regenerate them with `scripts/123_county_center_national.py`.


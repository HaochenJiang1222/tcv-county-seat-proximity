# How this package was assembled

The package is assembled from the authors' working tree by an internal script that is not itself
published, because it references local directories. The rules it applies are reproduced here so the
package can be audited without it.

1. **Scripts.** Every `.py` file in the working script directory whose name begins with a number of
   100 or above is copied to `scripts/` unchanged. The numeric prefix includes lettered variants, so
   `123b_elevation_national.py` and `123c_dist_county_national.py` are included alongside
   `123_county_center_national.py`. Scripts numbered below 100 belong to a separate paper and are
   excluded.
2. **Derived data.** Each derived dataset is copied to `data/` after removing any column named
   `lat`, `lon`, `latitude` or `longitude`. The only packaged file that still carries coordinates is
   `county_center_points_public.csv`: those are public administrative reference points (county
   government seats and polygon centroids), not the restricted village coordinates. Readers who
   prefer not to rely on the redistributed copy can regenerate them with
   `scripts/123_county_center_national.py`.
3. **Outputs.** Frozen result logs and the two figures are copied to `output/` unchanged.
4. **Manifest.** `MANIFEST.csv` records the byte size and SHA-256 checksum of every packaged file,
   together with the path of the working-tree file it came from.
5. **Portability.** Five scripts originally resolved their working directory either from a hardcoded
   local path or by splitting the path on the working directory's name. Both forms break outside the
   authors' machine; they were changed to resolve the root from `__file__`, which is behaviourally
   identical in the working tree and portable in the package. No other script was edited.

Nothing in this package has been altered to change a reported result.

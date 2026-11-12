# Reference values

`snapshot.json` holds counts recounted straight from the SBTi workbooks by `tests/independent_recount.py`. That script reads the workbooks with `openpyxl` and plain Python and imports nothing from the `climate_targets` package, so the tests compare the pipeline against a second, separate calculation.

The file contains the SHA-256 of each workbook it was recounted from, headline counts, and company counts, validated near-term counts and validated net-zero counts for every location, sector and organisation type.

If the workbooks in `data/raw/` change, the snapshot tests fail with a message asking for the differences to be reviewed. To regenerate the file after reviewing the differences, run `python tests/independent_recount.py`.

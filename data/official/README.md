# Official Challenge Dataset

Place the official TIAA x ASU AI Investment Spark Challenge CSV file(s) in this directory.

## Usage

1. Download the official challenge CSV from the competition portal.
2. Copy the file(s) to this directory: `data/official/<filename>.csv`
3. The `fiducia.dataset_adapter` module will automatically discover and load all `*.csv` files
   in this directory, mapping column names via `config/dataset_mapping.json`.

## Column mapping

See `config/dataset_mapping.json` for the complete column-name-to-internal-field mapping.

## Notes

- Blank cells are preserved as `None` (never coerced to zero). This is intentional per
  the `blank_is_not_zero` policy.
- Any unmapped required fields will route the fund through `data_repair` and ultimately
  fail-closed if unresolvable.
- This directory is git-ignored (except for this README). Do not commit real fund data.

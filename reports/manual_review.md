## Manual review

Reviewed from screenshots of the running Streamlit app at 1600 pixels wide.

- Overview: the four cards, both bar charts, the paired-dot chart, the findings panel and the data checks table render. Card values and the Japan, United Kingdom and United States counts and shares agree with the independent recount. Axis titles and legends are present and labels do not overlap.
- Company and target explorer: the company and record tables show their row counts and both download buttons are present.
- Data quality and methodology: the tables, source file hashes and dates render.
- CSV downloads are verified by the browser test, which parses the downloaded file, and were not opened in a spreadsheet application.
- A narrow window was checked for horizontal overflow only.

## Reproduction

I created a new virtual environment, installed `requirements.txt` (pandas 2.3.3, openpyxl 3.1.5, plotly 7.1.0, streamlit 1.65.0) and `pip install -e ".[dev]"`, deleted `data/processed/*.csv` and the generated reports, and ran `python scripts/write_verification.py --browser` with that environment. The raw workbooks stayed in `data/raw/`. The run was on the development machine.

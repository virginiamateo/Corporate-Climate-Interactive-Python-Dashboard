# Data

This folder holds the SBTi source workbooks and the cleaned files built from them. Neither is committed to the repository (see Licence).

## Sources

All files come from the Science Based Targets initiative (SBTi) Target Dashboard: https://sciencebasedtargets.org/target-dashboard

| File | Download link |
|---|---|
| `companies-excel.xlsx` | https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx |
| `targets-excel.xlsx` | https://files.sciencebasedtargets.org/production/files/targets-excel.xlsx |
| `Alpha-Dashboard-Data-Dictionary.xlsx` | https://files.sciencebasedtargets.org/production/files/Alpha-Dashboard-Data-Dictionary.xlsx |

The SHA-256 values of the files used for this project:

```text
e5c81f5da06e622c4bd0e0a797b3d8348a5c73fcb775a070a15cb19ab742afaa  companies-excel.xlsx
f14f0661d4bdea302fafc2cf33aa11f48e8e105319ea0fd7a96fb4a404c5d309  targets-excel.xlsx
b50ea0fd52b817b2ce85de1e2ab96598e5c39ce5f8be0b320ba9175ef6af2280  Alpha-Dashboard-Data-Dictionary.xlsx
```

SBTi updates these files at the same addresses. A later download may have different hashes and different counts.

## Layout

- `raw/` holds the three workbooks exactly as downloaded. They are never edited.
- `processed/` holds `companies.csv` and `targets.csv`, generated from `raw/` by the build script. They are never edited by hand.

## Reproducing the data

From the repository root:

```bash
cd data/raw
curl -O https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx
curl -O https://files.sciencebasedtargets.org/production/files/targets-excel.xlsx
curl -O https://files.sciencebasedtargets.org/production/files/Alpha-Dashboard-Data-Dictionary.xlsx
```

## Licence and attribution

The SBTi Website Terms of Use (https://sciencebasedtargets.org/about-us/website-terms-of-use) allow content to be stored "for research, your personal use, or other non-commercial use", provided the Science Based Targets initiative is credited as the source with a link to the relevant page. The terms do not mention datasets and do not address redistribution. For uses they do not expressly permit, they direct readers to info@sciencebasedtargets.org.

For that reason the original workbooks and the cleaned CSV files are excluded from Git through `.gitignore`. The repository contains the code, the method, aggregate results and screenshots, each attributed to SBTi.

Source: Science Based Targets initiative, Target Dashboard, https://sciencebasedtargets.org/target-dashboard

## Limitations of the data

- The directory is voluntary. It describes companies that chose to register, not all companies in a sector or country.
- A validated target is a status assigned by SBTi. It does not show that emissions have fallen.
- The `location` field contains countries, territories and other geographic designations, so it is not a list of sovereign states.
- A blank `net_zero_status` means no status is recorded.

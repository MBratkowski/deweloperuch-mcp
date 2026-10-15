# Project statistics

Written once a day by the `stats` workflow (`.github/workflows/stats.yml` and
`.github/scripts/archive_stats.py` on `main`); do not edit by hand. GitHub keeps a
repository's traffic for 14 days and pypistats.org daily downloads for about 180 days;
this branch keeps them.

All dates are UTC (`YYYY-MM-DD`); rows are sorted by their first columns. A file with a
`captured` column gets that day's capture on every run, and a rerun on the same day
replaces it. In the other files a later run replaces the rows of the dates it fetched
again (the latest day is partial until then) and keeps the older ones.

| File | Columns | Holds |
|---|---|---|
| `github/views.csv` | `date,count,uniques` | Views of the repository's pages per day (all, unique visitors). |
| `github/clones.csv` | `date,count,uniques` | Clones of the repository per day (all, unique cloners). |
| `github/referrers.csv` | `captured,referrer,count,uniques` | The sites that sent the most visitors in the 14 days up to `captured`. |
| `github/paths.csv` | `captured,path,title,count,uniques` | The most viewed pages of the repository in the 14 days up to `captured`. |
| `github/releases.csv` | `captured,tag,asset,download_count` | Downloads of each asset of each published release since its upload, as of `captured`. |
| `github/repo.csv` | `captured,stars,forks,watchers` | The repository's stars, forks and watchers as of `captured`. |
| `pypi/downloads.csv` | `date,category,downloads` | Downloads of the PyPI package per day, `with_mirrors` and `without_mirrors` (pypistats.org). |

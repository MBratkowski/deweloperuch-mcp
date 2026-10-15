# GitHub and PyPI statistics responses

Responses of the APIs that `.github/scripts/archive_stats.py` (the daily `stats` workflow) reads, for its offline tests (`tests/repo_stats/`). None of them comes from deweloperuch.pl.

| File | Request | Response |
|---|---|---|
| `views.json` | `GET api.github.com/repos/MBratkowski/deweloperuch-mcp/traffic/views` | 200, `{count, uniques, views ×14}`, days 2026-10-01 to 2026-10-14, all 0 but the last (92 views, 40 unique) |
| `clones.json` | `GET …/traffic/clones` | 200, `{count, uniques, clones ×14}`, the same days, all 0 but the last (103, 46) |
| `referrers.json` | `GET …/traffic/popular/referrers` | 200, 3 referrers |
| `paths.json` | `GET …/traffic/popular/paths` | 200, 10 paths |
| `releases.json` | `GET …/releases?per_page=100` | 200, 2 releases (v0.1.1 with 4 assets, v0.1.0 with 3), none a draft |
| `repo.json` | `GET …/repos/MBratkowski/deweloperuch-mcp` | 200; 16 stars, 0 forks, 1 subscriber. Trimmed: see below |
| `pypistats_overall.json` | `GET pypistats.org/api/packages/deweloperuch-mcp/overall` | 200, one day (2026-10-14, the day of the first upload): 260 `with_mirrors`, 110 `without_mirrors` |
| `views_401.json` | `GET …/traffic/views` without a token | 401 `Unauthorized`, `{message: "Requires authentication", …}`; GitHub sent CRLF line endings, stored with LF |

## Provenance

- Captured on 2026-10-15 around 17:44 UTC: the GitHub ones with `gh api` and the maintainer's credentials (`views_401.json` with Python's `urllib` and no token), the PyPI one with Python's `urllib`. One request per file.
- Byte-exact bodies, with two exceptions. `views_401.json` has LF line endings instead of the CRLF GitHub sent (git stores text with LF here). From `repo.json` three top-level fields were removed and the rest re-serialized compactly, keys in their order:
  - `permissions`: the requesting account's access (`admin`, `maintain`, `push`, `triage`, `pull`, all `true`);
  - `security_and_analysis`: the repository's security settings (secret scanning, push protection, Dependabot updates), shown to administrators;
  - `temp_clone_token`: an empty string in this response, removed because it is a token field.
- The remaining fields of `repo.json` are the public repository object plus the merge settings GitHub returns to accounts with push access (`allow_auto_merge`, `allow_merge_commit`, `allow_rebase_merge`, `allow_squash_merge`, `allow_update_branch`, `delete_branch_on_merge`, `merge_commit_message`, `merge_commit_title`, `squash_merge_commit_message`, `squash_merge_commit_title`, `use_squash_pr_title_as_default`), found by comparing with an anonymous request on the same day. None of them is a secret.
- Content: aggregate counters, public release metadata and public paths of the repository. No personal data, so nothing was replaced.

## Rules

- Never edit or overwrite a file. A new observation is a new file, described in the table above with its source and date.

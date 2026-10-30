# EDXSO AI Engineer Intern — Assignment 1

This workspace now runs offline from a local 50-record demo fixture. To preserve
the assignment's data-quality requirements, **all records are explicitly
synthetic**: names, handles, profile footprints, content themes, follower counts,
and engagement rates are invented test data. `.invalid` profile URLs and blank
emails prevent the demo from being mistaken for verified creator data or used
for real outreach. Do not submit the synthetic fixture as a real influencer
dataset.

## Run locally

Requirements: Python 3.9+. The local workflow uses only the Python standard
library and does not call YouTube or other discovery endpoints.

```powershell
python main.py
```

By default, message personalization uses the local content-aware generator and
requires no network or API key. To opt in to Gemini-generated copy, set
`GEMINI_API_KEY` in the environment. The key is read only with
`os.getenv("GEMINI_API_KEY")`; never paste it into source code. Gemini calls
require network access. The response is rejected if it is malformed or fails
the 60–90 word email and 15–30 word DM requirements.

Optionally set `MIN_ENGAGEMENT_RATE` (for example `1.0` means 1%) to apply an
engagement floor as an additional qualification condition.

## Workflow

1. **Local data:** `config.py` provides exactly 50 synthetic profile objects
   across Fashion & Beauty and Technology. The Fashion & Beauty criteria are the
   active filter; technology creators are retained in the output as failed
   records with a reason.
2. **Filtering:** Fashion & Beauty content and a follower count from 5,000 to
   100,000 (inclusive) are required to pass. Optional engagement floor is also
   enforced when configured. Every record receives a status and explanation.
3. **Enrichment:** Fixture fields include platform, profile URL, follower count,
   engagement rate, niche, content themes, recent content, and contact email.
   Emails are blank and normalized to `Not Found`; demographic and website
   fields unavailable in the fixtures are reported as `Not Found`.
4. **Personalization:** Local copy uses profile name, niche, and recent-content
   themes. Optional Gemini uses the same observed signals. Both outputs are
   validated against required message lengths.
5. **Sending/tracking:** No email or DM is sent. With all fixture emails missing,
   qualified records are logged as skipped. The CSV tracker persists across
   runs and prevents duplicate profile URLs.

## Outputs

- `influencer_dataset.csv`: all 50 synthetic profiles with enrichment and
  pass/fail reasons.
- `personalized_messages.csv`: generated email pitches and Instagram DMs for
  qualified demo profiles, including synthetic-data markers.
- `outreach_tracker.csv`: simulated delivery status and timestamps, including
  synthetic-data markers.

All three files are generated or updated by `python main.py`.

## Moving to real data

The local mode solves the unavailable Google Cloud billing setup for workflow
development and testing, but it does not meet the assignment's real-data
submission requirement. Before using this for outreach or submission, replace
the fixture with profiles collected from permitted sources, verify profile
metrics and contact details, cite their provenance, and keep unavailable email
addresses as `Not Found`. Do not treat generated demo data as real creator
information.

## Tests

```powershell
python -m unittest discover -s tests
```

# Incidents

Post-mortems for failures that affected production. One folder per incident.

## Layout

```
incidents/
└── YYYY-MM-DD-<slug>/
    ├── incident.md            (the write-up — required)
    └── (optional: logs/, screenshots/, transcripts/)
```

## Naming

- Folder: `YYYY-MM-DD-<slug>` where the date is when the incident *occurred* (not when the write-up was finished).
- Slug: lowercase-kebab, short, descriptive.
- File: `incident.md` (uniform across all incidents).

## Suggested `incident.md` structure

```markdown
# <Short title>

- Date: YYYY-MM-DD
- Severity: <impact summary>
- Surface: <where it appeared — service, endpoint, agent>
- Status: open | mitigated | resolved

## Summary
1–3 sentence executive summary.

## Timeline
What happened, with timestamps.

## Root cause
What broke and why.

## Remediation
What was done to mitigate / fix.

## Prevention
Follow-up work to make recurrence less likely (link to PRs / issues).
```

## Sanitize before committing

Real runtime ARNs, account IDs, internal IPs, bucket names, session / upload IDs, and customer brand references should be redacted. See [../CONVENTIONS.md](../CONVENTIONS.md#sensitive-data-in-docs).

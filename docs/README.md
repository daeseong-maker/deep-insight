# Docs

Documentation for the Deep Insight project. Filed by *type*: features, incidents, and process.

## Layout

```
docs/
├── features/    Per-feature design and planning. One folder per feature.
├── incidents/   Post-mortems, one folder per incident (YYYY-MM-DD-<slug>/incident.md).
└── process/     Cross-cutting process docs (release management, contribution guides).
```

## Where do new docs go?

```
Is it a post-mortem of something that already broke?      → incidents/YYYY-MM-DD-<slug>/incident.md
Is it a release / versioning / contribution process doc?  → process/<slug>.md
Is it about an existing or planned feature?               → features/<feature-slug>/...
Otherwise — propose a new top-level bucket in CONVENTIONS.md before adding.
```

## Starting a new feature

1. `cp -r features/_template features/<feature-slug>`
2. Fill in `README.md`. Delete chapter files you don't need yet; add them as the design grows.

Naming, frontmatter, and the "regroup at 12 features" rule are in [CONVENTIONS.md](./CONVENTIONS.md).

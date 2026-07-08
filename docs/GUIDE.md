# Documentation Guide

## Directory Structure

```text
docs/
  README.md
  GUIDE.md
  00-reference/
  01-architecture/
  02-requirements/
  03-protocols/
  04-planning/
  05-execution/
  06-testing/
  07-debugging/
  08-reports/
  09-backlog/
  10-learning/
  superpowers/
```

## Naming Rules

- Use ASCII paths: `NN-english-kebab`.
- Use Chinese, English, or bilingual titles inside the Markdown file, not in the path.
- Use `00-guide.md` as the category guide inside each directory.
- Use `01-...md` and higher numbers for real project documents.
- Keep old or speculative material out of the public entry path unless it has been reviewed.

## Documentation Status Rules

Every project-facing document must make its evidence boundary clear:

- `Implemented`: code exists and builds.
- `Verified`: code has fresh test, build, or hardware evidence.
- `Blocked`: external hardware, toolchain, or decision is required.
- `Deferred`: intentionally moved to a later stage.

Do not describe hardware behavior as verified unless there is board evidence.

## Promotion Rule

The repository tracks the clean documentation skeleton and the active roadmap/backlog.
Large raw references and historical notes can stay local or ignored until they are curated into one of the public directories.

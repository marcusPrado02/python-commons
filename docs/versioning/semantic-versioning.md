# Semantic Versioning

`mp-commons` follows [Semantic Versioning 2.0.0](https://semver.org/).

---

## Version Format

```
MAJOR.MINOR.PATCH[-prerelease][+build]
```

| Component | Meaning |
|---|---|
| `MAJOR` | Incompatible API change |
| `MINOR` | New backward-compatible functionality |
| `PATCH` | Backward-compatible bug fix |
| `prerelease` | `alpha.N`, `beta.N`, `rc.N` |

## What Counts as a Breaking Change (MAJOR bump)

- Removing or renaming a public symbol (class, function, constant)
- Changing the signature of a public method in an incompatible way
- Removing an optional parameter without a deprecation cycle
- Changing the behaviour of an existing method in a semantically
  incompatible way
- Dropping Python version support

## What Counts as a New Feature (MINOR bump)

- New public modules, classes, or functions
- New optional parameters with default values
- New extras / adapters
- New optional behaviours toggled by flags

## Deprecation Policy

1. Deprecated symbols are marked with `warnings.warn(..., DeprecationWarning)`
   and documented in `CHANGELOG.md`.
2. A deprecated symbol lives for **at least one MINOR release** before removal
   in a MAJOR release.
3. `CHANGELOG.md` must list the release in which removal is planned.

## Release Checklist

1. Update `version` in `pyproject.toml` and `src/mp_commons/__init__.py`.
2. Add a section to `CHANGELOG.md` with date and changes.
3. Tag the commit: `git tag v1.2.3`.
4. Push — CI publishes to PyPI automatically on semver tags.

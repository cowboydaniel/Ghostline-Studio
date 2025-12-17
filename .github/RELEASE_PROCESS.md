# Release Process

This project has automated release workflows that create GitHub releases automatically.

## Two Release Workflows

### 1. **Tag-Based Release** (Recommended) - `release.yml`

Triggers when you push a **git tag** matching the pattern `v*` (e.g., `v0.1.0`).

**Usage:**
```bash
# Update the version in pyproject.toml
vim pyproject.toml
# Change: version = "0.1.0"

# Commit the change
git add pyproject.toml
git commit -m "Bump version to 0.1.0"

# Create and push a git tag
git tag -a v0.1.0 -m "Release version 0.1.0"
git push origin v0.1.0
```

The workflow will:
- ✅ Read the version from the tag
- ✅ Extract release notes from `CHANGELOG.md`
- ✅ Create a GitHub Release with release notes
- ✅ Fallback to commit message if CHANGELOG entry doesn't exist

**Advantages:**
- Clean separation between commits and releases
- Explicit control over when releases happen
- Multiple commits can be grouped into one release
- Standard Git workflow

---

### 2. **Commit-Based Release** (Alternative) - `release-on-commit.yml`

Triggers on **every commit** to `main`/`master` (if Python files or `pyproject.toml` changes).

**Usage:**
```bash
# Update version in pyproject.toml
vim pyproject.toml
# Change: version = "0.2.0"

# Commit and push
git add pyproject.toml
git commit -m "Bump version to 0.2.0"
git push origin main
```

The workflow will:
- ✅ Read version from `pyproject.toml`
- ✅ Check if release already exists (avoid duplicates)
- ✅ Create a git tag automatically
- ✅ Create a GitHub Release
- ✅ Use CHANGELOG.md for release notes (if available)

**Advantages:**
- Automatic release on every commit
- No manual tag creation needed
- Simpler workflow for frequent releases

---

## CHANGELOG Format

For both workflows to extract release notes automatically, maintain a `CHANGELOG.md` following this format:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-12-17

### Added
- Initial release of Ghostline Studio
- Local account authentication system
- Usage statistics tracking
- Quick settings panel
- Update checker with GitHub API integration
- Documentation viewer
- Community and Changelog dialogs
- Diagnostics exporter with sensitive data redaction

### Fixed
- Network error handling for update checker

### Changed
- Improved error messages for offline scenarios

## [0.0.1] - 2025-12-01

### Added
- Project initialization
```

---

## Which Workflow to Use?

Choose based on your release strategy:

| Scenario | Workflow | Command |
|----------|----------|---------|
| Stable releases with controlled versioning | `release.yml` (tag-based) | `git tag -a v0.1.0` |
| Continuous delivery / frequent releases | `release-on-commit.yml` | Update `pyproject.toml` |
| Both scenarios | Keep both enabled | They don't conflict |

**Recommended:** Use **`release.yml`** (tag-based) for clear version control and explicit release management.

---

## GitHub Token

Both workflows use `GITHUB_TOKEN` (provided by GitHub Actions automatically) to create releases. No additional configuration needed.

## Disabling Workflows

To disable automatic releases, either:
1. Delete or rename the `.github/workflows/release*.yml` files, or
2. Add `[skip ci]` to your commit message (note: GitHub Actions doesn't respect this by default)

---

## Examples

### Example 1: Using Tag-Based Release

```bash
# Work on features
git add .
git commit -m "Add new feature X"
git push

# When ready to release:
# 1. Update version
sed -i 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml

# 2. Update CHANGELOG
vim CHANGELOG.md
# Add new [0.2.0] section

# 3. Commit version bump
git add pyproject.toml CHANGELOG.md
git commit -m "Bump version to 0.2.0"
git push

# 4. Create release (triggers workflow)
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# GitHub Actions automatically creates the release!
```

### Example 2: Using Commit-Based Release

```bash
# Update version and commit
sed -i 's/version = "0.1.0"/version = "0.2.0"/' pyproject.toml
git add pyproject.toml
git commit -m "Bump version to 0.2.0"
git push origin main

# GitHub Actions automatically creates the release!
```

---

## Troubleshooting

**Release wasn't created?**
- Check `.github/workflows/` files exist
- Verify tag/commit matches trigger pattern
- Check GitHub Actions log: Settings → Actions → Workflow runs
- Ensure `CHANGELOG.md` or commit message exists

**Multiple releases created?**
- Both workflows might be enabled. Choose one or rename the other.
- Or disable one workflow temporarily.

**Release notes are empty?**
- Add release notes to `CHANGELOG.md` in the correct format
- Or ensure commit message is descriptive

---

## Next Steps

1. **Choose your workflow** (recommend: tag-based)
2. **Update version** in `pyproject.toml`
3. **Update CHANGELOG.md** with release notes
4. **Push tag** (tag-based) or **commit** (commit-based)
5. **GitHub Actions creates release automatically** ✨

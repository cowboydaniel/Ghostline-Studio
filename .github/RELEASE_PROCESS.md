# Automatic Release Process

This project uses **fully automatic releases** with `auto-release.yml`.

## How It Works

Every time you **push a commit to `main`**, the workflow automatically:

1. ✅ Calculates the next version (auto-increments patch version)
2. ✅ Creates a git tag with the new version
3. ✅ Creates a GitHub Release with commit details
4. ✅ Uses your commit message as release notes

**That's it!** No manual steps, no file updates, no tags to create.

---

## Usage - Just Commit and Push!

```bash
# Make your changes
git add .
git commit -m "Add new feature X"

# Push to main
git push origin main

# 🚀 GitHub Actions automatically creates a release!
```

---

## Release Notes

Release notes come from your **commit message**:

```bash
git commit -m "Add new feature X

This is a longer description that will appear in the release notes.
- Feature added
- Bug fixed
- Improvement made"

git push origin main
# Release is created with your commit message as the release body!
```

---

## Version Numbering

The workflow automatically:
- Fetches the latest release version (e.g., `v1.2.3`)
- Increments the patch version → `v1.2.4`
- Pushes the new tag and creates a release

**First release:** If there are no previous releases, it starts with `v0.0.1`.

---

## Release Details

Each release includes:
- ✅ Commit message as release notes
- ✅ Commit SHA (short hash)
- ✅ Author name
- ✅ Download links
- ✅ Comparison links (what changed since last release)

---

## Examples

### Example 1: Simple commit

```bash
git commit -m "Fix typo in menu"
git push origin main
# Creates release v0.0.1 with "Fix typo in menu" as release notes
```

### Example 2: Multi-line commit

```bash
git commit -m "Implement quick settings panel

- Add theme selector
- Add font size control
- Add autosave settings
- Apply changes in real-time"

git push origin main
# Creates release with full description as release notes
```

### Example 3: Continuous commits

```bash
git commit -m "Add feature A"
git push  # Release v0.0.1 created

git commit -m "Fix bug in A"
git push  # Release v0.0.2 created

git commit -m "Add feature B"
git push  # Release v0.0.3 created
```

---

## No Manual Actions Required!

| What NOT to do | Why |
|---|---|
| Don't create git tags manually | Workflow creates them automatically |
| Don't update version files | Workflow manages versions |
| Don't update CHANGELOG | Use commit messages instead |
| Don't manage releases manually | Workflow does it all |

---

## Disabling Auto-Release

To temporarily disable auto-releases:

**Option 1:** Rename the workflow file
```bash
mv .github/workflows/auto-release.yml .github/workflows/auto-release.yml.disabled
```

**Option 2:** Delete the workflow
```bash
rm .github/workflows/auto-release.yml
```

**Option 3:** Disable in GitHub UI
- Go to Settings → Actions → Disable for this repository

---

## Viewing Releases

Releases appear automatically on:
- **GitHub:** https://github.com/cowboydaniel/Ghostline-Studio/releases
- **GitHub Actions:** Settings → Actions → Workflow runs

---

## Troubleshooting

**No release created?**
- Check that you pushed to `main` (not another branch)
- Check GitHub Actions: Settings → Actions → Workflow runs
- Verify the workflow file exists: `.github/workflows/auto-release.yml`

**Release with wrong version?**
- The workflow auto-increments from the latest GitHub release
- Check https://github.com/cowboydaniel/Ghostline-Studio/releases for current version

**Want to skip a commit?**
- Use `[skip ci]` in commit message (note: GitHub Actions doesn't respect this by default, but you can modify the workflow if needed)

---

## That's All!

Just commit and push to main. Releases happen automatically. 🚀

---

## GitHub Token

The workflow uses `GITHUB_TOKEN` (provided by GitHub Actions automatically) to create releases. No additional configuration needed.

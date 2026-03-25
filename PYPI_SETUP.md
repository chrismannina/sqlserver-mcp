# PyPI Publishing Setup

One-time setup to publish sqlserver-mcp to PyPI. After this, every GitHub release auto-publishes.

## 1. Create a PyPI account

Go to https://pypi.org/account/register/ and sign up (if you don't have one).

## 2. Add trusted publisher on PyPI

Go to https://pypi.org/manage/account/publishing/ and add a "pending publisher":

- **PyPI project name**: `sqlserver-mcp`
- **Owner**: `chrismannina`
- **Repository**: `sqlserver-mcp`
- **Workflow name**: `publish.yml`
- **Environment**: *(leave blank)*

This lets the GitHub Actions workflow publish without an API token.

## 3. Create a release to trigger publish

```bash
cd ~/workspace/work/repos/sqlserver-mcp
git tag v0.2.0
git push origin v0.2.0
gh release create v0.2.0 --title "v0.2.0" --notes "Initial PyPI release"
```

The publish workflow runs automatically on release creation.

## 4. Verify

After the workflow completes (~1-2 min), check https://pypi.org/project/sqlserver-mcp/

Teammates can then install with:

```bash
uv tool install sqlserver-mcp
```

## Future releases

Bump the version in `pyproject.toml` and `src/sqlserver_mcp/__init__.py`, commit, then:

```bash
git tag v0.3.0
git push origin v0.3.0
gh release create v0.3.0 --title "v0.3.0" --generate-notes
```

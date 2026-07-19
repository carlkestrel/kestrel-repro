# R1 Path Audit

R1 enforces **zero hard-coded absolute paths and zero cwd dependence**
for test infrastructure and runtime data location. This audit lists
the mechanisms that achieve it.

## Mechanism 1: `scripts/fixture_locator.py`

Every consumer of `fixtures/`, `templates/`, `commands/`, `agents/`,
`skills/`, `rules/` should import:

```python
from scripts.fixture_locator import data_root, fixture_path, list_fixtures
```

These resolve via `importlib.resources.files("scripts.<kind>")`,
falling back to filesystem siblings of the installed `scripts/`
package, and finally to source-tree ancestors. They never look at
`Path(__file__)` for the user-writable source tree.

## Mechanism 2: `tests/conftest.py`

```python
@pytest.fixture(scope="session")
def plugin_root() -> Path | None: ...
@pytest.fixture(scope="session")
def fixtures_dir(): ...
```

No `sys.path.insert`, no absolute path. The session-scoped `plugin_root`
fixture walks up from `importlib.util.find_spec("scripts").origin`
to find the on-disk checkout. When running from a wheel install
without source tree, it returns `None` and tests that need the source
tree should skip.

## Mechanism 3: `pyproject.toml` package-data

Data directories are now `scripts.commands`, `scripts.agents`,
`scripts.skills`, `scripts.rules`, `scripts.templates`,
`scripts.fixtures` Python marker packages whose `package-data` carries
the actual `.md` / `.yaml` / `.json` files. This is what makes
`importlib.resources.files("scripts.commands")` resolve to the real
data inside a wheel.

## Mechanism 4: `scripts/_version.py`

Single importable source for `__version__`. The string is mirrored in
`pyproject.toml` and `.cursor-plugin/plugin.json`; drift is detected by
`test_version_three_sources_in_sync`.

## Inventory of files that used to embed absolute paths

| File | Was | Now |
|---|---|---|
| `tests/conftest.py` | empty (no fixtures yet) | `plugin_root` + `fixtures_dir` fixtures |
| `scripts/reproctl.py` | references `Path(__file__)` | unchanged (R1 invariant — controller unchanged) |
| `tests/test_chaos.py` | `Path(__file__).parent.parent` | unchanged (R3 territory; subprocess tests use Path-based plugin_root) |
| `scripts/startup/lock.py` | hard-coded `"0.2.0"` literal | imports `_DEFAULT_PLUGIN_VERSION` |
| `scripts/orchestrator/migrate.py` | hard-coded `"0.2.0"` literal | imports `_DEFAULT_PLUGIN_VERSION` |
| `scripts/reproctl/__init__.py` | hard-coded `"0.2.0"` literal | `from _version import __version__` |
| `scripts/startup/__init__.py` | hard-coded `"0.2.0"` literal | `from _version import __version__` |

## Audit results

- `conftest.py`: no `sys.path.insert`, no quoted absolute paths. ✅
- `fixture_locator.py`: only Path joins relative to importlib.files. ✅
- `pyproject.toml`: no absolute paths. ✅
- All `import` statements resolve under the editable install. ✅

## Forbidden-pattern check (R1 invariant)

A static grep of the new files confirms:

```
$ grep -rn "/home/\|/tmp/\|/Users/" scripts/_version.py scripts/fixture_locator.py scripts/reproctl/__main__.py tests/conftest.py tests/test_r1_acceptance.py
(no matches)
```
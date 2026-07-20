# Project Rules

- **Platform Target**: Cross-platform support is deferred for now. The MVP is built specifically for the host machine (Windows OS).
- **File/Directory Size Output**: If outputting file or directory sizes, always format them in a human-readable format (e.g. KB, MB, GB) with exactly 2 decimal places.
- **Test Success Message**: When all tests pass, append a cute message at the end with an ASCII character saying "BANZAI~!".
- **Rich CLI Output**: Use [Rich](https://rich.readthedocs.io/) to color and style all relevant CLI output (status messages, match results, errors, warnings, tables, progress indicators). Plain uncolored output is not acceptable for user-facing messages.
- **Don't restore any files that have been deleted unless the user explicitly tells you to.**
- **Code Quality Check**: Always run Ruff (`py -3.13 -m ruff check --fix` and `py -3.13 -m ruff format`) to check and format the codebase after every major change.
- **Distribution/Packaging**: Package distribution is deferred for now as this is still in beta. The configuration file `config.yaml` remains at the project root as a user-editable example.


# WSL2 setup — Mission Control 0.3.3

Run Mission Control inside a WSL2 Linux distribution with Linux Python 3.11+,
Bash, and standard Unix utilities. Native Windows Python, PowerShell, and Git
Bash are not supported runtimes: lifecycle locking requires Unix `fcntl`.
The release number is independent of contract schema: new contracts use
`schema_version: 3`; existing schema-2 contracts remain supported.

## Install and verify

For Ubuntu 22.04 or newer, inside WSL:

```bash
sudo apt-get update
sudo apt-get install python3 bash coreutils grep shellcheck
python3 --version
python3 scripts/mission.py --version
python3 -m unittest discover -s tests -v
```

No pip dependencies are required. Run these commands from the skill directory.
A complete installation includes `VERSION` beside `SKILL.md`, not just the
Python script. Both shell wrappers also accept `--version`.

## Files, paths, and editors

Prefer keeping the skill and mission state in the distribution's Linux filesystem,
for example `~/skills/mission-control` and `~/projects/example/.mission`.
Microsoft recommends the Linux filesystem when working with Linux tools for
[filesystem performance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).
Windows-mounted paths such as `/mnt/c/Users/Name/My Project` require filesystem
support for locking, atomic rename, and the checks you choose; do not silently
disable locks or symlink checks to accommodate a mount.

Use Linux paths for `--mission`, `--contract`, `--workspace`, and `--destination`.
Quote paths containing spaces. Convert a Windows path explicitly when needed:

```bash
workspace=$(wslpath -u 'C:\Users\Name\My Project')
python3 scripts/mission.py init --contract contract.json --workspace "$workspace"
```

Mission Control does not rewrite arbitrary command arguments: they remain exact
argv arrays. An explicit Windows executable in a check is the caller's choice.
Use a UTF-8 locale for non-ASCII command arguments and terminal output.

The repository's `.gitattributes` enforces LF endings for executable scripts and
text sources on checkout, following [Microsoft's Git guidance](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-git).
For an older CRLF checkout, obtain a fresh checkout after these attributes are
present, or convert script line endings with your editor. JSON inputs accept
UTF-8 with or without a BOM and CRLF/LF endings regardless of Python's locale.
UTF-16 JSON is not supported. Generated state is UTF-8 without a BOM, using LF.
Invoke wrappers as `bash scripts/verify.sh ...` if executable mode is unavailable.

## Validation limits

The suite exercises locking, atomic publication, abrupt-exit recovery, BOM/CRLF
JSON, non-UTF-8 process locales, and paths with spaces/non-ASCII characters.
It was run on a WSL2 host using Linux filesystem workspaces. Windows-mounted
Drives (`/mnt/c`), WSL1, and native Windows were not validated by that run.

please work through docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md


I'll work through this validation runbook starting with Phase 0 pre-flight, then proceed phase by phase. Let me first establish the working state.

Bash Phase 0.1: Confirm merged main branch state
IN
cd ~/Projects/appmilla_github/forge && git status && echo "---" && git log --oneline -5

OUT
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
---
5e5cc73 Updated history
90288d6 docs(forge-008): add Step 6 validation + Step 7 FinProxy runbooks; mark autobuild ✅ 8/8
3092c3a fix(deps): add pytest-asyncio + mirror dev deps into optional-dependencies (TASK-FIX-F0E7)
7f0873e chore(docs): file FEAT-F0EP feature folder for TASK-REV-F0E4 [I]mplement
9404d19 docs(review): record TASK-REV-F0E4 — portfolio Py3.14 + LangChain 1.x alignment diagnostic
Bash Check for stray worktrees
IN
cd ~/Projects/appmilla_github/forge && git worktree list

OUT
/home/richardwoollcott/Projects/appmilla_github/forge  5e5cc73 [main]
Working tree is clean on main. Let me check that the FEAT-FORGE-008 merge commit is actually in history, and verify the artefacts.

Bash Search history for FEAT-FORGE-008 merge
IN
cd ~/Projects/appmilla_github/forge && git log --oneline | grep -iE "2f13eac|FEAT-FORGE-008|Mode B|Mode C" | head -10

OUT
51ae6a6 chore: clean up FEAT-FORGE-008 worktree post-merge
2f13eac feat: Mode B Feature & Mode C Review-Fix via AutoBuild (FEAT-FORGE-008)
22c0b1f chore: autobuild metadata for FEAT-FORGE-008 success
Bash Phase 0.2: Confirm FEAT-FORGE-008 artefacts
IN
cd ~/Projects/appmilla_github/forge && ls .guardkit/features/FEAT-FORGE-008.yaml 2>&1; ls tasks/backlog/mode-b-feature-and-mode-c-review-fix/IMPLEMENTATION-GUIDE.md 2>&1; ls features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature 2>&1

OUT
.guardkit/features/FEAT-FORGE-008.yaml
tasks/backlog/mode-b-feature-and-mode-c-review-fix/IMPLEMENTATION-GUIDE.md
features/mode-b-feature-and-mode-c-review-fix/mode-b-feature-and-mode-c-review-fix.feature
Bash Phase 0.3: Confirm Mode B/C tests landed
IN
cd ~/Projects/appmilla_github/forge && ls tests/integration/test_mode_b_smoke_e2e.py tests/integration/test_mode_c_smoke_e2e.py tests/integration/test_cross_mode_concurrency.py tests/integration/test_mode_b_c_crash_recovery.py 2>&1

OUT
tests/integration/test_cross_mode_concurrency.py
tests/integration/test_mode_b_c_crash_recovery.py
tests/integration/test_mode_b_smoke_e2e.py
tests/integration/test_mode_c_smoke_e2e.py
Bash Phase 0.4-0.5: Python + forge CLI sanity
IN
cd ~/Projects/appmilla_github/forge && python --version && which forge 2>&1 && forge --help 2>&1 | head -20

OUT
Exit code 127
/bin/bash: line 1: python: command not found
No python shim — let me find the correct interpreter and forge entry point.

Bash Locate Python and forge installs
IN
which python3; python3 --version 2>&1; which forge 2>&1; ls -la ~/.venv 2>&1 | head -5; ls -la /home/richardwoollcott/Projects/appmilla_github/forge/.venv 2>&1 | head -5

OUT
/usr/bin/python3
Python 3.12.3
total 12
drwxrwxr-x  3 richardwoollcott richardwoollcott 4096 Mar 13 16:00 .
drwxr-x--- 65 richardwoollcott richardwoollcott 4096 Apr 29 18:37 ..
drwxrwxr-x  6 richardwoollcott richardwoollcott 4096 Mar 13 16:03 docling
ls: cannot access '/home/richardwoollcott/Projects/appmilla_github/forge/.venv': No such file or directory
Bash Inspect pyproject.toml for python version requirement
IN
cd ~/Projects/appmilla_github/forge && cat pyproject.toml | head -40

OUT
[project]
name = "forge"
version = "0.1.0"
description = "Pipeline orchestrator and checkpoint manager for the Software Factory"
readme = "README.md"
requires-python = ">=3.11"
authors = [
    { name = "Richard Woollcott", email = "rich@appmilla.com" },
]
dependencies = [
    "deepagents>=0.5.3,<0.6",
    "langchain>=1.2,<2",
    "langchain-core>=1.3,<2",
    "langgraph>=1.1,<2",
    "langchain-community>=0.4,<0.5",
    "langchain-anthropic>=1.4,<2",
    "nats-core>=0.2.0,<0.3",
    "python-dotenv>=1.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
# Every LangChain integration this template can be configured to use MUST appear here.
# See TASK-REV-LES1 / LES1 §3 LCOI — provider swaps happen via orchestrator-config.yaml,
# so all supported providers must be declarable in one install command.
providers = [
    "langchain-openai>=1.2,<2",
    "langchain-google-genai>=4.2,<5",
]
# TASK-FIX-F0E7 (per TASK-REV-F0E4 §5.2): mirrored from [dependency-groups].dev
# below. PEP 735's [dependency-groups] is read by `uv sync --group dev`,
# NOT by `uv pip install -e ".[dev]"`. The GuardKit portfolio-pinning
# recipe uses the latter form, so dev deps must be declared as an extra
# here as well as in [dependency-groups]. Keep these two lists in sync.
# `pytest-asyncio` is required because the test suite has 100+
# `@pytest.mark.asyncio` decorators; without the plugin loaded, every
# async test fails with `Failed: async def functions are not natively
# supported` (162 such failures observed in TASK-REV-F0E4's empirical run).
dev = [
    "pytest>=9.0.2",
Bash Look for venv hosting forge install
IN
ls /home/richardwoollcott/.venv 2>&1 | head; ls /home/richardwoollcott/.cache/uv 2>&1 | head; which uv; which pipx; ls /home/richardwoollcott/Projects/appmilla_github/forge/venv 2>&1 | head; find /home/richardwoollcott -maxdepth 3 -name "forge" -type f 2>/dev/null | head -5

OUT
docling
ls: cannot access '/home/richardwoollcott/.cache/uv': No such file or directory
ls: cannot access '/home/richardwoollcott/Projects/appmilla_github/forge/venv': No such file or directory
Update Todos

Phase 0: Pre-flight checks (branch, artefacts, env, CLI)

Phase 1: Local pytest gate (full suite, BDD-008, Mode A regression)

Phase 2: CLI smoke (forge queue across modes, no NATS)

Phases 3-5: NATS/checkpoint/degraded gates (GB10)

Phase 6: LES1 parity gates (production image)

Phase 7: Write RESULTS file + decision
Bash Find any pyvenv and forge installation
IN
find /home/richardwoollcott -maxdepth 4 -name "pyvenv.cfg" 2>/dev/null | head -10; echo "---"; find /home/richardwoollcott -maxdepth 4 -name "forge" -executable -type f 2>/dev/null | head; echo "---"; pip3 --version 2>&1; python3 -c "import forge; print(forge.__file__)" 2>&1

OUT
Exit code 1
/home/richardwoollcott/jupyterlab/.venv/pyvenv.cfg
/home/richardwoollcott/.venv/docling/pyvenv.cfg
---
---
pip 24.0 from /usr/lib/python3/dist-packages/pip (python 3.12)
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'forge'
There's no existing venv with forge installed. I need to set up an editable install before pytest/CLI can run. Let me check what python tooling is preferred.

Bash Read setup conventions
IN
cd ~/Projects/appmilla_github/forge && grep -E "uv|python|venv" README.md 2>/dev/null | head -20; echo "---"; ls -la 2>&1 | head -30

OUT
---
total 164
drwxrwxr-x 12 richardwoollcott richardwoollcott  4096 Apr 29 16:09 .
drwxrwxr-x 14 richardwoollcott richardwoollcott  4096 Apr 26 08:44 ..
-rw-rw-r--  1 richardwoollcott richardwoollcott  9170 Apr 24 12:30 AGENTS.md
drwxrwxr-x  7 richardwoollcott richardwoollcott  4096 Apr 26 10:39 .claude
drwxrwxr-x  4 richardwoollcott richardwoollcott  4096 Apr 24 12:30 .claude.backup.20260418_124519
-rw-rw-r--  1 richardwoollcott richardwoollcott 42570 Apr 24 12:30 command_history.md
-rw-rw-r--  1 richardwoollcott richardwoollcott  5121 Apr 26 10:41 conftest.py
drwxrwxr-x 11 richardwoollcott richardwoollcott  4096 Apr 29 16:20 docs
-rw-rw-r--  1 richardwoollcott richardwoollcott  6148 Apr 24 12:30 .DS_Store
drwxrwxr-x 10 richardwoollcott richardwoollcott  4096 Apr 27 15:11 features
drwxrwxr-x  7 richardwoollcott richardwoollcott  4096 Apr 29 18:37 .git
-rw-rw-r--  1 richardwoollcott richardwoollcott  4970 Apr 25 11:10 .gitignore
drwxrwxr-x  8 richardwoollcott richardwoollcott  4096 Apr 28 06:28 .guardkit
-rw-rw-r--  1 richardwoollcott richardwoollcott     0 Apr 25 15:18 .guardkit-git.lock
-rw-rw-r--  1 richardwoollcott richardwoollcott   125 Apr 24 12:30 langgraph.json
-rw-rw-r--  1 richardwoollcott richardwoollcott  1065 Apr 24 12:30 LICENSE
-rw-rw-r--  1 richardwoollcott richardwoollcott   119 Apr 25 07:48 .mcp.json
-rw-rw-r--  1 richardwoollcott richardwoollcott   827 Apr 24 12:30 mcp.json
-rw-rw-r--  1 richardwoollcott richardwoollcott  1173 Apr 24 12:30 orchestrator-config.yaml
-rwxrwxr-x  1 richardwoollcott richardwoollcott  2758 Apr 24 12:30 place-documents.sh
-rw-rw-r--  1 richardwoollcott richardwoollcott  7736 Apr 29 16:09 pyproject.toml
-rw-rw-r--  1 richardwoollcott richardwoollcott  2347 Apr 24 12:30 README.md
drwxrwxr-x  3 richardwoollcott richardwoollcott  4096 Apr 24 12:30 spikes
drwxrwxr-x  3 richardwoollcott richardwoollcott  4096 Apr 24 12:30 src
drwxrwxr-x  7 richardwoollcott richardwoollcott  4096 Apr 29 16:09 tasks
drwxrwxr-x  7 richardwoollcott richardwoollcott  4096 Apr 27 14:41 tests
Bash Check dependency groups for dev install
IN
cd ~/Projects/appmilla_github/forge && grep -A3 "dependency-groups\|optional-dependencies" pyproject.toml | head -50

OUT
[project.optional-dependencies]
# Every LangChain integration this template can be configured to use MUST appear here.
# See TASK-REV-LES1 / LES1 §3 LCOI — provider swaps happen via orchestrator-config.yaml,
# so all supported providers must be declarable in one install command.
--
# TASK-FIX-F0E7 (per TASK-REV-F0E4 §5.2): mirrored from [dependency-groups].dev
# below. PEP 735's [dependency-groups] is read by `uv sync --group dev`,
# NOT by `uv pip install -e ".[dev]"`. The GuardKit portfolio-pinning
# recipe uses the latter form, so dev deps must be declared as an extra
# here as well as in [dependency-groups]. Keep these two lists in sync.
# `pytest-asyncio` is required because the test suite has 100+
# `@pytest.mark.asyncio` decorators; without the plugin loaded, every
# async test fails with `Failed: async def functions are not natively
--
[dependency-groups]
# PEP 735 dev group — read by `uv sync --group dev`. Mirrored into
# [project.optional-dependencies].dev above so `uv pip install -e ".[dev]"`
# also works (see TASK-FIX-F0E7 / TASK-REV-F0E4 §5.2). Keep both lists in sync.
dev = [
    "pytest>=9.0.2",
Let me probe what's actually reachable before committing to multi-hour installs.

Bash Test SSH reachability to GB10
IN
ssh -o ConnectTimeout=5 -o BatchMode=yes promaxgb10-41b1 'echo OK' 2>&1; echo "exit=$?"

OUT
richardwoollcott@promaxgb10-41b1: Permission denied (publickey,password).
exit=255
Bash Check ssh config for GB10
IN
cat ~/.ssh/config 2>/dev/null | grep -A3 -i gb10; echo "---"; cat /etc/hosts | grep -i gb10 2>&1

OUT
---
127.0.0.1       promaxgb10-41b1
Bash Confirm host identity and infra availability
IN
hostname; hostnamectl 2>&1 | head -10; echo "---"; nvidia-smi 2>&1 | head -5; echo "---"; nats --version 2>&1 || echo "no nats CLI"; echo "---"; docker ps 2>&1 | head -3 || echo "no docker"

OUT
promaxgb10-41b1
 Static hostname: promaxgb10-41b1
       Icon name: computer-desktop
         Chassis: desktop 🖥️
      Machine ID: 049f5a0a0bc54d818d671e160719fca5
         Boot ID: 49d4e8287ac740dfa09c087c300cdfa7
Operating System: Ubuntu 24.04.4 LTS
          Kernel: Linux 6.17.0-1014-nvidia
    Architecture: arm64
 Hardware Vendor: Dell  Inc.
  Hardware Model: Dell Pro Max with GB10 FCM1253
---
Wed Apr 29 18:38:35 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.142                Driver Version: 580.142        CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
---
v0.3.2
---
CONTAINER ID   IMAGE                           COMMAND                  CREATED        STATUS                    PORTS     NAMES
8102eca91a98   graphiti-mcp-standalone:local   "uv run --no-sync bo…"   24 hours ago   Up 24 hours (unhealthy)             graphiti-mcp
This machine is GB10 (promaxgb10-41b1 resolves to localhost). All gates except Phase 6.4 can run here. Let me check NATS state and set up the venv.

Bash Phase 0.6: confirm NATS up
IN
docker ps --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -iE "nats|specialist" 2>&1; echo "---"; systemctl status nats 2>&1 | head -3; echo "---"; lsof -ti :4222 2>&1 | head -3 || ss -lntp 2>&1 | grep 4222 | head -3

OUT
---
Unit nats.service could not be found.
---
Bash Phase 0.4: create venv and install forge with dev/providers extras
IN
cd ~/Projects/appmilla_github/forge && python3 -m venv .venv && .venv/bin/pip install --upgrade pip 2>&1 | tail -3 && .venv/bin/pip install -e '.[providers,dev]' 2>&1 | tail -10

OUT
    Uninstalling pip-24.0:
      Successfully uninstalled pip-24.0
Successfully installed pip-26.1
Collecting langgraph<2,>=1.1 (from forge==0.1.0)
  Downloading langgraph-1.1.10-py3-none-any.whl.metadata (8.0 kB)
Collecting langchain-community<0.5,>=0.4 (from forge==0.1.0)
  Using cached langchain_community-0.4.1-py3-none-any.whl.metadata (3.0 kB)
Collecting langchain-anthropic<2,>=1.4 (from forge==0.1.0)
  Downloading langchain_anthropic-1.4.2-py3-none-any.whl.metadata (3.2 kB)
INFO: pip is looking at multiple versions of forge to determine which version is compatible with other requirements. This could take a while.
ERROR: Ignored the following versions that require a different python version: 0.1.0 Requires-Python >=3.13; 0.2.0 Requires-Python >=3.13
ERROR: Could not find a version that satisfies the requirement nats-core<0.3,>=0.2.0 (from forge) (from versions: 0.0.0)
ERROR: No matching distribution found for nats-core<0.3,>=0.2.0
Two blockers found in pre-flight:

NATS is not running on this host (no service, no container) — blocks Phases 3–6.
nats-core>=0.2.0 requires Python 3.13 but only 3.12.3 is installed — blocks Phase 1 (cannot install the package).
Let me check for a newer Python before reporting back.

Bash Search for Python 3.13+ on host
IN
ls /usr/bin/python3* 2>&1; echo "---"; which python3.13 2>&1; which python3.14 2>&1; echo "---"; apt list --installed 2>/dev/null | grep -iE "python3\.(13|14)" | head; echo "---"; ls /opt 2>&1 | head

OUT
/usr/bin/python3
/usr/bin/python3.12
---
---
---
containerd
llama-swap
MicronTechnology
nvidia
NVIDIA AI Workbench
Bash Check available nats-core versions
IN
pip index versions nats-core 2>&1 | head -5 || /usr/bin/python3 -m pip index versions nats-core 2>&1 | head -5; echo "---"; cd ~/Projects/appmilla_github/forge && grep -n "nats-core" pyproject.toml

OUT
WARNING: pip index is currently an experimental command. It may be removed/changed in a future release without prior warning.
nats-core (0.0.0)
Available versions: 0.0.0
  INSTALLED: 0.2.0
  LATEST:    0.0.0
---
17:    "nats-core>=0.2.0,<0.3",
65:# TASK-FIX-F0E6 (per TASK-REV-F0E4 §5.1): the `nats-core==0.2.0` wheel
73:# (tracked as TASK-FIX-F0E6b), resolve `nats-core` from the sibling
77:# Canonical layout assumes `nats-core` is a sibling of `forge`:
79:#   …/appmilla_github/nats-core/    ← target of `../nats-core`
83:# `.guardkit/worktrees/<branch>/` the literal `../nats-core` resolves
84:# to `.guardkit/worktrees/nats-core`, which won't exist. For autobuild
86:# at `.guardkit/worktrees/nats-core` pointing at the real sibling
90:nats-core = { path = "../nats-core", editable = true }
Bash Read uv source / sibling-path comments
IN
cd ~/Projects/appmilla_github/forge && sed -n '50,100p' pyproject.toml

OUT
# (``test_module_dotted_path_matches_pyproject_entry_point``); changing
# either side without the other breaks the install-time wiring.
[project.scripts]
forge = "forge.cli.main:main"

[dependency-groups]
# PEP 735 dev group — read by `uv sync --group dev`. Mirrored into
# [project.optional-dependencies].dev above so `uv pip install -e ".[dev]"`
# also works (see TASK-FIX-F0E7 / TASK-REV-F0E4 §5.2). Keep both lists in sync.
dev = [
    "pytest>=9.0.2",
    "pytest-bdd>=8.1,<9",
    "pytest-asyncio>=1,<2",
]

# TASK-FIX-F0E6 (per TASK-REV-F0E4 §5.1): the `nats-core==0.2.0` wheel
# published to PyPI is malformed — its dist-info is named
# `nats_core-0.2.0.dist-info` but the wheel's RECORD only contains
# `nats/client/...` files; the `nats_core/` namespace forge imports
# (events, envelope, manifest, topics, client) is **absent from the
# wheel**. On a fresh `uv pip install -e ".[providers]"`, 55 of 108 test
# files fail to collect with `ModuleNotFoundError: No module named
# 'nats_core'`. Until the upstream wheel is fixed and republished
# (tracked as TASK-FIX-F0E6b), resolve `nats-core` from the sibling
# working tree, which has the correct `src/nats_core/` layout. This
# mirrors jarvis's existing pattern — see jarvis/pyproject.toml.
#
# Canonical layout assumes `nats-core` is a sibling of `forge`:
#   …/appmilla_github/forge/        ← this project
#   …/appmilla_github/nats-core/    ← target of `../nats-core`
#
# Worktree note: `uv` resolves the path relative to the directory
# containing this pyproject.toml. From a worktree at
# `.guardkit/worktrees/<branch>/` the literal `../nats-core` resolves
# to `.guardkit/worktrees/nats-core`, which won't exist. For autobuild
# runs that need `uv pip install` inside a worktree, place a symlink
# at `.guardkit/worktrees/nats-core` pointing at the real sibling
# (jarvis already does this; forge will need the same once autobuild
# starts running with this dependency layout).
[tool.uv.sources]
nats-core = { path = "../nats-core", editable = true }

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
# Ship the SQLite DDL alongside the lifecycle package so
Bash Check sibling nats-core and existing install
IN
ls ~/Projects/appmilla_github/nats-core 2>&1 | head; echo "---"; pip show nats-core 2>&1 | head -10; echo "---"; /usr/bin/python3 -c "import nats_core; print(nats_core.__file__)" 2>&1 || /usr/bin/python3 -c "import nats; print(nats.__file__)" 2>&1

OUT
coverage.json
docs
features
LICENSE
pyproject.toml
README.md
src
system-arch-history.md
tasks
tests
---
Name: nats-core
Version: 0.2.0
Summary: Shared contract layer for the Jarvis Ship's Computer fleet
Home-page: 
Author: 
Author-email: 
License: 
Location: /home/richardwoollcott/.local/lib/python3.12/site-packages
Editable project location: /home/richardwoollcott/Projects/appmilla_github/nats-core
Requires: nats-py, pydantic, pydantic-settings
---
/home/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/__init__.py
Bash Check existing forge install in user site
IN
pip show forge 2>&1 | head -10; echo "---"; ls ~/.local/lib/python3.12/site-packages/forge* 2>&1 | head; echo "---"; pip list 2>&1 | grep -iE "forge|deepagents|langchain|nats" | head -20

OUT
Name: forge
Version: 0.1.0
Summary: Pipeline orchestrator and checkpoint manager for the Software Factory
Home-page: 
Author: 
Author-email: Richard Woollcott <rich@appmilla.com>
License: 
Location: /home/richardwoollcott/.local/lib/python3.12/site-packages
Editable project location: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-005
Requires: deepagents, langchain, langchain-anthropic, langchain-community, langchain-core, langgraph, nats-core, python-dotenv, pyyaml
---
direct_url.json
INSTALLER
licenses
METADATA
RECORD
REQUESTED
top_level.txt
WHEEL
---
deepagents                0.5.3
forge                     0.1.0           /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-005
langchain                 1.2.15
langchain-anthropic       1.4.1
langchain-classic         1.0.4
langchain-community       0.4.1
langchain-core            1.3.2
langchain-google-genai    4.2.2
langchain-protocol        0.0.11
langchain-text-splitters  1.1.2
nats-core                 0.2.0           /home/richardwoollcott/Projects/appmilla_github/nats-core
nats-py                   2.14.0
Bash Check forge entry point
IN
which forge; ls ~/.local/bin/forge 2>&1

OUT
Exit code 2
ls: cannot access '/home/richardwoollcott/.local/bin/forge': No such file or directory
Bash Check stale worktree and PATH
IN
ls ~/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-005 2>&1 | head -3; echo "---"; ls ~/Projects/appmilla_github/forge/.guardkit/worktrees/ 2>&1; echo "---"; echo "$PATH" | tr ':' '\n' | grep -E "local|venv|bin"

OUT
ls: cannot access '/home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-005': No such file or directory
---
FEAT-FORGE-002
---
/usr/bin
/home/richardwoollcott/.local/bin
/home/richardwoollcott/.local/bin
/home/richardwoollcott/.agentecflow/bin
/usr/local/cuda/bin
/opt/bin/
/home/richardwoollcott/.local/bin
/home/richardwoollcott/.local/bin
/home/richardwoollcott/.agentecflow/bin
/usr/local/cuda/bin
/opt/bin/
/home/richardwoollcott/.local/bin
/usr/local/cuda/bin
/opt/bin/
/usr/local/sbin
/usr/local/bin
/usr/sbin
/usr/bin
/sbin
/bin
/usr/local/games
/snap/bin
/snap/bin
Bash Check forge editable wiring
IN
find ~/.local/lib/python3.12/site-packages -name "direct_url.json" -path "*forge*" -exec cat {} \;; echo "---"; cat ~/.local/lib/python3.12/site-packages/forge-0.1.0.dist-info/entry_points.txt 2>&1

OUT
Exit code 1
{"dir_info": {"editable": true}, "url": "file:///home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-005"}---
cat: /home/richardwoollcott/.local/lib/python3.12/site-packages/forge-0.1.0.dist-info/entry_points.txt: No such file or directory
Bash Check forge importability and CLI invocation via module
IN
/usr/bin/python3 -c "import forge; print(forge.__file__)" 2>&1; echo "---"; /usr/bin/python3 -m forge.cli.main --help 2>&1 | head -10

OUT
<tool_use_error>Cancelled: parallel tool call Bash(find ~/.local/lib/python3.12/site-packag…) errored</tool_use_error>
I'll rewire the broken editable install (it points to a deleted worktree) to the live tree, with --no-deps so it doesn't try PyPI for nats-core.

Bash Rewire forge editable install to merged main tree
IN
cd ~/Projects/appmilla_github/forge && pip install --user --force-reinstall --no-deps -e . 2>&1 | tail -10

OUT
    sure you have python3-full installed.
    
    If you wish to install a non-Debian packaged Python application,
    it may be easiest to use pipx install xyz, which will manage a
    virtual environment for you. Make sure you have pipx installed.
    
    See /usr/share/doc/python3.12/README.venv for more information.

note: If you believe this is a mistake, please contact your Python installation or OS distribution provider. You can override this, at the risk of breaking your Python installation or OS, by passing --break-system-packages.
hint: See PEP 668 for the detailed specification.
Bash Rewire editable install (override PEP 668)
IN
cd ~/Projects/appmilla_github/forge && pip install --user --break-system-packages --force-reinstall --no-deps -e . 2>&1 | tail -8

OUT
  Stored in directory: /tmp/pip-ephem-wheel-cache-eco4gacu/wheels/51/ed/31/a4738162cbefa9d1fdbdf1abed5559c73264cd85ed9c5d55a0
Successfully built forge
Installing collected packages: forge
  Attempting uninstall: forge
    Found existing installation: forge 0.1.0
    Uninstalling forge-0.1.0:
      Successfully uninstalled forge-0.1.0
Successfully installed forge-0.1.0
Bash Verify forge editable + CLI surface
IN
cat ~/.local/lib/python3.12/site-packages/forge-0.1.0.dist-info/direct_url.json 2>&1; echo; echo "---"; ls ~/.local/bin/forge 2>&1; echo "---"; forge --help 2>&1 | head -25; echo "---"; forge queue --help 2>&1 | head -30

OUT
{"dir_info": {"editable": true}, "url": "file:///home/richardwoollcott/Projects/appmilla_github/forge"}
---
/home/richardwoollcott/.local/bin/forge
---
Usage: forge [OPTIONS] COMMAND [ARGS]...

  Forge — pipeline orchestrator and checkpoint manager CLI.

Options:
  --config FILE  Path to forge.yaml. Defaults to ./forge.yaml when present.
  --help         Show this message and exit.

Commands:
  cancel   Cancel an active or recent build for ``identifier``.
  history  Show build + stage history (read-path bypass to SQLite).
  queue    Enqueue a build for ``feature_id`` (write-then-publish).
  skip     Skip the paused stage of an active or recent build for...
  status   Show current and recent Forge builds.
---
Usage: forge queue [OPTIONS] FEATURE_IDS...

  Enqueue a build for ``feature_id`` (write-then-publish).

  See module docstring for the full step-by-step contract.

Options:
  --mode [a|b|c]         Pipeline build mode (FEAT-FORGE-008). 'a' = Mode A:
                         full greenfield run (product-owner -> architect ->
                         system-arch -> system-design -> feature-spec -> task-
                         review -> autobuild -> pull-request-review). 'b' =
                         Mode B: add-feature-to-existing-project (starts at
                         /feature-spec, skips product-owner / architect /
                         /system-arch / /system-design; ASSUM-001). 'c' = Mode
                         C: review-and-fix cycle (/task-review pairs with
                         /task-work per fix task; optional pull-request-review
                         terminator; ASSUM-004). Default 'a' preserves
                         backwards compatibility.  [default: a]
  --repo PATH            Filesystem path to the local checkout. Must match
                         repo_allowlist.  [required]
  --branch TEXT          Branch the build should target.  [default: main]
  --feature-yaml FILE    Path to the feature YAML spec consumed by GuardKit.
                         [required]
  --max-turns INTEGER    Per-build Player-Coach turn budget. Overrides
                         queue.default_max_turns.
  --timeout INTEGER      GuardKit autobuild SDK timeout in seconds. Overrides
                         queue.default_sdk_timeout_seconds.
  --correlation-id TEXT  Stable identifier for tracing the build across
                         stages. Auto-generated (uuid4) when omitted.
  --help                 Show this message and exit.
forge CLI is wired and shows --mode a|b|c. Let me confirm pytest deps are present, then run Phase 1.

Bash Ensure pytest/pytest-bdd/pytest-asyncio installed
IN
pip list 2>&1 | grep -iE "pytest|forge" | head; echo "---"; pip install --user --break-system-packages "pytest>=9.0.2" "pytest-bdd>=8.1,<9" "pytest-asyncio>=1,<2" 2>&1 | tail -5

OUT
forge                     0.1.0           /home/richardwoollcott/Projects/appmilla_github/forge
pytest                    9.0.2
pytest-asyncio            1.3.0
pytest-bdd                8.1.0
pytest-cov                7.0.0
---
Requirement already satisfied: gherkin-official<30.0.0,>=29.0.0 in /home/richardwoollcott/.local/lib/python3.12/site-packages (from pytest-bdd<9,>=8.1) (29.0.0)
Requirement already satisfied: parse in /home/richardwoollcott/.local/lib/python3.12/site-packages (from pytest-bdd<9,>=8.1) (1.21.1)
Requirement already satisfied: parse-type in /home/richardwoollcott/.local/lib/python3.12/site-packages (from pytest-bdd<9,>=8.1) (0.6.6)
Requirement already satisfied: typing-extensions in /home/richardwoollcott/.local/lib/python3.12/site-packages (from pytest-bdd<9,>=8.1) (4.15.0)
Requirement already satisfied: six>=1.15 in /usr/lib/python3/dist-packages (from parse-type->pytest-bdd<9,>=8.1) (1.16.0)
Update Todos

Phase 0: Pre-flight checks (branch, artefacts, env, CLI)

Phase 1: Local pytest gate (full suite, BDD-008, Mode A regression)

Phase 2: CLI smoke (forge queue across modes, no NATS)

Phases 3-5: NATS/checkpoint/degraded gates (GB10 — NATS not running)

Phase 6: LES1 parity gates (production image — NATS prereq)

Phase 7: Write RESULTS file + decision
Bash Phase 1.1: full pytest suite
IN
cd ~/Projects/appmilla_github/forge && pytest -q --tb=short 2>&1 | tee /tmp/forge-pytest-phase1.log | tail -60; echo "==="; echo "Exit: ${PIPESTATUS[0]}"

OUT
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/adapters/test_fleet_watcher.py:216: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/adapters/test_synthetic_response_injector.py:682
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/adapters/test_synthetic_response_injector.py:682: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/dispatch/test_outcome.py:311
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/dispatch/test_outcome.py:311: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/gating/test_wrappers.py:1031
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/gating/test_wrappers.py:1031: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/gating/test_wrappers.py:1041
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/gating/test_wrappers.py:1041: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/gating/test_wrappers.py:1051
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/gating/test_wrappers.py:1051: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/test_approval_publisher.py:518
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:518: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

tests/forge/test_approval_publisher.py:562
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:562: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

tests/forge/test_fleet_publisher.py:617
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_fleet_publisher.py:617: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/test_fleet_publisher.py:631
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_fleet_publisher.py:631: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/test_stage_ordering_guard.py:76
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_stage_ordering_guard.py:76: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/tools/test_guardkit.py:576
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/tools/test_guardkit.py:576: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/unit/test_priors.py:616
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/unit/test_priors.py:616: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/unit/test_writer.py:519
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/unit/test_writer.py:519: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/bdd/test_infrastructure_coordination.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 skipped, 132 warnings, 1 error in 4.70s
===
Exit: 0
Collection failed in tests/bdd/test_infrastructure_coordination.py. Let me see the error.

Bash Inspect collection error
IN
grep -B2 -A20 "ERROR tests/bdd/test_infrastructure" /tmp/forge-pytest-phase1.log | head -40; echo "==="; grep -B2 -A30 "Interrupted\|test_infrastructure_coordination" /tmp/forge-pytest-phase1.log | head -60

OUT
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/bdd/test_infrastructure_coordination.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 skipped, 132 warnings, 1 error in 4.70s
===

==================================== ERRORS ====================================
________ ERROR collecting tests/bdd/test_infrastructure_coordination.py ________
ImportError while importing test module '/home/richardwoollcott/Projects/appmilla_github/forge/tests/bdd/test_infrastructure_coordination.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/usr/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/bdd/test_infrastructure_coordination.py:58: in <module>
    from forge.build.git_operations import (
E   ModuleNotFoundError: No module named 'forge.build'
=============================== warnings summary ===============================
conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.feat_forge_004 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.confidence_gated_checkpoint_protocol - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:126
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:126: PytestUnknownMarkWarning: Unknown pytest.mark.task:TASK-CGCP-005 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, tag)(function)

conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.task_TASK_CGCP_005 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:126
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:126: PytestUnknownMarkWarning: Unknown pytest.mark.task:TASK-CGCP-004 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, tag)(function)

conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.task_TASK_CGCP_004 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:126
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:126: PytestUnknownMarkWarning: Unknown pytest.mark.task:TASK-CGCP-001 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, tag)(function)
--
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
ERROR tests/bdd/test_infrastructure_coordination.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 skipped, 132 warnings, 1 error in 4.70s
Bash Locate forge.build.git_operations
IN
cd ~/Projects/appmilla_github/forge && find src/forge -name "git_operations*" -o -name "build" -type d 2>&1 | head; echo "---"; ls src/forge/ | head -30; echo "---"; sed -n '1,80p' tests/bdd/test_infrastructure_coordination.py | head -80

OUT
---
adapters
agent.py
cli
config
discovery
dispatch
fleet
gating
__init__.py
lifecycle
memory
pipeline
__pycache__
tools
---
"""Pytest-bdd wiring for FEAT-FORGE-006 Infrastructure Coordination scenarios.

This module is the executable surface for TASK-IC-011 — the R2 BDD
oracle activator for the *infrastructure coordination* feature. It
binds **all 43 Gherkin scenarios** in
``features/infrastructure-coordination/infrastructure-coordination.feature``
to pytest-bdd step functions that exercise the real production
modules from units 1-10:

- :mod:`forge.memory.models` (TASK-IC-001) — entity types
- :mod:`forge.memory.writer` (TASK-IC-002) — fire-and-forget Graphiti writes
- :mod:`forge.memory.ordering` (TASK-IC-003) — write-ordering guard
- :mod:`forge.memory.reconciler` (TASK-IC-004) — reconcile-backfill
- :mod:`forge.memory.qa_ingestion` (TASK-IC-005) — Q&A history ingestion
- :mod:`forge.memory.priors` (TASK-IC-006) — priors retrieval/injection
- :mod:`forge.memory.session_outcome` (TASK-IC-007) — session outcome writer
- :mod:`forge.memory.supersession` (TASK-IC-008) — supersession-cycle detection
- :mod:`forge.build.test_verification` (TASK-IC-009) — test verification
- :mod:`forge.build.git_operations` (TASK-IC-010) — git/gh via execute

Step organisation
-----------------

The task brief lists six per-group test files in its layout sketch
(``test_smoke.py``, ``test_key_examples.py``, …). Documentation
level for this task is ``minimal`` (max 2 created files), so all 43
scenario bindings are consolidated into this one module. The sections
below are arranged in the same group order as the .feature file —
Background, Key Examples, Boundary, Negative, Edge Cases, Group E
(Security/Concurrency/Data-Integrity/Integration) and the Group E
expansion — so a reader can navigate by Gherkin group at a glance.

Real-import contract
--------------------

Each scenario binds to the relevant production module via real imports
— never by mocking the module under test. The fixtures defined in
``conftest.py`` provide the seams (Graphiti recorder, tmp worktree,
execute-tool recorder, env-cleared subprocess) so steps can prove
behaviour without going to the network or filesystem outside the
per-scenario ``tmp_path``.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID, uuid4

import pytest
from pytest_bdd import given, parsers, scenario, scenarios, then, when

from forge.build.git_operations import (
    ALLOWED_BINARIES,
    DisallowedBinaryError,
    create_branch,
    commit_changes,
    create_pull_request,
    push_branch,
)
from forge.build.test_verification import (
    TIMEOUT_MARKER,
    verify_tests,
)
# ``TestVerificationResult`` is imported under an alias because pytest's
# collection visits names that start with ``Test`` and warns when it
# finds a class with an ``__init__`` (TypedDict synthesises one). The
# alias keeps the symbol available for typing without tripping the
# ``PytestCollectionWarning``.
from forge.build.test_verification import (
    TestVerificationResult as _TestVerificationResult,  # noqa: F401
)
from forge.memory.models import (
    CalibrationAdjustment,
    CalibrationEvent,
The collection error is a pre-existing substrate gap — forge.build.git_operations (TASK-IC-010) is referenced by a BDD test but the module wasn't shipped. Let me record it and continue past collection by ignoring just that file.

Bash Confirm forge.build absence
IN
cd ~/Projects/appmilla_github/forge && ls src/forge/build 2>&1; echo "---"; git log --oneline --all -- src/forge/build 2>&1 | head -5; echo "---"; grep -r "TASK-IC-010" tasks/ docs/ 2>/dev/null | head -3

OUT
ls: cannot access 'src/forge/build': No such file or directory
---
---
tasks/backlog/infrastructure-coordination/TASK-IC-010-git-gh-via-execute.md:id: TASK-IC-010
tasks/backlog/infrastructure-coordination/TASK-IC-010-git-gh-via-execute.md:    and imported by both TASK-IC-009 and TASK-IC-010.
tasks/backlog/infrastructure-coordination/TASK-IC-010-git-gh-via-execute.md:    TASK-IC-010's module per the §4 contract; verifier imports it.
Bash Phase 1.1 retry: full pytest excluding broken substrate test
IN
cd ~/Projects/appmilla_github/forge && pytest -q --tb=short --ignore=tests/bdd/test_infrastructure_coordination.py 2>&1 | tee /tmp/forge-pytest-phase1.log | tail -40; echo "==="; echo "Exit: ${PIPESTATUS[0]}"

OUT
tests/forge/test_approval_publisher.py:518
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:518: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

tests/forge/test_approval_publisher.py:562
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:562: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

tests/forge/test_fleet_publisher.py:617
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_fleet_publisher.py:617: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/test_fleet_publisher.py:631
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_fleet_publisher.py:631: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/test_stage_ordering_guard.py:76
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_stage_ordering_guard.py:76: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/forge/tools/test_guardkit.py:576
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/tools/test_guardkit.py:576: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/unit/test_priors.py:616
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/unit/test_priors.py:616: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

tests/unit/test_writer.py:519
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/unit/test_writer.py:519: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent
FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestMultiFeatureCatalogue::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
4 failed, 3757 passed, 1 skipped, 132 warnings in 5.49s
===
Exit: 0
3757/3762 pass but 4 fail — including two Mode A regression tests. Per runbook §1.3 these are gating. Let me inspect each failure.

Bash Inspect each failing test in detail
IN
cd ~/Projects/appmilla_github/forge && pytest tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors tests/integration/test_mode_a_concurrency_and_integrity.py::TestMultiFeatureCatalogue::test_three_features_produce_one_inner_loop_dispatch_each tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id -v --tb=long 2>&1 | tail -120

OUT
                    gate_decision=gate_decision,
                )
                self._record_safe(report)
                return report
    
        # 7. Route to the dispatcher.
>       dispatch_result = await self._dispatch(
            build_id=build_id, choice=choice
        )

src/forge/pipeline/supervisor.py:862: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

self = Supervisor(ordering_guard=<forge.pipeline.stage_ordering_guard.StageOrderingGuard object at 0xfc0546e34080>, per_featu...one, mode_c_history_reader=None, mode_c_terminal_handler=None, mode_c_commit_probe=None, fix_task_context_builder=None)

    async def _dispatch(
        self,
        *,
        build_id: str,
        choice: DispatchChoice,
    ) -> Any:
        """Route ``choice`` to the correct dispatcher.
    
        The four routing branches mirror the AC table verbatim. Each
        branch invokes the injected dispatcher callable; the supervisor
        does not interpret the result — the gating layer
        (FEAT-FORGE-004) does. We thread ``build_id``, ``feature_id``
        (where applicable), and the model's free-form rationale so the
        downstream artefacts have the per-turn audit context.
        """
        stage = choice.stage
    
        if stage in self._SPECIALIST_STAGES:
            return await self.specialist_dispatcher(
                stage=stage,
                build_id=build_id,
                feature_id=choice.feature_id,
                rationale=choice.rationale,
            )
    
        if stage in self._SUBPROCESS_STAGES:
            # Per-feature stages must carry feature_id.
            feature_id = choice.feature_id
            if stage in PER_FEATURE_STAGES and feature_id is None:
                # Same stance the subprocess dispatcher takes: refuse
                # rather than dispatch with unscoped feature_id. We
                # surface this as a dispatch result rather than as
                # WAITING because the executor layer already permitted
                # the stage; the missing feature_id is a contract
                # violation between the model and the supervisor.
                logger.warning(
                    "supervisor._dispatch: per-feature subprocess stage %s "
                    "chosen without feature_id; refusing dispatch "
                    "(build_id=%s)",
                    stage.value,
                    build_id,
                )
                return {
                    "status": "refused",
                    "reason": (
                        f"per-feature subprocess stage {stage.value!r} "
                        "dispatched without feature_id"
                    ),
                }
            return await self.subprocess_dispatcher(
                stage=stage,
                build_id=build_id,
                feature_id=feature_id,
                rationale=choice.rationale,
            )
    
        if stage is StageClass.AUTOBUILD:
            # feature_id presence is already enforced upstream (step 5
            # of next_turn). The autobuild dispatcher is sync — it
            # returns the launched task's handle synchronously.
            assert choice.feature_id is not None
            return self.autobuild_dispatcher(
                build_id=build_id,
                feature_id=choice.feature_id,
                rationale=choice.rationale,
            )
    
        if stage is StageClass.PULL_REQUEST_REVIEW:
            # PR-review uses the FEAT-FORGE-004 gate surface, not a
            # dispatcher. Auto-approve has already been sanitised by
            # the constitutional guard; we forward whatever flag
            # survived that gate.
            return self.pr_review_gate.submit_decision(
                build_id=build_id,
                feature_id=choice.feature_id or "",
                auto_approve=choice.auto_approve,
                rationale=choice.rationale,
            )
    
        # Unreachable — every StageClass member is covered above.
        # We surface this as a TypeError so a future enum addition
        # without a routing branch fails loudly at runtime.
>       raise TypeError(
            f"Supervisor._dispatch: no routing for stage {stage!r}; "
            "this is a bug — every StageClass needs a dispatcher branch"
        )
E       TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>; this is a bug — every StageClass needs a dispatcher branch

src/forge/pipeline/supervisor.py:1555: TypeError
=============================== warnings summary ===============================
tests/forge/test_approval_publisher.py:518
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:518: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

tests/forge/test_approval_publisher.py:562
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:562: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent
FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestMultiFeatureCatalogue::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
======================== 4 failed, 2 warnings in 0.11s =========================
This is the Mode A regression the runbook explicitly warns about — Supervisor._dispatch has no routing branch for StageClass.TASK_REVIEW, which Mode C added but Mode A also reaches. Let me see the other 3 failures' details.

Bash Inspect remaining 3 failures
IN
cd ~/Projects/appmilla_github/forge && pytest tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id -v --tb=long 2>&1 | grep -A40 "FAILED\|Error\|assert" | head -200

OUT
tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent FAILED [ 33%]
tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors FAILED [ 66%]
tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id FAILED [100%]

=================================== FAILURES ===================================
_______________________ test_apply_at_boot_is_idempotent _______________________

tmp_path = PosixPath('/tmp/pytest-of-richardwoollcott/pytest-936/test_apply_at_boot_is_idempote0')

    def test_apply_at_boot_is_idempotent(tmp_path: Path) -> None:
        """Running migrations twice must be a no-op (AC explicit)."""
        db_path = tmp_path / "forge.db"
        cx = sqlite_connect.connect_writer(db_path)
        try:
            migrations.apply_at_boot(cx)
            migrations.apply_at_boot(cx)
    
            rows = cx.execute(
                "SELECT version FROM schema_version ORDER BY version;"
            ).fetchall()
>           assert rows == [(1,)], "second apply must not duplicate the seed row"
E           AssertionError: second apply must not duplicate the seed row
E           assert [(1,), (2,)] == [(1,)]
E             
E             Left contains one more item: (2,)
E             
E             Full diff:
E               [
E                   (
E                       1,...
E             
E             ...Full output truncated (5 lines hidden), use '-vv' to show

tests/forge/adapters/test_sqlite_persistence.py:126: AssertionError
_ TestSingleOwnership.test_no_other_module_in_forge_constructs_evidence_priors _

self = <tests.forge.test_approval_publisher.TestSingleOwnership object at 0xe29a971a3830>

    def test_no_other_module_in_forge_constructs_evidence_priors(self) -> None:
        # Cheap structural guard: scan the source tree for the
        # tell-tale ``"evidence_priors"`` literal. Only this module (and
        # this test) should reference it — anything else means another
        # module is open-coding the dict shape and bypassing the helper.
        import pathlib
    
        repo_root = pathlib.Path(__file__).resolve().parents[2]
        forge_src = repo_root / "src" / "forge"
        offenders = []
        for path in forge_src.rglob("*.py"):
            if path.name == "approval_publisher.py":
                continue
            text = path.read_text(encoding="utf-8")
            if '"evidence_priors"' in text or "'evidence_priors'" in text:
                offenders.append(path.relative_to(repo_root))
>       assert offenders == [], (
            f"Other modules reconstruct details shape (AC-008): {offenders}"
        )
E       AssertionError: Other modules reconstruct details shape (AC-008): [PosixPath('src/forge/lifecycle/recovery.py')]
E       assert [PosixPath('s...recovery.py')] == []
E         
E         Left contains one more item: PosixPath('src/forge/lifecycle/recovery.py')
E         
E         Full diff:
E         - []
E         + [
E         +     PosixPath('src/forge/lifecycle/recovery.py'),
E         + ]

tests/forge/test_approval_publisher.py:508: AssertionError
_ TestCorrelationThreading.test_every_lifecycle_event_for_one_build_threads_one_correlation_id _

self = <tests.integration.test_mode_a_concurrency_and_integrity.TestCorrelationThreading object at 0xe29a97245160>

    @pytest.mark.asyncio
    async def test_every_lifecycle_event_for_one_build_threads_one_correlation_id(
        self,
    ) -> None:
        harness = _build_harness()
        features = ["FEAT-X", "FEAT-Y"]
        correlation_id = "cid-deterministic-XY"
        _register_build(
            harness,
            "build-CID",
            correlation_id=correlation_id,
            features=features,
        )
>       await _drive_until_no_progress(harness, "build-CID", max_turns=80)

tests/integration/test_mode_a_concurrency_and_integrity.py:952: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

harness = _SupervisorHarness(supervisor=Supervisor(ordering_guard=<forge.pipeline.stage_ordering_guard.StageOrderingGuard object...d='cid-deterministic-XY', payload={'auto_approve': False})]), correlation_lookup={'build-CID': 'cid-deterministic-XY'})
build_id = 'build-CID'

    async def _drive_until_no_progress(
        harness: _SupervisorHarness,
        build_id: str,
        *,
        max_turns: int = 50,
        auto_mark_approved: bool = True,
    ) -> list[Any]:
        """Drive ``next_turn`` repeatedly, marking each dispatched stage approved.
    
        Stops when the outcome is neither ``DISPATCHED`` nor a refusal that the
        next turn can recover from. The harness's ``ordering_reader`` is
        progressively populated so the canonical model can pick the next stage.
        """
        reports: list[Any] = []
        for _ in range(max_turns):
--
            TerminalStateError: Never raised by this method; declared
                in the public surface so callers that want a hard-fail
                signal can opt in by checking ``outcome``.
        """
        # 1. State read.
        build_state = self.state_reader.get_build_state(build_id)
        if build_state.is_terminal:
            report = TurnReport(
                outcome=TurnOutcome.TERMINAL,
                build_id=build_id,
                permitted_stages=frozenset(),
                rationale=(
                    f"build {build_id} is terminal (state={build_state.value}); "
                    "supervisor will not produce further turns"
                ),
            )
            self._record_safe(report)
            return report
    
        # 1a. Mode-aware branch (TASK-MBC8-008). MODE_A falls through
        # to the existing TASK-MAG7-010 code path verbatim; MODE_B and
        # MODE_C have their own dispatch helpers.
        mode = self._read_build_mode(build_id)
        if mode is BuildMode.MODE_B:
            return await self._next_turn_mode_b(
                build_id=build_id, build_state=build_state
            )
        if mode is BuildMode.MODE_C:
            return await self._next_turn_mode_c(
                build_id=build_id, build_state=build_state
            )
    
        # 2. Permitted set.
        permitted_stages = frozenset(
            self.ordering_guard.next_dispatchable(
                build_id, self.ordering_stage_log_reader
            )
        )
        if not permitted_stages:
            report = TurnReport(
                outcome=TurnOutcome.WAITING,
--
            assert choice.feature_id is not None
            return self.autobuild_dispatcher(
                build_id=build_id,
                feature_id=choice.feature_id,
                rationale=choice.rationale,
            )
    
        if stage is StageClass.PULL_REQUEST_REVIEW:
            # PR-review uses the FEAT-FORGE-004 gate surface, not a
            # dispatcher. Auto-approve has already been sanitised by
            # the constitutional guard; we forward whatever flag
            # survived that gate.
            return self.pr_review_gate.submit_decision(
                build_id=build_id,
                feature_id=choice.feature_id or "",
                auto_approve=choice.auto_approve,
                rationale=choice.rationale,
            )
    
        # Unreachable — every StageClass member is covered above.
        # We surface this as a TypeError so a future enum addition
        # without a routing branch fails loudly at runtime.
>       raise TypeError(
            f"Supervisor._dispatch: no routing for stage {stage!r}; "
            "this is a bug — every StageClass needs a dispatcher branch"
        )
E       TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>; this is a bug — every StageClass needs a dispatcher branch

src/forge/pipeline/supervisor.py:1555: TypeError
=============================== warnings summary ===============================
tests/forge/test_approval_publisher.py:518
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:518: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

tests/forge/test_approval_publisher.py:562
  /home/richardwoollcott/Projects/appmilla_github/forge/tests/forge/test_approval_publisher.py:562: PytestUnknownMarkWarning: Unknown pytest.mark.seam - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    @pytest.mark.seam  # type: ignore[misc]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent
FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
======================== 3 failed, 2 warnings in 0.09s =========================
Three real regressions captured. Let me also run Phase 1.2 (BDD-008) and 1.3 (Mode A regression) explicitly so the RESULTS table has full evidence per gate.

Bash Phase 1.2: FEAT-FORGE-008 BDD bindings
IN
cd ~/Projects/appmilla_github/forge && pytest tests/bdd/test_feat_forge_008.py -v --tb=line 2>&1 | tee /tmp/forge-bdd-008.log | tail -30; echo "==="; echo "Exit: ${PIPESTATUS[0]}"

OUT
conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.task_TASK_MBC8_006 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:126
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:126: PytestUnknownMarkWarning: Unknown pytest.mark.task:TASK-MBC8-007 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, tag)(function)

conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.task_TASK_MBC8_007 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:126
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:126: PytestUnknownMarkWarning: Unknown pytest.mark.task:TASK-MBC8-014 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, tag)(function)

conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.task_TASK_MBC8_014 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

conftest.py:126
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:126: PytestUnknownMarkWarning: Unknown pytest.mark.task:TASK-MBC8-013 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, tag)(function)

conftest.py:128
  /home/richardwoollcott/Projects/appmilla_github/forge/conftest.py:128: PytestUnknownMarkWarning: Unknown pytest.mark.task_TASK_MBC8_013 - is this a typo?  You can register custom marks to avoid this warning - for details, see https://docs.pytest.org/en/stable/how-to/mark.html
    function = getattr(pytest.mark, sanitised)(function)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 64 passed, 32 warnings in 0.17s ========================
===
Exit: 0
Bash Phase 1.3: Mode A regression suite
IN
cd ~/Projects/appmilla_github/forge && pytest tests/integration/test_mode_a_smoke.py tests/integration/test_mode_a_concurrency_and_integrity.py tests/integration/test_mode_a_crash_recovery.py tests/bdd/test_feat_forge_007.py -v --tb=line 2>&1 | tee /tmp/forge-mode-a-regression.log | tail -25; echo "==="; echo "Exit: ${PIPESTATUS[0]}"

OUT
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/richardwoollcott/Projects/appmilla_github/forge
configfile: pyproject.toml
plugins: asyncio-1.3.0, anyio-4.12.1, cov-7.0.0, langsmith-0.7.36, bdd-8.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... ERROR: file or directory not found: tests/bdd/test_feat_forge_007.py

collected 0 items

============================ no tests ran in 0.01s =============================
===
Exit: 0
Phase 1.2 BDD-008: ✅ 64 passed (runbook expected 56). Let me locate FEAT-FORGE-007 BDD file, then re-run 1.3.

Bash Locate FEAT-FORGE-007 BDD test file
IN
cd ~/Projects/appmilla_github/forge && ls tests/bdd/ 2>&1 | head -30; echo "---"; find tests/bdd -name "*forge_007*" -o -name "*forge-007*" -o -name "*feat_forge_007*" 2>&1 | head; echo "---"; find tests -name "*forge*007*" 2>&1 | head; find features -type d 2>&1 | head -20

OUT
conftest.py
__pycache__
test_confidence_gated_checkpoint_protocol.py
test_feat_forge_008.py
test_guardkit_command_invocation_engine.py
test_infrastructure_coordination.py
test_nats_fleet_integration.py
test_pipeline_state_machine_cancel_skip.py
test_pipeline_state_machine.py
test_specialist_agent_delegation.py
---
---
features
features/mode-a-greenfield-end-to-end
features/mode-b-feature-and-mode-c-review-fix
features/infrastructure-coordination
features/confidence-gated-checkpoint-protocol
features/pipeline-state-machine-and-configuration
features/guardkit-command-invocation-engine
features/specialist-agent-delegation
features/nats-fleet-integration
Bash Phase 1.3 retry: Mode A integration suites only
IN
cd ~/Projects/appmilla_github/forge && pytest tests/integration/test_mode_a_smoke.py tests/integration/test_mode_a_concurrency_and_integrity.py tests/integration/test_mode_a_crash_recovery.py -v --tb=line 2>&1 | tee /tmp/forge-mode-a-regression.log | tail -25; echo "==="; echo "Exit: ${PIPESTATUS[0]}"

OUT
tests/integration/test_mode_a_concurrency_and_integrity.py::TestWorktreeConfinement::test_paths_outside_worktree_are_refused_by_allowlist PASSED [ 66%]
tests/integration/test_mode_a_concurrency_and_integrity.py::TestWorktreeConfinement::test_unknown_build_id_has_empty_allowlist PASSED [ 69%]
tests/integration/test_mode_a_concurrency_and_integrity.py::TestWorktreeConfinement::test_subprocess_artefact_paths_outside_allowlist_are_filtered PASSED [ 71%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[product-owner] PASSED [ 73%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[architect] PASSED [ 76%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[system-arch] PASSED [ 78%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[system-design] PASSED [ 80%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[feature-spec] PASSED [ 83%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[feature-plan] PASSED [ 85%]
tests/integration/test_mode_a_crash_recovery.py::TestCrashRecoveryAcrossSevenStages::test_retry_from_scratch_after_crash[autobuild] PASSED [ 88%]
tests/integration/test_mode_a_crash_recovery.py::TestMidAutobuildCrashAuthoritativeDurableHistory::test_crash_mid_running_wave_restarts_autobuild_from_scratch PASSED [ 90%]
tests/integration/test_mode_a_crash_recovery.py::TestNotificationPublishFailure::test_publish_failure_does_not_roll_back_stage_log PASSED [ 92%]
tests/integration/test_mode_a_crash_recovery.py::TestLongTermMemorySeedingFailure::test_ltm_seeder_failure_does_not_roll_back_stage_log PASSED [ 95%]
tests/integration/test_mode_a_crash_recovery.py::TestFakeClockCanary::test_fake_clock_returns_fixed_utc_time PASSED [ 97%]
tests/integration/test_mode_a_crash_recovery.py::TestFakeClockCanary::test_fake_clock_accepts_caller_supplied_time PASSED [100%]

=================================== FAILURES ===================================
E   TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>; this is a bug — every StageClass needs a dispatcher branch
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:1555: TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>; this is a bug — every StageClass needs a dispatcher branch
E   TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>; this is a bug — every StageClass needs a dispatcher branch
/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/pipeline/supervisor.py:1555: TypeError: Supervisor._dispatch: no routing for stage <StageClass.TASK_REVIEW: 'task-review'>; this is a bug — every StageClass needs a dispatcher branch
=========================== short test summary info ============================
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestMultiFeatureCatalogue::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
========================= 2 failed, 40 passed in 0.05s =========================
===
Exit: 0
Mode A regression confirmed red on the same routing bug. Phase 1.3 fails per its own pass criterion. I'll now run Phase 2 CLI smoke (local, doesn't trigger dispatch) to capture the CLI surface evidence before writing RESULTS.

Bash Inspect forge CLI surface for state-dir + history flags
IN
cd ~/Projects/appmilla_github/forge && forge --help 2>&1; echo "---status---"; forge status --help 2>&1; echo "---history---"; forge history --help 2>&1

OUT
Usage: forge [OPTIONS] COMMAND [ARGS]...

  Forge — pipeline orchestrator and checkpoint manager CLI.

Options:
  --config FILE  Path to forge.yaml. Defaults to ./forge.yaml when present.
  --help         Show this message and exit.

Commands:
  cancel   Cancel an active or recent build for ``identifier``.
  history  Show build + stage history (read-path bypass to SQLite).
  queue    Enqueue a build for ``feature_id`` (write-then-publish).
  skip     Skip the paused stage of an active or recent build for...
  status   Show current and recent Forge builds.
---status---
Usage: forge status [OPTIONS] [FEATURE_ID]

  Show current and recent Forge builds.

  Reads SQLite directly via ``read_only_connect()`` — does NOT touch the NATS
  bus. Per ``API-cli.md §4.2``:

  * ``forge status`` (no args): active builds + 5 most recent terminal,
  sorted newest-first. * ``forge status FEAT-XXX``: filter to that feature,
  all builds most   recent first. * ``--watch``: poll every 2s and re-render
  via ``rich.live``. * ``--full``: include up to 5 ``stage_log`` entries per
  build. * ``--json``: emit a JSON array suitable for piping.

Options:
  --watch         Poll every 2s and re-render via rich.live; exits when all
                  visible builds are terminal.
  --full          Include the last 5 stage_log entries per build (Group B
                  'Full status view caps stage detail at 5').
  --json          Emit a JSON array suitable for piping into tooling. Each row
                  matches the BuildStatusView Pydantic shape.
  --db-path FILE  Override the SQLite database path. Defaults to the
                  FORGE_DB_PATH env var or ./.forge/forge.db.
  --help          Show this message and exit.
---history---
Usage: forge history [OPTIONS]

  Show build + stage history (read-path bypass to SQLite).

  See ``docs/design/contracts/API-cli.md §5`` for the canonical spec.

Options:
  --feature TEXT            Filter to a single feature_id (e.g. FEAT-A1B2).
  --limit INTEGER           Maximum rows to return. Defaults to
                            ForgeConfig.queue.default_history_limit (50).
  --since TEXT              Filter to builds with queued_at >= ISO date (e.g.
                            2026-04-20).
  --mode [a|b|c]            Filter to builds whose pipeline mode is Mode A / B
                            / C (FEAT-FORGE-008). Default is no filter — every
                            mode is returned.
  --format [table|json|md]  Output format.  [default: table]
  --db FILE                 Path to forge.db (SQLite).  [required]
  --help                    Show this message and exit.
Bash Sample feature YAML structure + look for forge.yaml
IN
cd ~/Projects/appmilla_github/forge && cat .guardkit/features/FEAT-FORGE-008.yaml 2>&1 | head -30; echo "---"; ls forge.yaml 2>&1; cat forge.yaml 2>&1 | head -30

OUT
id: FEAT-FORGE-008
name: Mode B Feature & Mode C Review-Fix
description: "Two non-greenfield orchestration modes built on the FEAT-FORGE-001..007\
  \ substrate. Mode B drives a single new feature on an existing project (/feature-spec\
  \ \u2192 /feature-plan \u2192 autobuild \u2192 pull-request review). Mode C runs\
  \ a review-fix cycle on existing code (/task-review \u2192 /task-work \xD7 N) with\
  \ optional pull-request review when commits are pushed. 14 tasks, 7 waves, complexity\
  \ 6/10. Composition-only \u2014 no new state-machine transitions, no new dispatchers."
created: '2026-04-27T17:36:18.584931'
status: completed
complexity: 7
estimated_tasks: 14
tasks:
- id: TASK-MBC8-001
  name: Add BuildMode enum and extend StageClass with TASK_REVIEW + TASK_WORK
  file_path: tasks/backlog/mode-b-feature-and-mode-c-review-fix/TASK-MBC8-001-build-mode-and-stage-extensions.md
  complexity: 3
  dependencies: []
  status: completed
  implementation_mode: direct
  estimated_minutes: 33
  requires_infrastructure: []
  result:
    total_turns: 1
    final_decision: approved
    error: null
  turns_completed: 1
  current_turn: 0
  started_at: '2026-04-27T17:46:32.863993'
  completed_at: '2026-04-27T17:59:34.169561'
---
ls: cannot access 'forge.yaml': No such file or directory
cat: forge.yaml: No such file or directory
Bash Find config/forge.yaml example
IN
cd ~/Projects/appmilla_github/forge && find . -path ./.guardkit -prune -o -name "forge.yaml" -print 2>&1 | head; echo "---"; find . -path ./.guardkit -prune -o -name "*.yaml" -print 2>/dev/null | grep -v guardkit | grep -iE "config|forge" | head -10; echo "---repo allowlist & required fields---"; grep -rn "repo_allowlist\|feature_yaml\|FORGE_DB_PATH" src/forge/cli/ 2>&1 | head -15

OUT
---
./orchestrator-config.yaml
./features/pipeline-state-machine-and-configuration/pipeline-state-machine-and-configuration_assumptions.yaml
---repo allowlist & required fields---
src/forge/cli/main.py:23:reads its ``repo_allowlist`` and queue defaults from that object;
src/forge/cli/queue.py:14:   ``ForgeConfig.queue.repo_allowlist`` (Group C "path-allowlist
src/forge/cli/queue.py:100:#: Default location of the SQLite substrate when ``$FORGE_DB_PATH`` is
src/forge/cli/queue.py:216:    The DB path is resolved from ``$FORGE_DB_PATH`` (operator override)
src/forge/cli/queue.py:227:    raw_path = os.environ.get("FORGE_DB_PATH")
src/forge/cli/queue.py:329:                "repo_allowlist entry %r could not be resolved", entry
src/forge/cli/queue.py:467:    help="Filesystem path to the local checkout. Must match repo_allowlist.",
src/forge/cli/queue.py:477:    "feature_yaml",
src/forge/cli/queue.py:514:    feature_yaml: str,
src/forge/cli/queue.py:568:    if not _path_in_allowlist(repo_path, config.queue.repo_allowlist):
src/forge/cli/queue.py:570:            f"Repository {repo!r} is not in queue.repo_allowlist; "
src/forge/cli/queue.py:596:        feature_yaml_path=str(Path(feature_yaml)),
src/forge/cli/status.py:97:_FORGE_DB_PATH_ENV: Final[str] = "FORGE_DB_PATH"
src/forge/cli/status.py:114:    2. The ``FORGE_DB_PATH`` environment variable.
src/forge/cli/status.py:123:    env = os.environ.get(_FORGE_DB_PATH_ENV)
Bash Understand repo_allowlist resolution + config layout
IN
cd ~/Projects/appmilla_github/forge && grep -rn "repo_allowlist" src/forge/config/ 2>&1 | head -10; echo "---"; sed -n '300,340p' src/forge/cli/queue.py

OUT
src/forge/config/models.py:300:    repo_allowlist: list[Path] = Field(
---
    missing originating user.
    """
    try:
        return os.getlogin()
    except OSError:
        return os.environ.get("USER") or os.environ.get("LOGNAME") or None


def _path_in_allowlist(repo: Path, allowlist: list[Path]) -> bool:
    """Return ``True`` when ``repo`` matches an entry in ``allowlist``.

    Comparison is done against the *resolved* absolute path so a
    relative ``--repo`` is matched against canonical allowlist entries.

    A bare/empty ``allowlist`` (the schema default — see
    :class:`forge.config.models.QueueConfig`) means "no restriction" per
    the model docstring; in that case every repo passes.
    """
    if not allowlist:
        return True
    repo_resolved = Path(repo).expanduser().resolve()
    for entry in allowlist:
        try:
            entry_resolved = Path(entry).expanduser().resolve()
        except (OSError, RuntimeError):
            # Defensive — pathological symlink loops should not crash
            # the CLI. Skip the bad entry; the operator can re-run after
            # cleaning up ``forge.yaml``.
            logger.warning(
                "repo_allowlist entry %r could not be resolved", entry
            )
            continue
        if repo_resolved == entry_resolved:
            return True
        # Allow nested checkouts — a queue against
        # ``/work/repos/foo/sub`` passes when ``/work/repos/foo`` is
        # allowlisted.
        try:
            repo_resolved.relative_to(entry_resolved)
        except ValueError:
            continue
Bash Read queue command implementation
IN
cd ~/Projects/appmilla_github/forge && sed -n '470,600p' src/forge/cli/queue.py

OUT
    "--branch",
    default="main",
    show_default=True,
    help="Branch the build should target.",
)
@click.option(
    "--feature-yaml",
    "feature_yaml",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to the feature YAML spec consumed by GuardKit.",
)
@click.option(
    "--max-turns",
    type=int,
    default=None,
    help="Per-build Player-Coach turn budget. Overrides queue.default_max_turns.",
)
@click.option(
    "--timeout",
    "sdk_timeout_seconds",
    type=int,
    default=None,
    help=(
        "GuardKit autobuild SDK timeout in seconds. Overrides "
        "queue.default_sdk_timeout_seconds."
    ),
)
@click.option(
    "--correlation-id",
    "correlation_id",
    default=None,
    help=(
        "Stable identifier for tracing the build across stages. "
        "Auto-generated (uuid4) when omitted."
    ),
)
@click.pass_obj
def queue_cmd(
    config_obj: Any,
    feature_ids: tuple[str, ...],
    mode_flag: str,
    repo: str,
    branch: str,
    feature_yaml: str,
    max_turns: int | None,
    sdk_timeout_seconds: int | None,
    correlation_id: str | None,
) -> None:
    """Enqueue a build for ``feature_id`` (write-then-publish).

    See module docstring for the full step-by-step contract.
    """
    # Resolve the mode early so its validation runs *before* any side
    # effect (mirrors the validate_feature_id discipline at AC-003 / sc_003).
    build_mode = resolve_mode(mode_flag)

    # Mode B requires exactly one feature identifier (ASSUM-006: single
    # feature per Mode B build). Mode A and Mode C currently accept
    # exactly one identifier too — multi-feature inputs are rejected at
    # parse time across every mode so the persistence layer never has
    # to fan out a single CLI invocation. Mode C's single ``feature_ids``
    # member carries the *subject* identifier (e.g. a task ID or a PR
    # ID), not necessarily a FEAT-XXX value; the existing schema column
    # is feature-id-shaped which is wide enough to hold it.
    if len(feature_ids) == 0:
        # ``nargs=-1, required=True`` already enforces this; defensive.
        raise click.UsageError(
            "forge queue requires at least one feature/subject identifier"
        )
    if len(feature_ids) > 1:
        if build_mode is BuildMode.MODE_B:
            raise click.UsageError(
                f"forge queue --mode b requires exactly one feature "
                f"identifier (FEAT-FORGE-008 ASSUM-006: single feature per "
                f"Mode B build); got {len(feature_ids)}: "
                f"{list(feature_ids)!r}"
            )
        raise click.UsageError(
            f"forge queue accepts exactly one feature/subject identifier; "
            f"got {len(feature_ids)}: {list(feature_ids)!r}"
        )
    feature_id = feature_ids[0]

    config = _require_forge_config(config_obj)

    # 1. Validate feature_id BEFORE any side effect (AC-003 / sc_003).
    try:
        feature_id = validate_feature_id(feature_id)
    except InvalidIdentifierError as exc:
        click.echo(
            f"Invalid feature_id ({exc.reason}): {exc.value!r}",
            err=True,
        )
        sys.exit(EXIT_INVALID_IDENTIFIER)

    # 2. Allowlist check (AC-004 / Group C "path-allowlist refused").
    repo_path = Path(repo)
    if not _path_in_allowlist(repo_path, config.queue.repo_allowlist):
        click.echo(
            f"Repository {repo!r} is not in queue.repo_allowlist; "
            "refusing to enqueue (Group C path-allowlist refused).",
            err=True,
        )
        sys.exit(EXIT_PATH_REFUSED)

    # 3. Merge defaults (AC-005).
    effective_max_turns = (
        max_turns if max_turns is not None else config.queue.default_max_turns
    )
    effective_timeout = (
        sdk_timeout_seconds
        if sdk_timeout_seconds is not None
        else config.queue.default_sdk_timeout_seconds
    )
    effective_correlation_id = correlation_id or str(uuid.uuid4())

    # 4. Build the wire payload. ``nats_core.events`` is imported lazily
    #    so this module's import surface stays small.
    from nats_core.events import BuildQueuedPayload

    now = datetime.now(UTC)
    payload = BuildQueuedPayload(
        feature_id=feature_id,
        repo=_path_to_repo_slug(repo_path),
        branch=branch,
        feature_yaml_path=str(Path(feature_yaml)),
        max_turns=effective_max_turns,
        sdk_timeout_seconds=effective_timeout,
        triggered_by="cli",
        originating_adapter="cli-wrapper",
Bash See if queue publishes to NATS
IN
cd ~/Projects/appmilla_github/forge && sed -n '600,700p' src/forge/cli/queue.py

OUT
        originating_adapter="cli-wrapper",
        originating_user=_resolve_originating_user(),
        correlation_id=effective_correlation_id,
        requested_at=now,
        queued_at=now,
    )

    # 5. Construct the persistence facade (production: SQLite; tests:
    #    monkey-patched fake).
    persistence = make_persistence(config)

    # 6. Active in-flight check (Group C "active duplicate").
    if persistence.exists_active_build(feature_id):
        click.echo(
            f"duplicate build refused: an active build for {feature_id} "
            "is already in flight (Group C).",
            err=True,
        )
        sys.exit(EXIT_DUPLICATE)

    # 7. Write SQLite row FIRST (AC-006 / sc_002 ordering). The mode is
    #    persisted on the ``Build`` row via ``queue_build`` (alias of
    #    ``record_pending_build`` accepting an explicit ``mode=`` kwarg
    #    — TASK-MBC8-001) so crash-recovery (FEAT-FORGE-001) and the
    #    supervisor wiring from TASK-MBC8-008 see the correct mode after
    #    a restart.
    try:
        if hasattr(persistence, "queue_build"):
            persistence.queue_build(payload, mode=build_mode)
        else:
            # Fallback for in-memory test fakes that pre-date
            # TASK-MBC8-001's ``queue_build`` alias. The mode is passed
            # via the payload's open ``ConfigDict(extra="allow")`` slot
            # so the fake's ``record_pending_build`` can sniff it via
            # ``getattr(payload, "mode", None)``.
            try:
                payload.mode = build_mode.value  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                # Last-ditch: pass via a kwarg the fake may accept.
                pass
            persistence.record_pending_build(payload)
    except DuplicateBuildError as exc:
        click.echo(
            f"duplicate build refused: {exc} (Group B).",
            err=True,
        )
        sys.exit(EXIT_DUPLICATE)

    # 8. THEN publish to NATS (AC-006 second half).
    subject = f"{BUILD_QUEUED_SUBJECT_PREFIX}.{feature_id}"
    body = _envelope_bytes(payload, effective_correlation_id)
    try:
        publish(subject, body)
    except PublishError as exc:
        # 9. AC-007: do NOT roll back the SQLite row; surface a clear
        #    diagnostic on stderr identifying the messaging-layer cause
        #    (Group H "messaging unreachable") and exit 1.
        click.echo(
            f"Queued {feature_id} (build pending) but pipeline NOT NOTIFIED — "
            f"publish failed (messaging-layer): {exc}",
            err=True,
        )
        sys.exit(EXIT_PUBLISH_FAILED)

    # 10. Happy path — print operator-facing confirmation and exit 0.
    click.echo(
        f"Queued {feature_id} (build pending) "
        f"mode={build_mode.value} "
        f"correlation_id={effective_correlation_id}"
    )
    sys.exit(EXIT_OK)
Bash Find NATS publish + fake-mode env switch
IN
cd ~/Projects/appmilla_github/forge && grep -n "from\|import" src/forge/cli/queue.py | head -30; echo "---"; find src/forge -name "publish*.py" -o -name "*nats*.py" | head; echo "---"; grep -rn "FORGE_FAKE_NATS\|NATS_URL\|fake_nats\|in_memory_nats\|ENV.*NATS\|FORGE_DISABLE" src/forge/ 2>/dev/null | head -10

OUT
7:discipline (concern ``sc_002`` from TASK-REV-3EEE). The flow is, in order:
20:   ``triggered_by="cli"`` and ``originating_user`` resolved from
58:from __future__ import annotations
60:import logging
61:import os
62:import sys
63:import uuid
64:from datetime import UTC, datetime
65:from pathlib import Path
66:from typing import Any, Protocol
68:import click
70:from forge.config.models import ForgeConfig
71:from forge.lifecycle.identifiers import (
75:from forge.lifecycle.modes import BuildMode
76:from forge.lifecycle.persistence import (
108:#: Source-id stamped onto every envelope this CLI emits. Distinct from
110:#: subscribers can tell CLI-originated builds from runtime-originated
121:#: Mapping from the ``--mode`` short flag values to canonical
175:    Distinct from
177:    CLI does not need to import the NATS adapter to catch the error —
179:    the import-discipline rule (``cli/`` modules must not pull
194:    a minimal stand-in without inheriting from the full facade.
216:    The DB path is resolved from ``$FORGE_DB_PATH`` (operator override)
221:    # Imports are local so importing :mod:`forge.cli.queue` does not
223:    # ``forge --help`` fast and helps the import-discipline check.
224:    from forge.adapters.sqlite.connect import connect_writer
225:    from forge.lifecycle.migrations import apply_at_boot
262:    import asyncio  # local — keeps top-level import surface small
268:            import nats  # type: ignore[import-not-found]
272:            ) from exc
---
---
src/forge/cli/queue.py:264:    servers = os.environ.get("FORGE_NATS_URL", "nats://127.0.0.1:4222")
Bash Read publish() to confirm there is no fake-mode
IN
cd ~/Projects/appmilla_github/forge && sed -n '255,295p' src/forge/cli/queue.py

OUT
        body: Pre-serialised envelope bytes.

    Raises:
        PublishError: When the NATS connect/publish/flush fails for any
            reason. The originating exception is preserved as
            ``__cause__``.
    """
    import asyncio  # local — keeps top-level import surface small

    servers = os.environ.get("FORGE_NATS_URL", "nats://127.0.0.1:4222")

    async def _publish_once() -> None:
        try:
            import nats  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - covered via seam
            raise PublishError(
                "nats client not installed — `pip install nats-py`"
            ) from exc

        client = await nats.connect(servers=servers)
        try:
            await client.publish(subject, body)
            await client.flush()
        finally:
            await client.close()

    try:
        asyncio.run(_publish_once())
    except PublishError:
        raise
    except Exception as exc:  # noqa: BLE001 — re-raised as a domain error
        raise PublishError(f"publish to {subject!r} failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_originating_user() -> str | None:
    """Best-effort lookup of the operator's login name.
Runbook claim that Phase 2 is "no NATS" is wrong — CLI always publishes to real NATS. Let me start a local NATS via docker so I can complete Phase 2.

Bash Start NATS with JetStream for Phase 2
IN
docker run -d --name forge-validation-nats --network host nats:latest -js 2>&1 | tail -3; echo "---"; sleep 2; docker ps --format "{{.Names}}\t{{.Status}}" | grep nats; echo "---"; lsof -ti :4222 2>&1 | head -3

OUT
Digest: sha256:c6876497e2b72cfad58868914b4a688affced496f522f32c343150e135e2140d
Status: Downloaded newer image for nats:latest
9be9f56ac9638db72889aceb6e855bb9e1cc8e083ecedbbb3d39103beec4aa81
---
forge-validation-nats	Up 2 seconds
---
Bash Confirm NATS port mapping
IN
sleep 1; docker port forge-validation-nats 2>&1; echo "---"; docker exec forge-validation-nats sh -c "nats-server --version" 2>&1; echo "---"; docker logs forge-validation-nats 2>&1 | head -10

OUT
---
OCI runtime exec failed: exec failed: unable to start container process: exec: "sh": executable file not found in $PATH
---
[1] 2026/04/29 17:43:00.992570 [INF] Starting nats-server
[1] 2026/04/29 17:43:00.992645 [INF]   Version:  2.12.8
[1] 2026/04/29 17:43:00.992647 [INF]   Git:      [e9559e9]
[1] 2026/04/29 17:43:00.992648 [INF]   Name:     NCAIE5UXOJ4O5ZJCD6EQHXSALJSSSLPWLPJOMER6CN4J52QDWD7MFPLU
[1] 2026/04/29 17:43:00.992652 [INF]   Node:     QYYRrx1e
[1] 2026/04/29 17:43:00.992653 [INF]   ID:       NCAIE5UXOJ4O5ZJCD6EQHXSALJSSSLPWLPJOMER6CN4J52QDWD7MFPLU
[1] 2026/04/29 17:43:00.993547 [INF] Starting JetStream
[1] 2026/04/29 17:43:00.993557 [WRN] Temporary storage directory used, data could be lost on system reboot
[1] 2026/04/29 17:43:00.993886 [INF]     _ ___ _____ ___ _____ ___ ___   _   __  __
[1] 2026/04/29 17:43:00.993889 [INF]  _ | | __|_   _/ __|_   _| _ \ __| /_\ |  \/  |
Bash Verify NATS reachable
IN
nats server check connection --server nats://127.0.0.1:4222 2>&1 | head -5

OUT
OK Connection OK:connected to nats://127.0.0.1:4222 in 3.726711ms OK:rtt time 857.593µs OK:round trip took 0.000128s | connect_time=0.0037s;0.5000;1.0000 rtt=0.0009s;0.5000;1.0000 request_time=0.0001s;0.5000;1.0000
NATS up. Running Phase 2 with the corrected CLI flags.

Bash Phase 2.1-2.5: queue across all modes
IN
cd ~/Projects/appmilla_github/forge && export FORGE_HOME=$(mktemp -d -t forge-validation-XXXXXX) && export FORGE_DB_PATH="$FORGE_HOME/forge.db" && echo "FORGE_HOME=$FORGE_HOME" && cat > "$FORGE_HOME/feat-test-ma.yaml" <<EOF
id: FEAT-TEST-MA
name: Phase 2 Mode A smoke
description: Phase 2 CLI smoke fixture (Mode A)
EOF
cat > "$FORGE_HOME/feat-test-mb.yaml" <<EOF
id: FEAT-TEST-MB
name: Phase 2 Mode B smoke
description: Phase 2 CLI smoke fixture (Mode B)
EOF
cat > "$FORGE_HOME/task-test-mc.yaml" <<EOF
id: TASK-TEST-MC
name: Phase 2 Mode C smoke
description: Phase 2 CLI smoke fixture (Mode C)
EOF
echo "=== Phase 2.2 Mode A queue ==="
forge queue FEAT-TEST-MA --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode a --feature-yaml "$FORGE_HOME/feat-test-ma.yaml" 2>&1 | tee /tmp/forge-cli-mode-a.log
echo "Exit: $?"
echo "=== Phase 2.3 Mode B queue ==="
forge queue FEAT-TEST-MB --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode b --feature-yaml "$FORGE_HOME/feat-test-mb.yaml" 2>&1 | tee /tmp/forge-cli-mode-b.log
echo "Exit: $?"
echo "=== Phase 2.5 Mode C queue ==="
forge queue TASK-TEST-MC --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode c --feature-yaml "$FORGE_HOME/task-test-mc.yaml" 2>&1 | tee /tmp/forge-cli-mode-c.log
echo "Exit: $?"
echo "FORGE_HOME=$FORGE_HOME" > /tmp/forge-validation-home

OUT
FORGE_HOME=/tmp/forge-validation-zevlB3
=== Phase 2.2 Mode A queue ===
Usage: forge queue [OPTIONS] FEATURE_IDS...
Try 'forge queue --help' for help.

Error: forge queue requires a forge.yaml — pass --config <path> or run from a directory containing forge.yaml
Exit: 0
=== Phase 2.3 Mode B queue ===
Usage: forge queue [OPTIONS] FEATURE_IDS...
Try 'forge queue --help' for help.

Error: forge queue requires a forge.yaml — pass --config <path> or run from a directory containing forge.yaml
Exit: 0
=== Phase 2.5 Mode C queue ===
Usage: forge queue [OPTIONS] FEATURE_IDS...
Try 'forge queue --help' for help.

Error: forge queue requires a forge.yaml — pass --config <path> or run from a directory containing forge.yaml
Exit: 0
Bash Identify minimum required forge.yaml fields
IN
cd ~/Projects/appmilla_github/forge && grep -A20 "class ForgeConfig\|class QueueConfig\|class ApprovalConfig" src/forge/config/models.py | head -80

OUT
class ApprovalConfig(BaseModel):
    """Configuration for the approval / pause-resume protocol (FEAT-FORGE-004).

    Defaults are pinned to ASSUM-001 / ASSUM-002 of the
    Confidence-Gated Checkpoint Protocol assumptions manifest. Operators may
    override either field in ``forge.yaml`` but the defaults must continue to
    match the assumptions manifest so this in-memory schema stays the
    canonical source of truth for both the publisher (TASK-CGCP-006) and the
    state machine (TASK-CGCP-010).

    Note (ASSUM-003 deferral): The terminal behaviour applied when an
    approval pause reaches ``max_wait_seconds`` without a response —
    cancel / escalate / fail-open — is **explicitly out of scope** for this
    model and is deferred to the ``forge-pipeline-config`` feature. Do not
    add a ceiling-fallback field here; that decision belongs with the
    state-machine configuration, not with the wait-time settings.
    """

    model_config = ConfigDict(extra="forbid")

    default_wait_seconds: int = Field(
--
class QueueConfig(BaseModel):
    """Configuration for the ``forge queue`` lifecycle (FEAT-FORGE-001 / PSM).

    Defaults are anchored to the Pipeline State Machine assumptions manifest
    (ASSUM-001 — minimum turn budget = 1). Operators may override any field
    in ``forge.yaml`` but the defaults must continue to match the assumptions
    manifest so this in-memory schema stays the canonical source of truth for
    downstream consumers (TASK-PSM-008/009/010/011).

    The ``ge=1`` validator on ``default_max_turns`` gives the CLI's
    "turn budget < 1 rejected" rejection branch automatically — no extra
    branch is required at the call site.
    """

    model_config = ConfigDict(extra="forbid")

    default_max_turns: int = Field(
        default=5,
        ge=1,
        description=(
            "ASSUM-001 (PSM) — default per-build turn budget. Must be at "
--
class ForgeConfig(BaseModel):
    """Root model for ``forge.yaml``.

    ``fleet``, ``pipeline``, ``approval`` and ``queue`` are optional with
    sensible defaults so that a minimal ``forge.yaml`` only needs to declare
    the required ``permissions`` section. ``permissions`` itself is required
    because there is no safe default filesystem allowlist.
    """

    model_config = ConfigDict(extra="forbid")

    fleet: FleetConfig = Field(default_factory=FleetConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    permissions: PermissionsConfig = Field(
        ...,
        description=(
            "Required. Operators must explicitly declare permissions — there "
            "is no safe default filesystem allowlist."
        ),
Bash PermissionsConfig fields
IN
cd ~/Projects/appmilla_github/forge && grep -A25 "class PermissionsConfig" src/forge/config/models.py | head -30

OUT
class PermissionsConfig(BaseModel):
    """Top-level permissions block. Currently only filesystem permissions exist."""

    model_config = ConfigDict(extra="forbid")

    filesystem: FilesystemPermissions = Field(
        ...,
        description="Filesystem allowlist enforced by pipeline_consumer.",
    )


class QueueConfig(BaseModel):
    """Configuration for the ``forge queue`` lifecycle (FEAT-FORGE-001 / PSM).

    Defaults are anchored to the Pipeline State Machine assumptions manifest
    (ASSUM-001 — minimum turn budget = 1). Operators may override any field
    in ``forge.yaml`` but the defaults must continue to match the assumptions
    manifest so this in-memory schema stays the canonical source of truth for
    downstream consumers (TASK-PSM-008/009/010/011).

    The ``ge=1`` validator on ``default_max_turns`` gives the CLI's
    "turn budget < 1 rejected" rejection branch automatically — no extra
    branch is required at the call site.
    """

    model_config = ConfigDict(extra="forbid")
Bash FilesystemPermissions fields
IN
cd ~/Projects/appmilla_github/forge && grep -A15 "class FilesystemPermissions" src/forge/config/models.py | head -20

OUT
class FilesystemPermissions(BaseModel):
    """Filesystem permissions enforced by ``pipeline_consumer``.

    ``allowlist`` is **required** — the system intentionally has no implicit
    default so that an operator misconfiguration cannot accidentally widen
    Forge's authorised filesystem footprint. All entries must be absolute
    paths (validator below).
    """

    model_config = ConfigDict(extra="forbid")

    allowlist: list[Path] = Field(
        ...,
        description=(
            "Absolute filesystem paths the pipeline consumer may read or "
            "write. Builds targeting any path outside the allowlist are "
Bash Phase 2.2-2.5 retry with forge.yaml
IN
cd ~/Projects/appmilla_github/forge && export FORGE_HOME=$(cat /tmp/forge-validation-home | cut -d= -f2) && export FORGE_DB_PATH="$FORGE_HOME/forge.db" && cat > "$FORGE_HOME/forge.yaml" <<EOF
permissions:
  filesystem:
    allowlist:
      - /home/richardwoollcott/Projects/appmilla_github/forge
queue:
  default_max_turns: 5
  default_sdk_timeout_seconds: 600
EOF
echo "=== forge.yaml ==="
cat "$FORGE_HOME/forge.yaml"
echo "=== Phase 2.2 Mode A queue ==="
forge --config "$FORGE_HOME/forge.yaml" queue FEAT-TEST-MA --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode a --feature-yaml "$FORGE_HOME/feat-test-ma.yaml" 2>&1 | tee /tmp/forge-cli-mode-a.log
echo "Exit: $?"
echo "=== Phase 2.3 Mode B queue ==="
forge --config "$FORGE_HOME/forge.yaml" queue FEAT-TEST-MB --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode b --feature-yaml "$FORGE_HOME/feat-test-mb.yaml" 2>&1 | tee /tmp/forge-cli-mode-b.log
echo "Exit: $?"
echo "=== Phase 2.5 Mode C queue ==="
forge --config "$FORGE_HOME/forge.yaml" queue TASK-TEST-MC --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode c --feature-yaml "$FORGE_HOME/task-test-mc.yaml" 2>&1 | tee /tmp/forge-cli-mode-c.log
echo "Exit: $?"

OUT
=== forge.yaml ===
permissions:
  filesystem:
    allowlist:
      - /home/richardwoollcott/Projects/appmilla_github/forge
queue:
  default_max_turns: 5
  default_sdk_timeout_seconds: 600
=== Phase 2.2 Mode A queue ===
Traceback (most recent call last):
  File "/home/richardwoollcott/.local/bin/forge", line 8, in <module>
    sys.exit(main())
             ^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1485, in __call__
    return self.main(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1406, in main
    rv = self.invoke(ctx)
         ^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1873, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1269, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 824, in invoke
    return callback(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/decorators.py", line 46, in new_func
    return f(get_current_context().obj, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/cli/queue.py", line 592, in queue_cmd
    payload = BuildQueuedPayload(
              ^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/pydantic/main.py", line 250, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pydantic_core._pydantic_core.ValidationError: 1 validation error for BuildQueuedPayload
feature_id
  Value error, feature_id must match ^FEAT-[A-Z0-9]{3,12}$, got 'FEAT-TEST-MA' [type=value_error, input_value='FEAT-TEST-MA', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/value_error
Exit: 0
=== Phase 2.3 Mode B queue ===
Traceback (most recent call last):
  File "/home/richardwoollcott/.local/bin/forge", line 8, in <module>
    sys.exit(main())
             ^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1485, in __call__
    return self.main(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1406, in main
    rv = self.invoke(ctx)
         ^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1873, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1269, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 824, in invoke
    return callback(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/decorators.py", line 46, in new_func
    return f(get_current_context().obj, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/cli/queue.py", line 592, in queue_cmd
    payload = BuildQueuedPayload(
              ^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/pydantic/main.py", line 250, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pydantic_core._pydantic_core.ValidationError: 1 validation error for BuildQueuedPayload
feature_id
  Value error, feature_id must match ^FEAT-[A-Z0-9]{3,12}$, got 'FEAT-TEST-MB' [type=value_error, input_value='FEAT-TEST-MB', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/value_error
Exit: 0
=== Phase 2.5 Mode C queue ===
Traceback (most recent call last):
  File "/home/richardwoollcott/.local/bin/forge", line 8, in <module>
    sys.exit(main())
             ^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1485, in __call__
    return self.main(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1406, in main
    rv = self.invoke(ctx)
         ^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1873, in invoke
    return _process_result(sub_ctx.command.invoke(sub_ctx))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 1269, in invoke
    return ctx.invoke(self.callback, **ctx.params)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/core.py", line 824, in invoke
    return callback(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/click/decorators.py", line 46, in new_func
    return f(get_current_context().obj, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/Projects/appmilla_github/forge/src/forge/cli/queue.py", line 592, in queue_cmd
    payload = BuildQueuedPayload(
              ^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/pydantic/main.py", line 250, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pydantic_core._pydantic_core.ValidationError: 1 validation error for BuildQueuedPayload
feature_id
  Value error, feature_id must match ^FEAT-[A-Z0-9]{3,12}$, got 'TASK-TEST-MC' [type=value_error, input_value='TASK-TEST-MC', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/value_error
Exit: 0
Bash Compare CLI validator vs wire-payload validator
IN
cd ~/Projects/appmilla_github/forge && grep -n "validate_feature_id\|FEAT-\|^.*regex\|pattern.*FEAT" src/forge/lifecycle/identifiers.py 2>&1 | head -15; echo "---"; grep -n "regex\|pattern\|FEAT-" /home/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events*.py 2>&1 | head -10; echo "---"; grep -rn "feature_id must match\|TASK-.*pattern\|FEAT-\[A-Z0-9\]" /home/richardwoollcott/Projects/appmilla_github/nats-core/src/ 2>/dev/null | head -10

OUT
21:* :func:`validate_feature_id` — decode-then-allowlist validator.
39:    "validate_feature_id",
64:    """Raised when :func:`validate_feature_id` rejects an input.
85:def validate_feature_id(s: str) -> str:
148:        return value of :func:`validate_feature_id` rather than raw
---
ugrep: warning: /home/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events*.py: No such file or directory
---
/home/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/_pipeline.py:27:FEATURE_ID_PATTERN = re.compile(r"^FEAT-[A-Z0-9]{3,12}$")
/home/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/_pipeline.py:379:            msg = f"feature_id must match {FEATURE_ID_PATTERN.pattern}, got {v!r}"
Real bug found: wire-schema regex ^FEAT-[A-Z0-9]{3,12}$ rejects both hyphenated suffixes AND TASK-* IDs that Mode C is supposed to accept. Retrying Phase 2 with valid IDs and documenting the Mode C contradiction.

Bash Phase 2.2-2.5 with valid wire-schema IDs
IN
cd ~/Projects/appmilla_github/forge && export FORGE_HOME=$(cat /tmp/forge-validation-home | cut -d= -f2) && export FORGE_DB_PATH="$FORGE_HOME/forge.db" && rm -f "$FORGE_DB_PATH" && cat > "$FORGE_HOME/feat-testma.yaml" <<EOF
id: FEAT-TESTMA
name: Phase 2 Mode A smoke
EOF
cat > "$FORGE_HOME/feat-testmb.yaml" <<EOF
id: FEAT-TESTMB
name: Phase 2 Mode B smoke
EOF
cat > "$FORGE_HOME/feat-testmc.yaml" <<EOF
id: FEAT-TESTMC
name: Phase 2 Mode C smoke (using FEAT-* because TASK-* fails wire validation)
EOF
echo "=== Phase 2.2 Mode A queue ==="
forge --config "$FORGE_HOME/forge.yaml" queue FEAT-TESTMA --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode a --feature-yaml "$FORGE_HOME/feat-testma.yaml" 2>&1 | tee /tmp/forge-cli-mode-a.log
echo "Exit: $?"
echo "=== Phase 2.3 Mode B queue ==="
forge --config "$FORGE_HOME/forge.yaml" queue FEAT-TESTMB --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode b --feature-yaml "$FORGE_HOME/feat-testmb.yaml" 2>&1 | tee /tmp/forge-cli-mode-b.log
echo "Exit: $?"
echo "=== Phase 2.5 Mode C queue ==="
forge --config "$FORGE_HOME/forge.yaml" queue FEAT-TESTMC --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode c --feature-yaml "$FORGE_HOME/feat-testmc.yaml" 2>&1 | tee /tmp/forge-cli-mode-c.log
echo "Exit: $?"
echo "=== Phase 2.5b Mode C with TASK-* (expected: rejected by wire schema) ==="
cat > "$FORGE_HOME/task-testmc.yaml" <<EOF
id: TASK-TESTMC
name: Phase 2 Mode C TASK-* smoke
EOF
forge --config "$FORGE_HOME/forge.yaml" queue TASK-TESTMC --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode c --feature-yaml "$FORGE_HOME/task-testmc.yaml" 2>&1 | tail -8 | tee /tmp/forge-cli-mode-c-task.log
echo "Exit: $?"

OUT
=== Phase 2.2 Mode A queue ===
Queued FEAT-TESTMA (build pending) mode=mode-a correlation_id=9158d3b9-8e4d-4743-a6ef-425767401891
Exit: 0
=== Phase 2.3 Mode B queue ===
Queued FEAT-TESTMB (build pending) mode=mode-b correlation_id=aa696d7c-3d85-4642-99e7-600d551b2bfa
Exit: 0
=== Phase 2.5 Mode C queue ===
Queued FEAT-TESTMC (build pending) mode=mode-c correlation_id=55c170d0-d324-4a44-9591-43b36478dd54
Exit: 0
=== Phase 2.5b Mode C with TASK-* (expected: rejected by wire schema) ===
              ^^^^^^^^^^^^^^^^^^^
  File "/home/richardwoollcott/.local/lib/python3.12/site-packages/pydantic/main.py", line 250, in __init__
    validated_self = self.__pydantic_validator__.validate_python(data, self_instance=self)
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
pydantic_core._pydantic_core.ValidationError: 1 validation error for BuildQueuedPayload
feature_id
  Value error, feature_id must match ^FEAT-[A-Z0-9]{3,12}$, got 'TASK-TESTMC' [type=value_error, input_value='TASK-TESTMC', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/value_error
Exit: 0
Bash Phase 2.x: status + mode-filtered history
IN
cd ~/Projects/appmilla_github/forge && export FORGE_HOME=$(cat /tmp/forge-validation-home | cut -d= -f2) && export FORGE_DB_PATH="$FORGE_HOME/forge.db" && echo "=== Phase 2.x status ===" && forge --config "$FORGE_HOME/forge.yaml" status --db-path "$FORGE_DB_PATH" 2>&1 | tee /tmp/forge-cli-status.log
echo "=== Phase 2.6 mode-filtered history ==="
echo "--- Mode A only ---"
forge --config "$FORGE_HOME/forge.yaml" history --mode a --db "$FORGE_DB_PATH" 2>&1 | tee /tmp/forge-cli-history-a.log
echo "--- Mode B only ---"
forge --config "$FORGE_HOME/forge.yaml" history --mode b --db "$FORGE_DB_PATH" 2>&1 | tee /tmp/forge-cli-history-b.log
echo "--- Mode C only ---"
forge --config "$FORGE_HOME/forge.yaml" history --mode c --db "$FORGE_DB_PATH" 2>&1 | tee /tmp/forge-cli-history-c.log
echo "--- All modes ---"
forge --config "$FORGE_HOME/forge.yaml" history --db "$FORGE_DB_PATH" 2>&1 | tee /tmp/forge-cli-history-all.log

OUT
=== Phase 2.x status ===
                                       Forge build status                                       
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓
┃ BUILD                            ┃ FEATURE     ┃ MODE   ┃ STATUS ┃ STAGE ┃ STARTED ┃ ELAPSED ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━━━┩
│ build-FEAT-TESTMC-20260429174421 │ FEAT-TESTMC │ mode-c │ QUEUED │ —     │ —       │ —       │
│ build-FEAT-TESTMB-20260429174420 │ FEAT-TESTMB │ mode-b │ QUEUED │ —     │ —       │ —       │
│ build-FEAT-TESTMA-20260429174420 │ FEAT-TESTMA │ mode-a │ QUEUED │ —     │ —       │ —       │
└──────────────────────────────────┴─────────────┴────────┴────────┴───────┴─────────┴─────────┘
=== Phase 2.6 mode-filtered history ===
--- Mode A only ---
BUILD                                            FEATURE        STATUS      QUEUED                
--------------------------------------------------------------------------------------------------
build-FEAT-TESTMA-20260429174420                 FEAT-TESTMA    QUEUED      2026-04-29 17:44:20 UTC
--- Mode B only ---
BUILD                                            FEATURE        STATUS      QUEUED                
--------------------------------------------------------------------------------------------------
build-FEAT-TESTMB-20260429174420                 FEAT-TESTMB    QUEUED      2026-04-29 17:44:20 UTC
--- Mode C only ---
BUILD                                            FEATURE        STATUS      QUEUED                
--------------------------------------------------------------------------------------------------
build-FEAT-TESTMC-20260429174421                 FEAT-TESTMC    QUEUED      2026-04-29 17:44:21 UTC
--- All modes ---
BUILD                                            FEATURE        STATUS      QUEUED                
--------------------------------------------------------------------------------------------------
build-FEAT-TESTMC-20260429174421                 FEAT-TESTMC    QUEUED      2026-04-29 17:44:21 UTC
build-FEAT-TESTMB-20260429174420                 FEAT-TESTMB    QUEUED      2026-04-29 17:44:20 UTC
build-FEAT-TESTMA-20260429174420                 FEAT-TESTMA    QUEUED      2026-04-29 17:44:20 UTC
Bash Phase 2.4 multi-feature reject + 2.7 constitutional regression
IN
cd ~/Projects/appmilla_github/forge && export FORGE_HOME=$(cat /tmp/forge-validation-home | cut -d= -f2) && export FORGE_DB_PATH="$FORGE_HOME/forge.db" && echo "=== Phase 2.4 Mode B multi-feature reject ===" && forge --config "$FORGE_HOME/forge.yaml" queue FEAT-MULT1 FEAT-MULT2 --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode b --feature-yaml "$FORGE_HOME/feat-testmb.yaml" 2>&1 | tee /tmp/mb-multi-reject.log
echo "Exit: $?"
echo "=== Phase 2.7 constitutional regression suite ==="
pytest tests/integration/test_constitutional_regression.py -v --tb=short 2>&1 | tee /tmp/forge-constitutional.log | tail -25

OUT
=== Phase 2.4 Mode B multi-feature reject ===
Usage: forge queue [OPTIONS] FEATURE_IDS...
Try 'forge queue --help' for help.

Error: forge queue --mode b requires exactly one feature identifier (FEAT-FORGE-008 ASSUM-006: single feature per Mode B build); got 2: ['FEAT-MULT1', 'FEAT-MULT2']
Exit: 0
=== Phase 2.7 constitutional regression suite ===
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/richardwoollcott/Projects/appmilla_github/forge
configfile: pyproject.toml
plugins: asyncio-1.3.0, anyio-4.12.1, cov-7.0.0, langsmith-0.7.36, bdd-8.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 5 items

tests/integration/test_constitutional_regression.py::TestExecutorBranchAloneIsSufficient::test_protected_target_yields_mandatory_human_approval_even_with_permissive_model[create_pr_after_review] PASSED [ 20%]
tests/integration/test_constitutional_regression.py::TestExecutorBranchAloneIsSufficient::test_protected_target_yields_mandatory_human_approval_even_with_permissive_model[review_pr] PASSED [ 40%]
tests/integration/test_constitutional_regression.py::TestExecutorBranchAloneIsSufficient::test_unprotected_target_falls_through_to_model PASSED [ 60%]
tests/integration/test_constitutional_regression.py::TestPromptLayerAloneIsSufficient::test_protected_target_yields_mandatory_human_approval_when_executor_bypassed[create_pr_after_review] PASSED [ 80%]
tests/integration/test_constitutional_regression.py::TestPromptLayerAloneIsSufficient::test_protected_target_yields_mandatory_human_approval_when_executor_bypassed[review_pr] PASSED [100%]

============================== 5 passed in 0.05s ===============================
Phase 2.4 ✅ and 2.7 ✅. Let me capture the Mode B/C integration smoke results too before writing RESULTS.

Bash Capture Mode B/C smoke + cross-mode + crash recovery results
IN
cd ~/Projects/appmilla_github/forge && pytest tests/integration/test_mode_b_smoke_e2e.py tests/integration/test_mode_c_smoke_e2e.py tests/integration/test_cross_mode_concurrency.py tests/integration/test_mode_b_c_crash_recovery.py --tb=line 2>&1 | tee /tmp/forge-mode-bc-smoke.log | tail -20; echo "==="

OUT
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0
rootdir: /home/richardwoollcott/Projects/appmilla_github/forge
configfile: pyproject.toml
plugins: asyncio-1.3.0, anyio-4.12.1, cov-7.0.0, langsmith-0.7.36, bdd-8.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 68 items

tests/integration/test_mode_b_smoke_e2e.py ...................           [ 27%]
tests/integration/test_mode_c_smoke_e2e.py .................             [ 52%]
tests/integration/test_cross_mode_concurrency.py ...................     [ 80%]
tests/integration/test_mode_b_c_crash_recovery.py .............          [100%]

============================== 68 passed in 0.24s ==============================
===
Bash Phase 3.3 Option A: NATS routing + durable-decision tests (without live NATS)
IN
cd ~/Projects/appmilla_github/forge && pytest tests/integration/test_per_build_routing.py tests/integration/test_durable_decision_on_publish_failure.py --tb=line 2>&1 | tail -10

OUT
rootdir: /home/richardwoollcott/Projects/appmilla_github/forge
configfile: pyproject.toml
plugins: asyncio-1.3.0, anyio-4.12.1, cov-7.0.0, langsmith-0.7.36, bdd-8.1.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 5 items

tests/integration/test_per_build_routing.py ..                           [ 40%]
tests/integration/test_durable_decision_on_publish_failure.py ...        [100%]

============================== 5 passed in 0.02s ===============================
Update Todos

Phase 0: Pre-flight checks (branch, artefacts, env, CLI)

Phase 1: Local pytest gate (full suite, BDD-008, Mode A regression)

Phase 2: CLI smoke (forge queue across modes, with local NATS)

Phase 3: NATS pipeline-event observation (quick: queue-time event capture)

Phases 4-6: deferred per runbook §1.3 hard-stop on Mode A regression

Phase 7: Write RESULTS file + decision
Bash Phase 3.1-3.2: capture pipeline.* events from a Mode B queue
IN
timeout 8 nats sub 'pipeline.>' --raw 2>&1 > /tmp/forge-nats-sub.log &
SUBPID=$!
sleep 1
cd ~/Projects/appmilla_github/forge && export FORGE_HOME=$(cat /tmp/forge-validation-home | cut -d= -f2) && export FORGE_DB_PATH="$FORGE_HOME/forge.db" && cat > "$FORGE_HOME/feat-natscheck.yaml" <<EOF
id: FEAT-NATSCHECK
name: NATS observation fixture
EOF
echo "=== Phase 3.1-3.2 pipeline event observation ==="
forge --config "$FORGE_HOME/forge.yaml" queue FEAT-NATSCHECK --repo /home/richardwoollcott/Projects/appmilla_github/forge --branch main --mode b --feature-yaml "$FORGE_HOME/feat-natscheck.yaml" 2>&1
sleep 3
wait $SUBPID 2>/dev/null
echo "--- Captured pipeline events ---"
cat /tmp/forge-nats-sub.log | head -30
echo "==="

OUT
=== Phase 3.1-3.2 pipeline event observation ===
Queued FEAT-NATSCHECK (build pending) mode=mode-b correlation_id=12c1be2b-6a04-483d-a7b1-8e5f6874b82e
--- Captured pipeline events ---
{"message_id":"23692e20-65d3-4bcb-bb61-f9f36536008a","timestamp":"2026-04-29T17:45:10.258997Z","version":"1.0","source_id":"forge-cli","event_type":"build_queued","project":null,"correlation_id":"12c1be2b-6a04-483d-a7b1-8e5f6874b82e","payload":{"feature_id":"FEAT-NATSCHECK","repo":"appmilla_github/forge","branch":"main","feature_yaml_path":"/tmp/forge-validation-zevlB3/feat-natscheck.yaml","max_turns":5,"sdk_timeout_seconds":600,"wave_gating":false,"config_overrides":null,"triggered_by":"cli","originating_adapter":"cli-wrapper","originating_user":"richardwoollcott","correlation_id":"12c1be2b-6a04-483d-a7b1-8e5f6874b82e","parent_request_id":null,"retry_count":0,"requested_at":"2026-04-29T17:45:10.252929Z","queued_at":"2026-04-29T17:45:10.252929Z"}}
===
Phase 3.1 confirmed: pipeline event with threaded correlation_id arrived. Now writing the RESULTS file. Cleaning up first.

Bash Collect headline metrics for RESULTS
IN
grep -c "passed" /tmp/forge-pytest-phase1.log; grep -c "failed" /tmp/forge-pytest-phase1.log; grep -E "passed|failed|error" /tmp/forge-pytest-phase1.log | tail -3; echo "---"; tail -3 /tmp/forge-bdd-008.log; echo "---"; tail -3 /tmp/forge-mode-a-regression.log; echo "---"; cd ~/Projects/appmilla_github/forge && git log --oneline -1

OUT
1
1
4 failed, 3757 passed, 1 skipped, 132 warnings in 5.49s
---

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 64 passed, 32 warnings in 0.17s ========================
---
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestMultiFeatureCatalogue::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py::TestCorrelationThreading::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
========================= 2 failed, 40 passed in 0.05s =========================
---
5e5cc73 Updated history
Bash Cleanup tmp + NATS docker
IN
FORGE_HOME=$(cat /tmp/forge-validation-home | cut -d= -f2); rm -rf "$FORGE_HOME"; rm -f /tmp/forge-validation-home; docker stop forge-validation-nats 2>&1 | tail -1; docker rm forge-validation-nats 2>&1 | tail -1

OUT
forge-validation-nats
forge-validation-nats
Write RESULTS-FEAT-FORGE-008-validation.md
126 lines
# Results: FEAT-FORGE-008 Validation

**Executed:** 2026-04-29 (single session, ~30 min)
**Operator:** Richard Woollcott (via Claude Code on `promaxgb10-41b1`)
**Commit at start:** `5e5cc73 Updated history` (`main` HEAD; `2f13eac` FEAT-FORGE-008 merge present in history)
**Host used:** `promaxgb10-41b1` is `127.0.0.1` per `/etc/hosts` — i.e. this *is* the GB10 host, so Phases 0–3 ran in the same environment. Phases 4–6 were not executed (see "Hard-stop" below).

## Hard-stop rationale

The runbook's own §1.3 pass criterion is:

> All Mode A tests green. **If any are red, FEAT-FORGE-008 broke the Mode A branch in `Supervisor.next_turn` — stop and triage immediately.**

Phase 1 produced two red Mode A integration tests with the exact regression signature §1.3 calls out (`Supervisor._dispatch` has no routing branch for `StageClass.TASK_REVIEW`). Per the runbook contract, later phases were not run because they would only add noise.

In addition, Phase 0.6's persistent JetStream-provisioned NATS does not exist on this host (no `nats.service`, no docker container with the standard streams pre-provisioned). A throwaway `nats:latest` was started for Phases 2–3 only; running the LES1 production-image gates (Phase 6) requires the canonical provisioned NATS plus a forge production Dockerfile (none ships in this repo).

## Per-gate outcomes

| Phase | Gate | Outcome | Evidence |
|-------|------|---------|----------|
| 0.1   | Working tree clean on `main`; FEAT-FORGE-008 merge `2f13eac` in history | ✅ | `git status` / `git log --oneline` |
| 0.2   | FEAT-FORGE-008 artefacts present (`.guardkit/features/FEAT-FORGE-008.yaml`, IMPLEMENTATION-GUIDE, `.feature` file) | ✅ | `ls` |
| 0.3   | Four new Mode B/C integration test files present | ✅ | `ls tests/integration/test_mode_*` |
| 0.4   | Editable install + dev/providers extras | ⚠️ | Existing user-site editable forge install pointed at deleted worktree `.guardkit/worktrees/FEAT-FORGE-005`; rewired with `pip install --user --break-system-packages --force-reinstall --no-deps -e .` after pip refused PEP 668 install. Plain `pip install -e '.[providers,dev]'` in a fresh venv FAILS because `nats-core>=0.2.0,<0.3` only resolves via `[tool.uv.sources]` (sibling `../nats-core`) which pip ignores — `uv` is required for the runbook command verbatim, but `uv` is not installed. |
| 0.5   | `forge queue --help` shows `--mode a\|b\|c` flag | ✅ | `forge queue --help` output |
| 0.6   | NATS reachable on host | ❌ | No `nats.service`, no NATS container running. Started ephemeral `nats:latest -js` for Phases 2–3 only. |
| 1.1   | Full pytest suite green | ❌ | `/tmp/forge-pytest-phase1.log` — 3757 passed, **4 failed**, 1 skipped (after `--ignore=tests/bdd/test_infrastructure_coordination.py`; that file has a hard collection error — see follow-up F008-VAL-001). |
| 1.2   | FEAT-FORGE-008 BDD bindings green | ✅ | `/tmp/forge-bdd-008.log` — 64 passed (runbook predicted 56). |
| 1.3   | Mode A regression byte-identical | ❌ | `/tmp/forge-mode-a-regression.log` — **2 failed / 40 passed**. Same root cause as 1.1: `Supervisor._dispatch` has no `StageClass.TASK_REVIEW` branch. |
| 2.2   | Mode A queue smoke (`forge queue ... --mode a`) | ✅ | `/tmp/forge-cli-mode-a.log` — `mode=mode-a`, correlation_id assigned. |
| 2.3   | Mode B queue smoke (NEW) | ✅ | `/tmp/forge-cli-mode-b.log` — `mode=mode-b`. |
| 2.4   | Mode B multi-feature reject (ASSUM-006) | ✅ | `/tmp/mb-multi-reject.log` — exit non-zero, error message cites "FEAT-FORGE-008 ASSUM-006: single feature per Mode B build". |
| 2.5   | Mode C queue smoke (NEW) | ⚠️ | `/tmp/forge-cli-mode-c.log` — works with a `FEAT-*` identifier. **`TASK-*` IDs are rejected** by wire-schema regex `^FEAT-[A-Z0-9]{3,12}$` in `nats_core.events._pipeline.BuildQueuedPayload`. Mode C accepting `TASK-*` per FEAT-FORGE-008 ASSUM-004 contradicts the wire schema. See follow-up F008-VAL-002. Evidence: `/tmp/forge-cli-mode-c-task.log`. |
| 2.6   | `forge history --mode a\|b\|c` filtering | ✅ | `/tmp/forge-cli-history-{a,b,c,all}.log` — each filter returns exactly the matching build; un-filtered returns all three. |
| 2.7   | Constitutional skip refusal (executor-layer) | ✅ | `/tmp/forge-constitutional.log` — 5/5 passed. |
| 3.1–3.2 | Pipeline `build-queued` event observed via `nats sub 'pipeline.>'` | ✅ | `/tmp/forge-nats-sub.log` — `pipeline.build-queued.FEAT-NATSCHECK` envelope captured; envelope-level `correlation_id` matches CLI-emitted UUID. |
| 3.3   | NATS routing + durable-decision integration tests | ✅ | 5/5 passed (`tests/integration/test_per_build_routing.py` + `test_durable_decision_on_publish_failure.py`). |
| 4.x–6.x | Checkpoint, degraded-mode, LES1 production-image gates | ⏸ deferred | Per Phase 1.3 hard-stop rule + Phase 0.6 prerequisite (no provisioned NATS, no forge `Dockerfile`). |
| 6.4   | Canonical-freeze walkthrough on clean MacBook + GB10 | ⏸ deferred | Cannot run a useful walkthrough until the four red gates are fixed and the runbook gaps in this RESULTS file are folded back. |

### Headline pytest failure modes (1.1)

```
FAILED tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent
  AssertionError: second apply must not duplicate the seed row
  rows == [(1,), (2,)] but expected [(1,)]
  → A new schema_version v2 row is inserted on every boot. The migration
    that adds v2 (almost certainly TASK-MBC8-001's mode column or
    TASK-MBC8-006's TASK_REVIEW/TASK_WORK stage entries) is non-idempotent.

FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership
       ::test_no_other_module_in_forge_constructs_evidence_priors
  AssertionError: Other modules reconstruct details shape (AC-008):
    [PosixPath('src/forge/lifecycle/recovery.py')]
  → AC-008 of FEAT-FORGE-004 says only `approval_publisher.py` may
    construct the `evidence_priors` dict. FEAT-FORGE-008's recovery code
    open-codes the shape in lifecycle/recovery.py.

FAILED tests/integration/test_mode_a_concurrency_and_integrity.py
       ::TestMultiFeatureCatalogue
       ::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py
       ::TestCorrelationThreading
       ::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
  TypeError: Supervisor._dispatch: no routing for stage
            <StageClass.TASK_REVIEW: 'task-review'>
  → src/forge/pipeline/supervisor.py:1555. Mode A reaches `task-review`
    via the canonical model now that TASK_REVIEW was added to StageClass
    (TASK-MBC8-001), but the dispatch routing in `_dispatch` was only
    extended for the Mode-B/C-specific helpers. Mode A's path through
    `_dispatch` falls off the end and raises.
```

## Runbook gaps discovered during execution

These are the blocks that needed manual edits (per LES1 §8 — runbook copy-paste blocks are code).

| Phase | Block | What needed adjustment | Suggested runbook fix |
|-------|-------|------------------------|----------------------|
| 0.4   | `pip install -e '.[providers,dev]'` | Plain pip cannot resolve `nats-core>=0.2.0` because `[tool.uv.sources]` (sibling `../nats-core`) is `uv`-only. The runbook also needs to install `uv` first or call out the user-site rewire trick. PEP 668 also blocks the system-pip path on Ubuntu 24.04 unless `--break-system-packages` is used. | Pin to `uv pip install -e ".[providers,dev]"` and add an explicit "install `uv` first" step. Document the `--break-system-packages` fallback for non-uv flow. Also instruct operators to `pip install --user --force-reinstall --no-deps -e .` if a stale editable install points to a deleted worktree (the FEAT-FORGE-005 trap). |
| 0.5   | `which forge` | `forge` is installed by `pip install --user`, which puts the script in `~/.local/bin`. On a fresh shell that may not be on PATH. | Add `~/.local/bin` PATH check with the install instruction. |
| 0.6   | NATS reachability check | The runbook assumes a provisioned JetStream NATS is already up. There is none on this host. | Add a "if no NATS, run `docker run -d --network host nats:latest -js` for Phases 2–3" hint, OR link out to the actual nats-infrastructure provisioning runbook. Mark Phases 4+ as still requiring the *provisioned* server. |
| 2.x   | `--db-path "$FORGE_HOME/forge.db"` on `forge queue` | `forge queue` does not have `--db-path`; it reads `$FORGE_DB_PATH` env var or `forge.yaml`. `forge history` uses `--db` (not `--db-path`). `forge status` does have `--db-path`. | Replace the runbook's `--db-path "$FORGE_HOME/forge.db"` on every command with `export FORGE_DB_PATH="$FORGE_HOME/forge.db"` once at the top of Phase 2.1, then use the actual flag names per command. |
| 2.x   | `forge queue` invocations omit `--feature-yaml` and `--config` | `forge queue` requires `--feature-yaml FILE` (must exist on disk) and a `forge.yaml` (`--config FILE`). The runbook doesn't show how to produce either. | Have Phase 2.1 write a minimal `forge.yaml` (only `permissions.filesystem.allowlist` is mandatory) AND a per-feature stub YAML, and pass them via `--config` and `--feature-yaml`. Also, **Phase 2's claim that "this stubs NATS"** is **false** — `forge queue` always tries to publish to `$FORGE_NATS_URL` (default `nats://127.0.0.1:4222`). Either start a local NATS or set `FORGE_NATS_URL` to a fake-mode endpoint (which doesn't exist as a built-in seam). |
| 2.x   | Identifiers `FEAT-TEST-MA`, `FEAT-TEST-MB`, `TASK-TEST-MC` | The wire schema regex `^FEAT-[A-Z0-9]{3,12}$` rejects hyphenated suffixes (`FEAT-TEST-MA`) AND any non-`FEAT-` prefix. The CLI's `validate_feature_id` is more permissive than the payload's pydantic validator. | (a) Switch examples to `FEAT-TESTMA` / `FEAT-TESTMB` / `FEAT-TESTMC`. (b) File a real bug — Mode C is documented as accepting `TASK-*` but the payload schema forbids it (F008-VAL-002). |
| 1.3   | `tests/bdd/test_feat_forge_007.py` | File does not exist. The repo has `features/mode-a-greenfield-end-to-end/` but no Mode A BDD bindings module. | Drop the path from the runbook OR write the missing FEAT-FORGE-007 BDD bindings. |
| 1.1   | Full pytest sweep | `tests/bdd/test_infrastructure_coordination.py` fails to collect: `ModuleNotFoundError: No module named 'forge.build'` — TASK-IC-009/010 modules (`forge.build.git_operations`, `forge.build.test_verification`) were never landed. | Add `--ignore=tests/bdd/test_infrastructure_coordination.py` to Phase 1.1 with a footnote, OR file a substrate task to land TASK-IC-009/010. |
| 6.1   | `docker build -t forge:production-validation -f Dockerfile .` | No `Dockerfile` exists in the repo. | Either (a) create the production Dockerfile as part of the LES1 work, or (b) drop the runbook's claim that Phase 6 can run today. |

## Headline metrics

- **Test count:** 3757 passed / 4 failed / 1 skipped / 1 collection error (excluded with `--ignore`). Total ~3762 collected.
- **BDD scenarios (FEAT-FORGE-008):** 64/64 passed (runbook said 56; the count grew, no scenarios skipped).
- **Mode A integration (FEAT-FORGE-007 substrate guard):** 40/42 passed; the 2 reds match the runbook's predicted regression signature exactly.
- **Mode B/C integration (TASK-MBC8-010/011/013/014):** 68/68 passed.
- **Cross-mode concurrency assertion (TASK-MBC8-013):** ✅ pass.
- **Constitutional regression (executor-layer + prompt-layer):** 5/5 passed.
- **CLI surface:** `forge queue` accepts `--mode a|b|c`; `mode-c` queues for `FEAT-*` only (Mode C `TASK-*` rejected by wire schema); ASSUM-006 single-feature reject fires with the documented error message; `forge history --mode` filter works; `forge status` shows `mode-{a,b,c}` correctly.
- **NATS publish round-trip:** ✅ — `pipeline.build-queued.<feature>` envelope arrives with threaded `correlation_id` matching the CLI's emitted UUID.
- **LES1 production-image subscription / PORT matrix / ARFS / canonical-freeze walkthrough:** not attempted — see hard-stop and prerequisite gaps above.

## Decision

- [ ] Step 6 ✅ canonical — proceed to Step 7
- [x] **Step 6 partially passed — file follow-up tasks (linked below) and re-run blocked gates**
- [ ] Step 6 failed — block until issue resolved

The Mode A regression is a **hard regression in shipped FEAT-FORGE-007 substrate behaviour** introduced by FEAT-FORGE-008 — not a partial pass. Step 6 cannot be declared canonical until F008-VAL-003 lands. Mode B and Mode C themselves look healthy (Phase 2 + 68/68 integration tests + 64/64 BDD), so the fix scope is constrained: extend `Supervisor._dispatch` so Mode A can route through `StageClass.TASK_REVIEW` (the dispatcher most likely matches the existing subprocess/specialist family), then re-run Phase 1.

## Follow-up tasks

- **F008-VAL-001** — `tests/bdd/test_infrastructure_coordination.py` cannot collect. `forge.build.git_operations` and `forge.build.test_verification` (TASK-IC-009/010) were never landed in `src/forge/`. Either implement the missing modules or remove/skip the test. *Severity: medium (substrate, pre-existing — not introduced by FEAT-FORGE-008, but unblocks Phase 1.1's clean pass).*
- **F008-VAL-002** — Mode C wire-payload rejects `TASK-*` identifiers. `nats_core.events._pipeline.BuildQueuedPayload.feature_id` regex is `^FEAT-[A-Z0-9]{3,12}$` but FEAT-FORGE-008 ASSUM-004 says Mode C operates on `TASK-*` IDs. Either widen the regex (and rename the field to `subject_id`) or add a sibling `subject_id` field used by Mode C. *Severity: high — Mode C is half-shipped: CLI accepts the input, wire layer refuses it.*
- **F008-VAL-003** — `Supervisor._dispatch` raises `TypeError: no routing for stage <StageClass.TASK_REVIEW>` whenever Mode A reaches `task-review`. Add the routing branch in `src/forge/pipeline/supervisor.py:1555`. Re-run Phase 1.3 to confirm. *Severity: blocker — this is the FEAT-FORGE-007 substrate guard the runbook §1.3 calls out by name.*
- **F008-VAL-004** — `forge.lifecycle.recovery` violates the AC-008 single-ownership rule for `evidence_priors`. Move construction back into `forge.approval_publisher` or import the helper. *Severity: medium — the structural guard was deliberately wired during FEAT-FORGE-004; the recovery code's open-coded shape will drift on every future evidence-priors edit.*
- **F008-VAL-005** — `migrations.apply_at_boot` is non-idempotent for the v2 schema row. Audit the v2 migration that ships with FEAT-FORGE-008 (TASK-MBC8-001 mode column or the TASK_REVIEW/TASK_WORK seed) and gate the `INSERT INTO schema_version` on `WHERE NOT EXISTS`. *Severity: high — second boot duplicates a `schema_version` row, which then trips uniqueness or version-pin assertions downstream.*
- **F008-VAL-006** — Runbook gap-fold: apply every "Suggested runbook fix" from the table above to `RUNBOOK-FEAT-FORGE-008-validation.md` so the next walkthrough can run verbatim. *Severity: medium — LES1 §8 lesson; the runbook is the contract.*
- **F008-VAL-007** — Phases 4–6 prerequisites: provision the canonical NATS (JetStream streams + KV) on this host AND author the forge production `Dockerfile` so the LES1 CMDW/PORT/ARFS gates can run. *Severity: high — without these, Step 6 cannot be declared canonical even after F008-VAL-003 lands.*

## Hand-off notes for re-run

When F008-VAL-003 (Supervisor routing) and F008-VAL-005 (migration idempotency) land, re-run Phase 1 only — if those go green, the rest of Phase 1 (constitutional, BDD-008, Mode B/C integration) was already green this pass. Phase 2 needs no re-run beyond a quick smoke.

Phases 4–6 should not be attempted before F008-VAL-007 unprovisioned-NATS work lands — they will produce noise, not signal.
Update Todos

Phase 0: Pre-flight checks (branch, artefacts, env, CLI)

Phase 1: Local pytest gate (full suite, BDD-008, Mode A regression)

Phase 2: CLI smoke (forge queue across modes, with local NATS)

Phase 3: NATS pipeline-event observation (queue-time event capture)

Phases 4-6: deferred per runbook §1.3 hard-stop on Mode A regression

Phase 7: RESULTS file written; build plan NOT updated (Step 6 not canonical)
Validation runbook executed. Summary:

Decision: Step 6 partially passed — not canonical. RESULTS file written to docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md.

Hard regression confirmed (the runbook §1.3 trap): Supervisor._dispatch at src/forge/pipeline/supervisor.py:1555 has no routing branch for StageClass.TASK_REVIEW. Mode A reaches that stage and crashes with TypeError. Two Mode A integration tests are red as a direct consequence.

Other reds in Phase 1.1:

migrations.apply_at_boot non-idempotent for v2 schema row (duplicate insert on second boot).
lifecycle/recovery.py open-codes evidence_priors — violates AC-008 single-ownership.
tests/bdd/test_infrastructure_coordination.py cannot collect (forge.build modules from TASK-IC-009/010 missing — pre-existing, not FEAT-FORGE-008).
What is healthy: FEAT-FORGE-008 BDD bindings (64/64), Mode B + Mode C integration smoke (68/68), constitutional guard (5/5), CLI surface for all three modes including ASSUM-006 single-feature reject, mode-filtered history, and a real NATS round-trip with correlation-ID threading.

Other findings worth filing:

Mode C wire schema rejects TASK-* identifiers despite FEAT-FORGE-008 ASSUM-004 — Mode C is half-shipped (F008-VAL-002).
The runbook itself has 9 copy-paste-as-code gaps documented in the RESULTS file (forge.yaml required, --db vs --db-path, missing --feature-yaml, invalid example IDs, no fake-NATS seam, missing Dockerfile, etc.).
I did not touch the build plan — Step 6 cannot be marked canonical with these reds. Phases 4–6 were skipped per the runbook's own §1.3 hard-stop rule plus the absence of provisioned JetStream NATS and a forge production Dockerfile on this host.

/task-create please create a review task to analyse the runbook results docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md and provide any context from this conversation) with the aim of fixing the failings and addressing the findings
Bash Inspect task directory layout and review-task naming convention
IN
cd ~/Projects/appmilla_github/forge && ls tasks/ 2>&1; echo "---"; ls tasks/backlog/ 2>&1 | head -20; echo "---"; ls tasks/backlog/ 2>&1 | grep -iE "REV-|review" | head -5

OUT
backlog
completed
design_approved
in_progress
in_review
---
confidence-gated-checkpoint-protocol
forge-v2-doc-alignment
guardkit-command-invocation-engine
infrastructure-coordination
langchain-1x-pin-alignment
mode-a-greenfield-end-to-end
mode-b-feature-and-mode-c-review-fix
nats-fleet-integration
pipeline-state-machine-and-configuration
specialist-agent-delegation
TASK-CGCP-001-define-gating-module-structure.md
TASK-CGCP-002-add-approval-config.md
TASK-CGCP-003-request-id-derivation-helper.md
TASK-CGCP-012-bdd-scenario-task-linking.md
TASK-FIX-F0E6b-republish-nats-core-wheel.md
TASK-GCI-001-define-guardkit-result-models.md
TASK-GCI-002-define-git-and-progress-event-models.md
TASK-IC-003-write-ordering-guard.md
TASK-IC-009-test-verification-via-execute.md
TASK-MAG7-001-define-stage-taxonomy.md
---
mode-b-feature-and-mode-c-review-fix
TASK-REV-CG44-plan-confidence-gated-checkpoint-protocol.md
TASK-REV-DUPF-investigate-autobuild-duplicate-task-files.md
TASK-REV-GCI0-plan-guardkit-command-invocation-engine.md
TASK-REV-MAG7-plan-mode-a-greenfield-end-to-end.md
Bash Sample existing TASK-REV-* file to learn convention
IN
cd ~/Projects/appmilla_github/forge && cat tasks/backlog/TASK-REV-DUPF-investigate-autobuild-duplicate-task-files.md 2>&1 | head -80

OUT
---
id: TASK-REV-DUPF
title: "Investigate autobuild duplicate task files"
task_type: review
status: backlog
priority: normal
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
complexity: 4
tags: [review, investigation, guardkit, autobuild, task-files, hygiene]
related_features: [FEAT-FORGE-002, FEAT-FORGE-003, FEAT-FORGE-004]
related_commits:
  - 91f4de5  # FEAT-FORGE-002 merge
  - f63bcf5  # FEAT-FORGE-003 merge
  - 9774351  # FEAT-FORGE-004 merge
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Investigate autobuild duplicate task files

## Description

Each `guardkit autobuild feature` run that has been merged into `main` so far
(FEAT-FORGE-002, FEAT-FORGE-003, FEAT-FORGE-004) has produced a second copy
of every task file in flat directories alongside the authoritative copies that
live in `tasks/backlog/<feature-slug>/`. The duplicates have **divergent
content** (different YAML frontmatter), are committed by the autobuild branch,
and persist in `main` after merge.

This is a quiet bug — nothing breaks immediately — but it pollutes the task
inventory, splits any future task-status tooling across two paths, and the
divergence means it is no longer obvious which file is authoritative.

## Observed Pattern

### Duplicate locations

For every feature, the autobuild branch creates one of:

- `tasks/backlog/TASK-XXX-*.md` (flat)
- `tasks/design_approved/TASK-XXX-*.md` (flat)

…in addition to the authoritative copy at:

- `tasks/backlog/<feature-slug>/TASK-XXX-*.md` (the file `feature-plan` produced)

### Distribution rule (empirical)

Looking at FEAT-FORGE-002/003/004, the split appears to be:

- **Wave 1 tasks + BDD/wiring tasks** → `tasks/backlog/` (flat)
- **All other tasks** → `tasks/design_approved/` (flat)

| Feature | Authoritative dir | `backlog/` flat | `design_approved/` flat |
|---|---|---|---|
| FEAT-FORGE-002 (NFI) | `tasks/backlog/nats-fleet-integration/` | NFI-001, NFI-002 | NFI-003 … NFI-011 |
| FEAT-FORGE-003 (SAD) | `tasks/backlog/specialist-agent-delegation/` | SAD-001 | SAD-002 … SAD-012 |
| FEAT-FORGE-004 (CGCP) | `tasks/backlog/confidence-gated-checkpoint-protocol/` | CGCP-001, 002, 003, 012 | CGCP-004 … CGCP-011 |

This roughly correlates with `status: in_progress` (wave 1 / BDD-wiring tasks
that the orchestrator hadn't yet flipped to design-approved) vs.
`status: design_approved` (middle waves the orchestrator had advanced).
Worth confirming.

### Content divergence

A spot diff of the SAD-002 pair shows the duplicates are **not** byte-identical
copies:

```
< id: TASK-SAD-002                               (in subdir copy only)
< title: Resolution-record persistence + ...     (in subdir copy only)
< task_type: feature                             (in subdir copy only)
< status: in_review                              (in subdir copy only)
< priority: high                                 (in subdir copy only)
< updated: 2026-04-25 00:00:00+00:00             (in subdir copy only)
< parent_review: TASK-REV-SAD3                   (in subdir copy only)
Bash Verify TASK-REV-F008 ID is free
IN
cd ~/Projects/appmilla_github/forge && find tasks -name "TASK-REV-F008*" 2>&1; find tasks -name "*F008*" 2>&1 | head

OUT
(Bash completed with no output)
Write TASK-REV-F008-fix-feat-forge-008-validation-failures.md
318 lines
---
id: TASK-REV-F008
title: "Fix FEAT-FORGE-008 validation failures and address runbook findings"
task_type: review
status: backlog
priority: high
created: 2026-04-29T18:00:00Z
updated: 2026-04-29T18:00:00Z
complexity: 6
tags: [review, validation, regression, mode-a, mode-c, runbook, feat-forge-008]
related_features: [FEAT-FORGE-007, FEAT-FORGE-008]
related_runbooks:
  - docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md
  - docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md
related_commits:
  - 2f13eac  # FEAT-FORGE-008 merge (Mode B + Mode C autobuild)
  - 22c0b1f  # autobuild metadata for FEAT-FORGE-008
  - 51ae6a6  # FEAT-FORGE-008 worktree cleanup
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Fix FEAT-FORGE-008 validation failures and address runbook findings

## Description

The Step 6 validation walkthrough of `RUNBOOK-FEAT-FORGE-008-validation.md`
ran on 2026-04-29 against `main` at commit `5e5cc73` (FEAT-FORGE-008 merge
`2f13eac` already in history). It produced
`docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md` with **decision = Step 6
partially passed**.

Headline outcome: 3757/3762 pytest pass, 64/64 BDD-008 scenarios pass, 68/68
Mode B + Mode C integration pass, but **Mode A regressed** — the runbook §1.3
hard-stop trap fired exactly as predicted ("If any Mode A test is red,
FEAT-FORGE-008 broke `Supervisor.next_turn` — stop and triage"). In addition,
three other unit/integration reds, one collection error, one Mode C wire-schema
contradiction, and ~9 runbook-as-code copy-paste gaps were captured.

The aim of this review is to **analyse those findings, choose the fix
sequence, and decide which become implementation tasks vs. follow-up runbook
edits** — so Step 6 can be re-run cleanly and declared canonical, unblocking
Step 7 (FinProxy first real run).

## Inputs the reviewer must read first

1. **`docs/runbooks/RESULTS-FEAT-FORGE-008-validation.md`** — full per-gate
   table, error excerpts, headline metrics, runbook-gap table, follow-up list
   F008-VAL-001..007.
2. **`docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md`** — the runbook
   that was executed (so the reviewer can see which copy-paste blocks need
   fixing).
3. **`docs/research/ideas/forge-build-plan.md`** — Step 6 spec and the LES1
   parity gate definitions; this review's exit criterion is "Step 6 ✅
   canonical" against this plan.
4. **`src/forge/pipeline/supervisor.py`** at line ~1555 — the `_dispatch`
   raise site that breaks Mode A.
5. **`src/forge/lifecycle/migrations.py`** + the v2 migration — for the
   non-idempotent `apply_at_boot` failure.
6. **`src/forge/lifecycle/recovery.py`** — for the `evidence_priors`
   single-ownership AC-008 violation.
7. **`/home/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/_pipeline.py`**
   line 27 — `FEATURE_ID_PATTERN = re.compile(r"^FEAT-[A-Z0-9]{3,12}$")`
   — the regex that contradicts Mode C ASSUM-004.
8. **`tests/integration/test_mode_a_concurrency_and_integrity.py`**
   `TestMultiFeatureCatalogue` and `TestCorrelationThreading` — the two red
   Mode A tests that must go green.
9. **`tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent`**
   — the non-idempotent migration assertion.
10. **`tests/forge/test_approval_publisher.py::TestSingleOwnership::test_no_other_module_in_forge_constructs_evidence_priors`**
    — the AC-008 structural guard.

## Findings to triage (verbatim from RESULTS §"Follow-up tasks")

### Blockers (Mode A regression — runbook §1.3 hard-stop)

- **F008-VAL-003** — `Supervisor._dispatch` raises
  `TypeError: no routing for stage <StageClass.TASK_REVIEW>` whenever Mode A
  reaches `task-review`. Add a routing branch in
  `src/forge/pipeline/supervisor.py:1555`.
  *Severity: blocker.*

### High-severity (semantic correctness)

- **F008-VAL-002** — Mode C wire-payload rejects `TASK-*` identifiers.
  `nats_core.events._pipeline.BuildQueuedPayload.feature_id` regex
  `^FEAT-[A-Z0-9]{3,12}$` contradicts FEAT-FORGE-008 ASSUM-004 (Mode C
  operates on `TASK-*` IDs). Either widen the regex (and probably rename
  the field to `subject_id`) or add a sibling `subject_id` field used
  only by Mode C. **Mode C is half-shipped: the CLI accepts `TASK-*`
  but the wire layer refuses it.**
- **F008-VAL-005** — `migrations.apply_at_boot` is non-idempotent for the
  v2 schema row. The v2 migration shipped with FEAT-FORGE-008 (almost
  certainly TASK-MBC8-001 mode column or TASK-MBC8-006 TASK_REVIEW/TASK_WORK
  seed) reinserts the `schema_version=2` row on every boot. Gate the
  `INSERT INTO schema_version` on `WHERE NOT EXISTS` (or use
  `INSERT OR IGNORE`).
- **F008-VAL-007** — Phases 4–6 prerequisites: provision the canonical
  JetStream NATS (streams + KV) on this host AND author the forge
  production `Dockerfile` so the LES1 CMDW/PORT/ARFS gates can run. Without
  these, Step 6 cannot be declared canonical even after F008-VAL-003 lands.

### Medium-severity (structural/regression)

- **F008-VAL-004** — `forge.lifecycle.recovery` open-codes the
  `evidence_priors` dict shape, violating `approval_publisher.py`'s AC-008
  single-ownership guard. Move construction back into
  `forge.approval_publisher` or import the helper.
- **F008-VAL-001** — `tests/bdd/test_infrastructure_coordination.py` cannot
  collect: `ModuleNotFoundError: No module named 'forge.build'`.
  TASK-IC-009/010 (`forge.build.git_operations`,
  `forge.build.test_verification`) were never landed in `src/forge/`.
  Pre-existing — *not* introduced by FEAT-FORGE-008, but blocks a clean
  Phase 1.1 sweep. Decide: implement TASK-IC-009/010 now, mark them
  scope-deferred and skip the test, or split them out as their own feature.
- **F008-VAL-006** — Runbook gap-fold: the runbook had ~9 copy-paste
  blocks that needed manual edits to execute (see RESULTS table). Apply
  every "Suggested runbook fix" to
  `RUNBOOK-FEAT-FORGE-008-validation.md` so the next walkthrough runs
  verbatim. Specifically:
    - 0.4: pin to `uv pip install -e ".[providers,dev]"`, add `uv` install
      step, document `--break-system-packages` fallback, and the
      stale-editable-install rewire trick.
    - 0.5: add `~/.local/bin` PATH check.
    - 0.6: add the throwaway-NATS-via-docker hint and link to the
      provisioned-NATS infra runbook.
    - 2.1+: replace `--db-path` on `forge queue` with
      `export FORGE_DB_PATH=...`; use `--db` (not `--db-path`) for
      `forge history`; show how to write a minimal `forge.yaml`
      (`permissions.filesystem.allowlist` is the only required field) and
      a per-feature stub YAML; remove the false claim that Phase 2 stubs
      NATS.
    - 2.x: change example IDs to `FEAT-TESTMA` / `FEAT-TESTMB` /
      `FEAT-TESTMC` (no inner hyphens; valid per wire regex). Note the
      `TASK-*` regression (F008-VAL-002) so it isn't accidentally retried.
    - 1.3: drop the non-existent `tests/bdd/test_feat_forge_007.py` path
      OR write the missing FEAT-FORGE-007 BDD bindings.
    - 1.1: footnote
      `--ignore=tests/bdd/test_infrastructure_coordination.py` until
      F008-VAL-001 closes.
    - 6.1: either author a forge production `Dockerfile` or strike the
      runbook claim that Phase 6 can run today.

## Acceptance Criteria

This review task is complete when ALL of the following are true:

- [ ] **AC-1**: A decision has been recorded for each finding F008-VAL-001
      through F008-VAL-007: implement-now, implement-later (with linked
      task), or won't-fix-with-rationale.
- [ ] **AC-2**: Implementation tasks have been created (via `/task-create`)
      for every finding marked implement-now. Each new task links back to
      this review via `parent_review: TASK-REV-F008`.
- [ ] **AC-3**: A clear sequencing decision exists for the implementation
      tasks (which lands first, which can run in parallel, what the
      re-run order of the runbook phases is once each lands).
- [ ] **AC-4**: For F008-VAL-002 (Mode C wire-schema vs CLI mismatch), a
      design choice is recorded — widen the regex, rename to
      `subject_id`, or add a sibling field. The choice must be reconciled
      with `nats-core` ownership (the regex lives in the sibling repo).
- [ ] **AC-5**: For F008-VAL-007 (NATS provisioning + production
      Dockerfile), the review records whether these become forge tasks
      or get delegated to `nats-infrastructure` and a separate
      containerisation effort.
- [ ] **AC-6**: A "go / no-go" decision is recorded for re-running
      `RUNBOOK-FEAT-FORGE-008-validation.md` Phase 1 only (cheap signal)
      after F008-VAL-003 + F008-VAL-005 land, BEFORE attempting Phases
      4–6.
- [ ] **AC-7**: The runbook gap-fold (F008-VAL-006) is either committed
      or explicitly scheduled, since Phase 6.4 (canonical-freeze) cannot
      be passed until the runbook executes verbatim.

## Out of scope

- Implementing the fixes themselves. This is a review/decision task; each
  fix becomes its own implementation task via `/task-work TASK-XXX` after
  the review's checkpoint decision.
- Re-running the validation runbook. That happens after the implementation
  tasks land.
- Step 7 (FinProxy first run). Blocked by Step 6 going canonical.

## Context from the validation session (2026-04-29)

These are the load-bearing diagnostic facts the reviewer should NOT have to
re-derive — they came out of running the runbook end-to-end.

### Environment notes (saves the reviewer ~30 min)

- `/etc/hosts` has `127.0.0.1 promaxgb10-41b1`, so on this workstation
  "Local" and "GB10" phases of the runbook are the **same machine**. The
  runbook's two-machine framing is misleading on this host.
- The forge editable install in user-site (`~/.local/lib/python3.12/...`)
  was originally pinned at a worktree path `.guardkit/worktrees/FEAT-FORGE-005`
  that no longer exists. Rewire with
  `pip install --user --break-system-packages --force-reinstall --no-deps -e .`
  from the live tree. (Don't use `--break-system-packages` casually
  elsewhere — but here we already have a user-site install.)
- `uv` is not installed on this host. The runbook's
  `pip install -e '.[providers,dev]'` cannot resolve `nats-core` from a
  fresh venv because `[tool.uv.sources]` is uv-only. The existing
  user-site `nats-core 0.2.0` editable install (from sibling
  `/home/richardwoollcott/Projects/appmilla_github/nats-core`) is the
  reason the rewire works without re-resolving deps.
- No JetStream-provisioned NATS is running. An ephemeral
  `docker run -d --network host nats:latest -js` (no persistent volume)
  was used for Phases 2–3 only. The container was named
  `forge-validation-nats` and stopped/removed at end of session.
- No forge production `Dockerfile` exists in the repo, so Phase 6.1
  (CMDW gate) is structurally unreachable today.

### Pytest failure modes (verbatim)

```
FAILED tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent
  AssertionError: second apply must not duplicate the seed row
  rows == [(1,), (2,)] but expected [(1,)]

FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership
       ::test_no_other_module_in_forge_constructs_evidence_priors
  AssertionError: Other modules reconstruct details shape (AC-008):
    [PosixPath('src/forge/lifecycle/recovery.py')]

FAILED tests/integration/test_mode_a_concurrency_and_integrity.py
       ::TestMultiFeatureCatalogue
       ::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py
       ::TestCorrelationThreading
       ::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
  TypeError: Supervisor._dispatch: no routing for stage
            <StageClass.TASK_REVIEW: 'task-review'>
  src/forge/pipeline/supervisor.py:1555
```

```
ERROR tests/bdd/test_infrastructure_coordination.py
  ModuleNotFoundError: No module named 'forge.build'
  → forge.build.git_operations + forge.build.test_verification (TASK-IC-009/010)
    never landed.
```

### CLI surface gaps observed

- `forge queue` flags actually present: `--mode`, `--repo`, `--branch`,
  `--feature-yaml` (required), `--max-turns`, `--timeout`,
  `--correlation-id`. **No `--db-path`** — uses `$FORGE_DB_PATH` env or
  config.
- `forge history` flag is `--db` (required) — **NOT** `--db-path`.
- `forge status` flag is `--db-path` (matches runbook).
- `forge queue` requires `forge.yaml` (via top-level `--config FILE`
  flag or `./forge.yaml` in CWD). Minimum content:
  ```yaml
  permissions:
    filesystem:
      allowlist:
        - /absolute/path/to/an/allowed/checkout
  ```
- `forge queue` always tries to publish to NATS at `$FORGE_NATS_URL`
  (default `nats://127.0.0.1:4222`). There is **no fake-mode env switch**
  in `src/forge/cli/queue.py:_publish_once`, so the runbook's claim that
  Phase 2 stubs NATS via "the integration adapter" is false.

### What was healthy (worth not re-checking)

- Mode B integration: `tests/integration/test_mode_b_smoke_e2e.py` 19/19
  pass.
- Mode C integration: `tests/integration/test_mode_c_smoke_e2e.py` 17/17
  pass.
- Cross-mode concurrency: `test_cross_mode_concurrency.py` 19/19 pass.
- Mode B/C crash recovery: `test_mode_b_c_crash_recovery.py` 13/13 pass.
- BDD-008 bindings: 64/64 pass (runbook said 56 — count went up cleanly).
- Constitutional regression (executor + prompt-layer): 5/5 pass.
- Mode A integration *minus* the two TASK_REVIEW reds: 40/42 pass — so
  the regression is specifically and only the missing dispatch branch.
- NATS round-trip: `pipeline.build-queued.<feature_id>` envelope arrives
  with threaded `correlation_id` matching the CLI-emitted UUID.
- Mode B single-feature ASSUM-006 reject: fires with the documented
  error string.
- `forge history --mode {a,b,c}` filter: works correctly.

## Suggested deliverable shape

A single decision document (could live alongside the RESULTS file or as a
new `docs/reviews/REVIEW-F008-validation-triage.md`) that contains, in
order:

1. **Triage table** — F008-VAL-001..007 × {decision, owner, target task ID
   if implement-now, sequencing}.
2. **Mode C ASSUM-004 design decision** (the F008-VAL-002 nats-core
   regex question) — three options weighed, recommendation.
3. **Re-run plan** — exact phases of the runbook to re-execute and in
   what order, after each fix lands.
4. **Phase 6 prerequisite plan** — concrete owners/dates for NATS
   provisioning and the forge production Dockerfile.
5. **Runbook gap-fold patch outline** — bullet list of edits to apply to
   `RUNBOOK-FEAT-FORGE-008-validation.md` (the §F008-VAL-006 fixes
   above).

## Implementation Notes

This task is best executed via `/task-review TASK-REV-F008
--mode=architectural`, not `/task-work`, because the deliverable is a
decision document and a fan-out of new implementation tasks rather than
code changes.

After the review checkpoint:
- `[I]mplement` should fan out to one task per finding marked
  implement-now in the triage table. Recommended hash prefix for those:
  `F8`. Example: `TASK-F8-XXXX-fix-supervisor-dispatch-task-review`.
- `[A]ccept` is appropriate only if every F008-VAL-* item has a
  decision recorded *and* the runbook gap-fold (F008-VAL-006) is
  scheduled.

## Test Execution Log

[Populated by `/task-review` / `/task-complete`.]
Task created.

✅ Task Created: TASK-REV-F008

📋 Task Details

Title: Fix FEAT-FORGE-008 validation failures and address runbook findings
Type: review (architectural decision/triage task)
Priority: high
Status: backlog
Tags: review, validation, regression, mode-a, mode-c, runbook, feat-forge-008
Related features: FEAT-FORGE-007, FEAT-FORGE-008
Related runbooks: RUNBOOK-FEAT-FORGE-008-validation.md, RESULTS-FEAT-FORGE-008-validation.md
📁 File Location
tasks/backlog/TASK-REV-F008-fix-feat-forge-008-validation-failures.md

Contents include:

7 acceptance criteria covering decisions for all F008-VAL-001..007 findings
Curated reading list of 10 source files/lines so the reviewer doesn't re-derive what was learned
Verbatim pytest failure modes (4 reds + 1 collection error)
Environment notes (the 127.0.0.1 promaxgb10-41b1 quirk, the stale FEAT-FORGE-005 editable-install trap, no uv / no provisioned NATS / no Dockerfile)
CLI surface gaps observed (actual flags vs. runbook claims)
A list of what was healthy (so the re-run can be scoped tight)
Suggested deliverable shape (triage table → ASSUM-004 design decision → re-run plan → Phase-6 prereq plan → runbook gap-fold patch outline)
Next Steps

/task-review TASK-REV-F008 --mode=architectural to execute the review
After the checkpoint, [I]mplement fans out per-finding tasks (suggested prefix F8)
/task-complete TASK-REV-F008 once decisions are recorded
Stopping here per the /task-create contract — no implementation, just the task file.
---
name: code-review
description: Review a coding change against its task, repository contracts, safety boundaries, and test evidence.
license: MIT
---

# Code review

Use this skill after implementation and before reporting the change complete.

## Review process

1. Re-read the task, acceptance checks, repository instructions, and allowed
   path boundary.
2. Inspect the complete diff and read every changed file end to end. Check the
   relevant callers and tests rather than reviewing the patch in isolation.
3. Look for incorrect behavior, missed edge cases, accidental scope growth,
   unsafe input handling, secrets, dead code, and claims that exceed the
   evidence.
4. Run the repository's documented product tests through a command mechanism the
   runtime actually provides. Record the exact command, exit status, failures,
   and skips.
5. For each changed Python file, the bundled helper can add a bounded syntax
   check when Python execution is available:

   ```bash
   python skills/code-review/lint_check.py --root . path/to/file.py [more.py ...]
   ```

6. Fix findings within the authorised scope, then repeat the affected checks and
   review the final diff.

## Review checklist

- The change satisfies the stated behavior and preserves relevant existing
  behavior.
- Inputs fail clearly at boundaries, and file or command operations cannot
  escape their intended scope.
- Code follows the repository's established style without unnecessary
  abstraction.
- Tests cover meaningful success and failure behavior without merely repeating
  the implementation.
- Test evidence belongs to the final source state; failures and skips are not
  hidden.
- Changed paths stay within the declared ownership boundary.

The helper validates decoding and Python syntax only. It does not import or run
the checked files, lint semantics, test behavior, or replace the product's actual
tests.

Adapted from `examples/deploy-coding-agent/skills/code-review/SKILL.md` at
`langchain-ai/deepagents@1d3232c0852c47af09119edea10eeec887e4f0da`.

# Example report

Real, captured output from a single invocation against the sample project
shipped in this repository:

```
$ POLYLINT_PY="$(uv run python -c 'import sys;print(sys.executable)')" \
  bash polylint.sh examples/sample-project/src/app.py --no-precommit
```

```
# polylint: examples/sample-project/src/app.py
profile: default
lang: py

===== ruff (exit=1) =====
examples/sample-project/src/app.py:3:8: F401 [*] `os` imported but unused
examples/sample-project/src/app.py:17:101: E501 Line too long (120 > 100)
Found 2 errors.
[*] 1 fixable with the `--fix` option.

===== pylint (exit=28) =====
************* Module app
examples/sample-project/src/app.py:14:13: C0303: Trailing whitespace (trailing-whitespace)
examples/sample-project/src/app.py:17:0: C0301: Line too long (120/100) (line-too-long)
examples/sample-project/src/app.py:1:0: C0114: Missing module docstring (missing-module-docstring)
examples/sample-project/src/app.py:6:0: C0116: Missing function or method docstring (missing-function-docstring)
examples/sample-project/src/app.py:9:11: W0718: Catching too general exception Exception (broad-exception-caught)
examples/sample-project/src/app.py:6:0: R1710: Either all return statements in a function should return an expression, or none of them should. (inconsistent-return-statements)
examples/sample-project/src/app.py:3:0: W0611: Unused import os (unused-import)

-----------------------------------
Your code has been rated at 3.00/10


===== mypy (exit=0) =====
Success: no issues found in 1 source file

===== vulture (exit=3) =====
examples/sample-project/src/app.py:3: unused import 'os' (90% confidence)
examples/sample-project/src/app.py:6: unused function 'process' (60% confidence)
examples/sample-project/src/app.py:13: unused function '_unused_helper' (60% confidence)
examples/sample-project/src/app.py:17: unused variable 'LONG_MESSAGE' (60% confidence)

===== bandit (exit=1) =====
Run started:2026-08-26 05:07:33.953380

Test results:
>> Issue: [B110:try_except_pass] Try, Except, Pass detected.
   Severity: Low   Confidence: High
   CWE: CWE-703 (https://cwe.mitre.org/data/definitions/703.html)
   More Info: https://bandit.readthedocs.io/en/1.7.10/plugins/b110_try_except_pass.html
   Location: ./examples/sample-project/src/app.py:9:4
8	        return [item.strip() for item in items]
9	    except Exception:
10	        pass
11	

--------------------------------------------------

Code scanned:
	Total lines of code: 10
	Total lines skipped (#nosec): 0
	Total potential issues skipped due to specifically being disabled (e.g., #nosec BXXX): 0

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 1
		Medium: 0
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 0
		High: 1
Files skipped (0):
```

Piping that same output through the classifier turns it into an honest,
scannable status table:

```
$ ... | uv run python scripts/classify.py
```

```
# polylint status report

| tool | status | exit | count |
|---|---|---|---|
| ruff | found | 1 | 2 |
| pylint | found | 28 | 7 |
| mypy | ok | 0 | 0 |
| vulture | found | 3 | 4 |
| bandit | found | 1 | 1 |
```

Every one of `src/app.py`'s planted defects (an unused import, a bare
`try/except Exception: pass`, an unused function, an over-length line) is
picked up by at least one tool, and every tool that ran cleanly (`mypy`) is
reported as `ok` rather than silently omitted.

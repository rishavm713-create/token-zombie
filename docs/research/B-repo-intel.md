# Group B: repository intelligence (research, 2026-11-25)
Scope: aider, serena, tree-sitter (+py-tree-sitter), ast-grep, SylphxAI/repomap. TZ today: bin/tzrank.py (111 lines), bin/tzmap.py (148), bin/tzcompress.py skeleton/ts_skeleton, bin/tzops.py impact (53-60, git grep -w only), tests/test_repo_intel.sh.
Class key: A reuse / B selective port (NOTICE) / C independent rebuild / D reference / E reject.

## 1. Aider-AI/aider
URL https://github.com/Aider-AI/aider | licence Apache-2.0 (SPDX; NOTICE already carries aider entry) | sha 5dc9490bb35f (main, pushed 2026-05-22)
Files inspected: aider/repomap.py (867 lines; get_ranked_tags 365-575, get_ranked_tags_map_uncached 629-708, to_tree 748-785), tests/basic/test_repomap.py (510 lines).

### Fidelity audit of bin/tzrank.py vs repomap.py
| Aspect | aider (line) | TZ | Verdict |
|---|---|---|---|
| Edge weight base | sqrt(num_refs) x mul (500-514) | math.sqrt(k) x mul | MATCH |
| mul: long snake/kebab/camel (len>=8) | x10 (494) | x10, snake or camel only (no kebab; irrelevant for py/js idents) | MATCH |
| mul: leading underscore, >5 definers | x0.1 each (496-499) | same | MATCH |
| mul: ident in mentioned_idents | x10 (492) | MISSING | GAP |
| mul: referencer in chat files | x50 (508) | x50 for --focus | MATCH |
| TZ-only: len(ident)<6 -> x0.1 | n/a | deliberate deviation (word-token refs) | KEEP, document |
| Unreferenced defs | self edge 0.1 (483-486) | self edge 0.1 | MATCH |
| No refs at all in repo | refs := defs (470-471) | not handled; gives only unreferenced self-loops | minor GAP |
| Personalization | per-file; chat file +100/N; mentioned_fnames max(.,100/N); +100/N if any path part / basename / stem is in mentioned_idents (383-445); also passed as `dangling` | uniform 1.0 on focus files only; dangling=pers (match) | PARTIAL: lacks mentioned_fnames and path-component ident match |
| Chat files excluded from output | yes (556) | yes (`f not in focus`) | MATCH |
| Files with no tags appended last by node rank (563-574) | yes | no | GAP (low) |
| Token-budget binary search | start middle=min(max_tokens//25, n_tags); stop when num_tokens<=budget and best, or pct_err<0.15; lo/hi bisect on count (670-703) | none: only `--n N` | GAP (main one) |
| Line-of-interest rendering (render_tree, TreeContext, lines truncated to 100 chars) | yes | prints `file: ident` only | GAP (cheap variant: def line text) |
| PageRank | networkx, alpha 0.85, MultiDiGraph, edges merged | own power iteration d=0.85, 50 it, edges flattened per (src,dst) | equivalent (sum of parallel edges = networkx weight sum) |
| Tags source | tree-sitter queries + pygments Name fallback (353) | ast (py top-level only) / regex (js, sh) + word tokens | DEVIATION: tzmap.defs returns top-level only, so methods never rank; word refs include comments/strings |
Result: weighting core is a faithful port; 4 gaps (mentioned idents, mentioned/path personalization, token-budget bisect, method-level defs). Uses of `tzmap.defs` mean class methods are invisible; fix with ast.walk (class members as `Class.method`, rank by leaf name).

### Decision: B (already done, extend). Status REVIEWED. Target bin/tzrank.py (+ tests/test_repo_intel.sh).
Spec of additions (all pure stdlib):
1. `ranked(root, focus, mentioned_idents=(), mentioned_files=())`: mul*=10 if ident in mentioned_idents; pers[f]=100/N for each focus file, max(.,100/N) for mentioned file, +100/N when {path parts, basename, stem} intersects mentioned_idents. Mentioned idents extracted from task text: `re.findall(r'[A-Za-z_][A-Za-z0-9_]*', task)` filtered to idents that exist in defines (aider does this in coders/base.py get_ident_mentions: split on non-word chars; keep as set).
2. `fit_budget(ranked_tags, max_tokens, count=len(s)//4)`: lo=0, hi=n; mid=min(max_tokens//25, n); loop while lo<=hi: tree=render(tags[:mid]); t=count(tree); err=abs(t-max)/max; if (t<=max and t>best_t) or err<0.15: best=tree,best_t=t; if err<0.15: break; if t<max: lo=mid+1 else hi=mid-1; mid=(lo+hi)//2. Return best (None -> ""). Token counter must be chars/4 labelled EST.
3. Methods: ast.walk ClassDef bodies -> `Class.method` def entries; refs matched on leaf name.
Parity examples (from test_repomap.py; their tests are behaviour-level, no numeric ranks):
- test_get_repo_map_with_identifiers (163-211): file defines `class MyClass`, `def my_method`, `def my_function`; second file only calls them; map must contain file name + all 3 names (needs method defs: TZ fails today for my_method).
- test_get_repo_map_excludes_added_files (246-271): files in chat set are absent from the map, others present. TZ: `--focus a b` omits them (already true for py).
- test_repo_map_refresh_* (49-157): adding `functionNEW` to a file appears in the next map after refresh; TZ has no cache so always true; assert it.
- test_repo_map_sample_code_base (445-506): fixture tests/fixtures/sample-code-base + expected-output file compared byte-for-byte; NOT portable (tree-sitter output, line rendering). Use instead TZ-own golden test on a 4-file fixture with hand-computed ordering (most-referenced first).
- Budget parity (derive from algorithm above): 100 tags, each rendered 40 chars, max_tokens 250 -> start mid=10 (250//25), 10 tags=100 tok, err 0.6 -> lo=11, mid=55 ->550 tok -> hi=54, mid=32 ->320 -> hi=31, mid=21 ->210 err 0.16 -> lo=22, mid=26 ->260 err 0.04 -> stop, 26 tags (within 15%). Good unit test, deterministic.
Conflicts: none; tz sym/impact stay text-based.

## 2. oraios/serena
URL https://github.com/oraios/serena | sha 23c06ff71540 | GitHub SPDX says NOASSERTION because licensing is per component.
Evidence: LICENSE lines 1-40 (per-component text), pyproject.toml line 12 `license = "GPL-3.0-or-later"` (the serena-agent distribution), LICENSES/{MIT,GPL-3.0-or-later}.txt.
Per directory: src/solidlsp/, test/solidlsp/, test/resources/ = MIT (copyright Oraios AI; some files in src/solidlsp/lsp_protocol_handler/ derived from OLSP, MIT). src/serena/ (incl. tools/symbol_tools.py), src/interprompt/, scripts/, test/serena/, docs/, everything else = GPL-3.0-or-later. Notable runtime deps: language servers downloaded per language (pyright, tsserver, etc.), mcp, pydantic.
Files inspected: src/serena/tools/symbol_tools.py (tools list, docstrings 45-330), file tree.
Capabilities: get_symbols_overview(relative_path, depth); find_symbol(name_path_pattern, depth, relative_path, include_body, include_kinds, substring_matching, max_matches); find_referencing_symbols(name_path, relative_path); find_implementations; find_declaration; diagnostics; rename/insert/replace symbol body.
Name-path semantics (documented in tool docstring, lines 96-113): `method` = any symbol with that name; `Class/method` = suffix match; `/Class/method` = absolute (exact full path in file); `Class/method[1]` = overload index; substring_matching applies to last segment.
TZ overlap: `tz sym NAME` (tzmap.sym) = regex def search + word refs, no scoping, no containment.
Decision: GPL part = C (describe behaviour, rebuild independently; never copy src/serena). SolidLSP (MIT) = D: could be vendored (B) but requires per-language servers, network downloads and long-lived processes, which breaks stdlib-only / zero-install; REJECT as dependency. Status REVIEWED (idea only; ledger row correct: "GPL-3.0+ app, MIT SolidLSP").
TZ target bin/tzmap.py `sym`. Spec (independent, python-only via ast, regex for js/ts/sh):
- Build per-file symbol tree: list of (name_path "Class/method", kind, start_line, end_line, children) with ast.walk over Module/ClassDef/FunctionDef.
- `tz sym PATTERN [--depth N] [--body] [--in PATH] [--substr]`: pattern rules exactly as above (suffix match on name_path segments; leading `/` anchors; `[i]` index on duplicates in same parent).
- `--body` prints source lines start..end of the match (cap 80 lines).
- Output must stay <= 60 lines; refs shown as file:line of word match grouped by file, tests flagged.
Parity examples (behaviour from Serena docstring, to be re-derived, not copied):
1. file `class MyClass:\n def my_method(self): ...` -> pattern `my_method` yields `MyClass/my_method`; `MyClass/my_method` yields same; `/my_method` yields nothing (absolute needs full path); `/MyClass/my_method` yields it.
2. two defs `def f` in one class -> `C/f[0]`, `C/f[1]`; `C/f[1]` returns only the second.
3. substr: `my_meth` without flag -> none; with `--substr` -> MyClass/my_method.
4. depth 1 on `MyClass` lists its direct methods only.
Conflicts: ledger lists "REIMPLEMENT idea only": keep. No LSP: references stay name-based (false positives for common names; mitigate with import-aware filter below).

## 3. tree-sitter/tree-sitter and py-tree-sitter
URLs https://github.com/tree-sitter/tree-sitter (sha n/a, master, pushed 2026-11-24) and https://github.com/tree-sitter/py-tree-sitter (v0.27.0, requires-python >=3.11).
Licence: both MIT (LICENSE files read: "The MIT License (MIT), Copyright (c) 2018 Max Brunsfeld" / "(c) 2019 Max Brunsfeld, GitHub"). Grammars are separate packages (e.g. tree-sitter-python MIT; check each before bundling).
Decision: D/E for a dependency. py-tree-sitter is a compiled wheel plus a grammar wheel per language: violates stdlib-only, and the ledger gate already treats it as optional. The existing `ts_skeleton` optional path stays; do not extend. Python skeletons via stdlib `ast` are better (see 6). Status REVIEWED (no change). Note py-tree-sitter 0.27 needs Python>=3.11; TZ must not assume it.

## 4. ast-grep/ast-grep
URL https://github.com/ast-grep/ast-grep | licence MIT (LICENSE: "MIT License, Copyright (c) 2022 Herrington Darkholme") | sha 9065b02439d9 | Rust binary (`sg`/`ast-grep`), tree-sitter inside.
Files inspected: crates/core/src/meta_var.rs (extract_meta_var 235-270, tests 308-350), crates/core/src/match_tree/strictness.rs, matcher/ and match_tree/ listing.
Pattern semantics (from meta_var.rs):
- `$NAME`: captures ONE named AST node; NAME = [A-Z_][A-Z0-9_]*; digits allowed after first char; first char digit -> not a metavariable. Same name used twice must match identical source text (e.g. `$A == $A`).
- `$_` or `$_NAME` (leading underscore): single node, not captured, no equality constraint.
- `$$NAME`: captures one node including unnamed (punctuation/operators) nodes (Capture(name, named=false)).
- `$$$`: matches zero or more nodes, not captured; `$$$NAME`: captured list (`$$$ARGS` for arguments); `$$$123` is NOT a metavar.
- Strictness levels (--strictness): cst (all nodes), smart (default; skips trivial source tokens), ast (named only), relaxed (also ignores comments), signature (ignores text of leaf nodes).
Parity examples (unit tests in meta_var.rs 312-327): extract("$$$")=Multiple; "$ABC"=Capture(ABC,named); "$$ABC"=Capture(ABC,unnamed); "$MATCH1"=Capture; "$$$ABC"=MultiCapture(ABC); "$$$123"=None. Doc example: pattern `console.log($MSG)` matches `console.log("hi")`; `foo($$$ARGS)` matches `foo()`, `foo(1)`, `foo(1, 2)`; `$A + $A` matches `x + x` not `x + y`.
TZ overlap: tz sym/exists = name search only; ledger row REJECTED (Rust binary dep).
Decision: C for a Python-only subset (stdlib `ast`), optional B-style pass-through to the `sg` binary when found on PATH (run as subprocess, `sg run -p PATTERN -l LANG --json`; never install). Status SELECTED (subset), target new module bin/tzgrep.py (`tz grep PATTERN [--lang py]`) or an `ast` mode in tzmap.
Spec for Python subset:
1. Parse pattern: replace metavars with placeholders valid in Python (`$A` -> `__MV_A__`, `$$$ARGS` -> `__MVM_ARGS__`, `$_` -> `__MV__`), `ast.parse(pattern)`; if the result is a single Expr use its `.value` as the template node; else the statement list.
2. Match(template, candidate): compare node types; for each field in `_fields` compare recursively; ignore `ctx`, lineno/col; Name with `__MV_X__` binds X to candidate (any expr node); bind-again requires `ast.dump(cand)` equal; a list field whose single element is `__MVM_X__` (as Name or Starred/arg) matches any list slice (collect the rest; support one multi per list); constants compare by value.
3. Walk all nodes of every .py file (reuse tzmap._files), report `path:line: first source line`, captures via `ast.get_source_segment`. Cap 50 matches.
Edge cases: pattern not parseable -> exit 2 with message; `$$NAME` unnamed capture not meaningful in ast, treat as `$NAME`; JS/TS: only through `sg` if present, else say UNSUPPORTED.
Test cases: `print($A)` hits `print(x)` not `print(x, y)`; `print($$$A)` hits both and `print()`; `$A == $A` hits `x == x` not `x == y`; `def $F($$$P): return $X` hits one-line return functions; `os.environ[$K]` hits subscripts only.

## 5. SylphxAI/repomap
URL https://github.com/SylphxAI/repomap | licence MIT (LICENSE: "Copyright (c) 2026 SylphxAI") | sha f770ec6d2b04 | Rust core (crates/repomap-core) + npm wrapper, v1.5.0 per README; description "code graph, search, call paths and change impact. No API key". Ledger row calls it "Node/TS runtime": outdated, it is now a Rust workspace (crates/).
Capabilities (README lines 172-192): six tools: map, search (BM25 over AST chunks + keywords + small static embedding), context (code + callers with call-site lines + callees + subtypes + importers + tests), impact (target symbol or `changed: true` from git diff; returns risk level LOW/MEDIUM/HIGH, direct callers, indirect by depth, importing files, modules touched, tests to run), call paths, PageRank, Louvain communities. Claims 83.0% top-10 file localization on SWE-bench Verified (bench/localization/localize.py) - vendor claim, not verified here.
Decision: D (idea reference) for impact output shape and risk grading; B only for permissively-licensed small ideas; engine is Rust + tree-sitter + embedding model (33 MB): E as dependency. Status REVIEWED. Bench script localize.py (Python) is useful as a model for ranked file discovery eval (see 7).
TZ overlap: `tz impact` (tzops.py:53) = git grep -w, one level, no risk, no call-sites.

## 6. Gap analysis and specs
### 6a. Change-impact analysis (TZ target bin/tzops.py impact; C rebuild, repomap = idea)
Current weakness: single-level word grep; test split by path regex; no depth; no diff mode.
Spec `tz impact [SYMBOL|FILE|--diff]`:
- `--diff`: symbols = defs whose line range intersects `git diff -U0 HEAD` hunks (map hunks to ast def ranges via end_lineno).
- Build name->files reverse index once with tzrank's define/ref scan (same word-token refs), restricted to files that `import` the defining module (python: `ast.Import/ImportFrom` module name or relative; js: `from '...'`/require path) when the symbol name length < 6 or defined in >5 files.
- BFS depth<=2: level 1 = files referencing symbol, level 2 = files referencing any def in level-1 files; stop at 40 files.
- Tests = level files matching `(^|/)(tests?|spec)/|test_|_test\.|\.spec\.|\.test\.`; print command hint only (never run).
- Risk: LOW if direct refs<=2 and no test gap; MEDIUM if 3-10 direct or >=1 untested direct caller; HIGH if >10 direct or defined in >5 files or name is dunder/`main`. Label EST (heuristic).
- Output <= 25 lines. Examples: symbol with 0 refs -> `0 callers, LOW`; symbol with 12 referencing files -> HIGH; change touching only a function body with refs only inside tests -> LOW + tests listed.
### 6b. Reference navigation (target tzmap.sym)
Add: `tz sym NAME --refs` printing file:line:text (max 30), excluding the def line, comments (`#`/`//` leading) and string-only mentions via `tokenize` for py (skip STRING/COMMENT tokens). This removes the "word refs include comments" caveat in the ledger. Example: file with `# parse_config here` and `x = parse_config()` -> only line of x.
### 6c. Code skeleton extraction for Python (bin/tzcompress.py skeleton already exists lines 13-31)
Already done via ast.unparse (docstring first line kept, body replaced with `...`, name set self-check at line 31). Gaps: (1) ast.unparse drops comments and reformats (acceptable, but report as LOSSY); (2) no `--max-lines`/per-class method filtering; (3) decorators and type annotations kept (good); (4) nested functions inside functions are dropped (good). Add `tz skel FILE [--sigs-only]` that prints `Class.method(args) -> ret  # L12-30` using end_lineno so the model can then read exact ranges (matches aider's lines-of-interest idea). Tokens: typically 85-95% smaller than file (EST; measure on tzrank.py: 111 lines).
### 6d. Ranked file discovery for a task (new, target tzrank.py `tz find "task text"`)
Pipeline (no embeddings, stdlib): idents = words in task (split camel/snake, lowercase, drop stopwords, len>2); score(file)= 3*name-part overlap with path parts + 2*def-name overlap + 1*BM25-lite on file text (tf-saturation k1=1.2, idf=log(1+N/df)); then feed top 5 as `mentioned_files` and all matched idents as `mentioned_idents` into tzrank personalization (section 1), return top 10 files with one reason each. Eval idea from repomap bench/localization: given a commit's task text and the files it touched, report hit@10; run on TZ's own git history (MEASURED, no paid API).
Example: task "fix dup read detection in tzopt" -> tzopt.py first (path overlap 'tzopt'), tz-guard.py next (refs read_decision).

## 7. Conflicts / notes
- tzrank personalization (focus) and `tz find` share one code path: build once in tzrank, keep tzmap light.
- Never import serena code (GPL); behaviour-only. repomap and ast-grep MIT, aider Apache-2.0: NOTICE required only for copied/adapted code (aider already listed; add ast-grep only if metavar grammar text is copied: it is not, spec is re-derived, so credit as idea in NOTICE optional).
- Hook budget: all above are on-demand CLI, zero cost to re-sent context unless the user runs them.

## 8. Ranked build list (value per re-sent token, highest first)
1. tzrank token-budget bisect + method-level defs + mentioned idents/personalization (S, high: a map capped at N tokens replaces reading files; deterministic test above). SELECTED.
2. `tz find "task"` ranked file discovery (S/M, high: replaces exploratory Reads/greps at chat start). SELECTED.
3. `tz impact --diff` with depth-2 and risk (M, medium-high: fewer wrong-file edits and re-reads). SELECTED.
4. tz sym name-path semantics + `--refs` without comments (S, medium). SELECTED.
5. tz skel with line ranges (S, medium; builds on tzcompress). SELECTED.
6. tz grep AST patterns Python subset (M, medium; optional `sg` pass-through). SELECTED.
7. py-tree-sitter, SolidLSP, repomap engine: REJECTED as dependencies (not stdlib-only).
Status per repo: aider SELECTED (extend), serena REVIEWED (C, GPL idea only), tree-sitter/py-tree-sitter REVIEWED (optional only), ast-grep SELECTED (C subset), repomap REVIEWED (D; ledger text outdated).

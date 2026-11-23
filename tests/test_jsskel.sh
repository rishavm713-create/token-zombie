#!/bin/bash
# JS/TS skeleton scanner (bin/tzcompress.py js_skeleton): strings, templates, regex, classes, TS, fail-open. Temp HOME only.
Z="$(cd "$(dirname "$0")/.." && pwd)"; pass=0; fail=0
T=$(mktemp -d); export HOME="$T/home"; mkdir -p "$HOME"; trap 'rm -rf "$T"' EXIT
ok() { if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
cat > "$T/t.py" <<'PY'
import sys
sys.path.insert(0, sys.argv[1] + '/bin')
import tzcompress as c
def chk(name, src, ok, has=(), lacks=(), count=None):
    sk, o = c.js_skeleton(src)
    good = o == ok and all(h in sk for h in has) and all(l not in sk for l in lacks) and (count is None or sk.count('{ ... }') == count)
    if not good: print('FAIL:', name, repr(sk), o)
    print('R', int(bool(good)))
chk('string braces', 'function a(x) { const s = "}{"; return \'}\' }\nconst k = 1;\n', True, ['function a(x) { ... }', 'const k = 1;'], ['return'], 1)
chk('template nested', 'function t(a) { return `x ${ {a:1}.a } }` + `${`}`}` }\nlet z = 2;\n', True, ['function t(a) { ... }', 'let z = 2;'], ['return'], 1)
chk('regex braces', 'function r(s) { return s.replace(/[{}]+\\//g, "") }\nconst q = /\\{/;\n', True, ['function r(s) { ... }', 'const q = /\\{/;'], ['replace'], 1)
cls = '@Component({selector: "x"})\nexport class A extends B {\n  @Input() name: string;\n  private x = 1;\n  constructor(private s: S) { super(); }\n  get v(): number { return 1 }\n  set v(n: number) { this.x = n }\n  static async *gen() { yield 1 }\n  public readonly h = (e) => { go(e) };\n  protected abstract m(): void;\n}\n'
chk('class decorators getters', cls, True, ['export class A extends B {', 'get v(): number { ... }', 'set v(n: number) { ... }', 'static async *gen() { ... }', 'constructor(private s: S) { ... }', '(e) => { ... }', '@Component({selector: "x"})', 'protected abstract m(): void;'], ['super()', 'yield'], 5)
ts = 'import { a } from "b";\nexport interface I { x: number; f(a: string): void }\nexport type T = (a: number) => { z: 1 };\nenum E { A, B }\nexport default function main(a: I): void { run() }\nexport async function* g() { yield 1 }\n'
chk('ts keeps decls', ts, True, ['interface I { x: number; f(a: string): void }', 'type T = (a: number) => { z: 1 };', 'enum E { A, B }', 'import { a } from "b";', 'function main(a: I): void { ... }', 'function* g() { ... }'], ['run()', 'yield'], 2)
chk('arrow', 'const f = (a) => { return a }\nconst g = async x => { await x }\nconst h = () => 5;\n', True, ['const f = (a) => { ... }', 'const g = async x => { ... }', 'const h = () => 5;'], ['return', 'await'], 2)
chk('control flow kept', 'if (x) { a() }\nfor (;;) { b() }\nconst o = { k: 1 };\n', True, ['if (x) { a() }', 'for (;;) { b() }', 'const o = { k: 1 };'], [], 0)
chk('division not regex', 'function d(a, b) { return a / b / 2 }\n', True, ['function d(a, b) { ... }'], [], 1)
chk('unbalanced fails open', 'function a( { oops', False)
chk('unbalanced brace', 'function a() { if (x) { 1 }\n', False)
chk('unterminated string', 'function a() { return "abc }\n', False)
sk, o = c.js_skeleton('function a() { 1 }\nfunction b() { 2 }\n'); print('R', int(sk.count('{ ... }') == 2 and o))
PY
o=$(python3 "$T/t.py" "$Z" 2>&1)
ok "scanner cases" '[ -z "$(echo "$o" | grep FAIL)" ] && [ "$(echo "$o" | grep -c "^R 1")" = 12 ]'
echo "$o" | grep -v '^R ' | grep . | head -20
echo 'export class K { go(a: number): number { return a + 1 } }' > "$T/s.ts"
for e in js ts jsx tsx mjs cjs; do cp "$T/s.ts" "$T/f.$e"; o=$(python3 "$Z/bin/tz" compress "$T/f.$e" 2>&1); ok "tz compress .$e" '[[ $o == *"go(a: number): number { ... }"* && $o != *"a + 1"* ]]'; done
printf 'function a( { oops' > "$T/bad.js"; o=$(python3 "$Z/bin/tz" compress "$T/bad.js" 2>&1); ok "tz compress fail open" '[[ $o == *"original kept"* ]]'
echo "pass $pass fail $fail"; [ "$fail" = 0 ]

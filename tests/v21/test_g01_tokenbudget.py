# g01 everything-claude-code token-budget-advisor: estimates, classes, depth options.
from harness import ok, done, Z
import tzdepth as B

ok('prose est', B.est_tokens('one two three four five') == round(5 * 1.3))
ok('code est', B.est_tokens('```x = f(a);```') == len('```x = f(a);```') // 4)
ok('empty min 1', B.est_tokens('') == 1)
ok('simple', B.classify('capital of France?') == 'simple')
ok('medium', B.classify('why is the sky blue') == 'medium')
ok('code req', B.classify('write a parser') == 'medium-high')
ok('complex', B.classify('compare these architecture options') == 'complex')
ok('creative', B.classify('a short story') == 'creative')
n, lo, hi = B.window('capital of France?')
ok('window mult', (lo, hi) == (n * 3, n * 8))
ok('cap', B.window('compare architecture options please now', cap=10)[1:] == (10, 10))
o = B.options('why is the sky blue')
ok('levels', list(o) == [25, 50, 75, 100] and o[25] < o[50] < o[75] < o[100])
ok('parse 50%', B.parse_level('50%') == 50)
ok('parse tldr', B.parse_level('tldr please') == 25)
ok('parse none', B.parse_level('hello') is None)
ok('render', '[100%]' in B.render('why is the sky blue'))
done()

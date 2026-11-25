# group 2: published token-zombie repo is the baseline; creator attribution must stay
import json, os
from harness import ok, done, Z


def read(p):
    return open(os.path.join(Z, p), encoding='utf-8').read()


ok('README keeps creator attribution', 'Created by [Rishav Mishra]' in read('README.md'))
ok('LICENSE keeps copyright holder', 'Rishav Mishra' in read('LICENSE'))
ok('plugin.json author kept', json.loads(read('.claude-plugin/plugin.json'))['author']['name'] == 'Rishav Mishra')
ok('NOTICE names all group 2 third-party repos', all(r in read('NOTICE') for r in (
    'rtk-ai/rtk', 'microsoft/TokenEconomizer', 'mattpocock/skills', 'obra/superpowers', 'langfuse/langfuse',
    'laude-institute/harbor', 'laude-institute/terminal-bench', 'morluto/rea', 'mksglu/context-mode', 'oraios/serena', 'parcadei/Continuous-Claude-v3')))
done()

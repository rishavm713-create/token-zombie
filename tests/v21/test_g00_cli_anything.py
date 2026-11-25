# CLI-Anything integration: tz clihelp (parity with upstream tests/test_skill_generator.py command extraction).
import json, os, subprocess, sys, tempfile, textwrap, time
from harness import ok, done, Z
import tzclihelp as C

T = tempfile.mkdtemp()


def put(name, text):
    path = os.path.join(T, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(textwrap.dedent(text))
    return path


def groups(text):
    return {g['name']: g for g in C.extract(textwrap.dedent(text))}


def names(group):
    return [c['name'] for c in group['commands']]


def run(*args):
    return subprocess.run([sys.executable, os.path.join(Z, 'bin', 'tzclihelp.py'), *args],
                          capture_output=True, text=True, timeout=30)


# parity: explicit click names win over function names
g = groups('''
    import click
    @click.group()
    def cli():
        pass
    @cli.group("remote-access")
    def remote_access_group():
        """Remote access commands."""
    @remote_access_group.command("list-active")
    def list_active_sessions():
        """List active sessions."""
    @cli.command(name="health-check")
    def health():
        """Check service health."""
''')
ok('declared group name', 'Remote Access' in g and 'Remote Access Group' not in g)
ok('declared command name', names(g['Remote Access']) == ['list-active'])
ok('name keyword', 'health-check' in names(g['Cli']) and 'health' not in names(g['Cli']))
ok('description', g['Remote Access']['commands'][0]['description'] == 'List active sessions.')

# parity: nested groups sharing a declared name, with a decorated root
g = groups('''
    import click
    @click.group()
    @click.pass_context
    def cli(ctx):
        pass
    @cli.group("configs")
    def configs_group():
        pass
    @configs_group.command("show")
    def show_config():
        pass
    @cli.group("alerts")
    def alerts():
        pass
    @alerts.group("configs")
    def alerts_configs():
        pass
    @alerts_configs.command("enable")
    def enable_alert_config():
        pass
''')
ok('nested disambiguated', list(g) == ['Cli', 'Configs', 'Alerts', 'Alerts Configs'])
ok('nested commands', names(g['Configs']) == ['show'] and names(g['Alerts Configs']) == ['enable'])
ok('top-level not prefixed by root', 'Cli Configs' not in g)
ok('no filler text', g['Configs']['description'] == '' and g['Configs']['commands'][0]['description'] == '')

# parity: nested decorator arguments and annotated functions
g = groups('''
    import click
    from pathlib import Path
    @click.group(context_settings=dict(help_option_names=["-h", "--help"]))
    @click.option("--format", type=click.Choice(["json", "text"]))
    def cli(format: str) -> None:
        pass
    @cli.command(context_settings=dict(ignore_unknown_options=True))
    @click.option("--output", type=click.Path(path_type=Path))
    def render(output):
        """Render output.

        Long details that stay out of the catalogue.
        """
    @cli.group("document")
    def document_group():
        """Document commands."""
    @document_group.command
    async def new_document() -> None:
        pass
''')
ok('nested decorator args', names(g['Cli']) == ['render'])
ok('first docstring line only', g['Cli']['commands'][0]['description'] == 'Render output.')
ok('bare decorator + async', names(g['Document']) == ['new-document'])

# parity: no groups -> General
g = groups('''
    import click
    @click.command()
    def export():
        pass
    @app.command("import-data")
    def import_data():
        pass
''')
ok('general group', list(g) == ['General'] and names(g['General']) == ['export', 'import-data'])

# kept although upstream drops them
g = groups('''
    import click
    from other import shared
    @click.group()
    def cli():
        pass
    @click.command()
    def lone():
        pass
    @shared.command()
    def borrowed():
        pass
''')
ok('loose click command kept', names(g['General']) == ['lone'])
ok('imported group command kept', names(g['Shared']) == ['borrowed'])
ok('plain functions ignored', C.extract('def command():\n    pass\n') == [])

# parity: large CLI stays fast
big = 'import click\n@click.group()\ndef cli():\n    pass\n' + ''.join(
    f'@cli.command(context_settings=dict(x=dict(y=1)))\ndef c{i}(a: str) -> None:\n    """Do {i}."""\n' for i in range(1500))
start = time.perf_counter()
many = C.extract(big)
ok('large cli', len(many[0]['commands']) == 1500 and time.perf_counter() - start < 2.0)

# target code is parsed, never run
marker = os.path.join(T, 'ran')
cli = put('app/tool_cli.py', f'''
    import click
    open({marker!r}, "w").close()
    @click.group()
    def cli():
        """Tool."""
    @cli.command()
    def go():
        """{"x" * 400}"""
''')
put('app/broken.py', 'import click\ndef (:\n')
put('app/venv/dep.py', 'import click\n@click.command()\ndef vendored():\n    pass\n')
put('app/.hidden/h.py', 'import click\n@click.command()\ndef secret():\n    pass\n')
found, skipped = C.scan(os.path.join(T, 'app'))
ok('dir scan', [os.path.normpath(f) for f, _ in found] == [os.path.normpath(cli)])
ok('syntax error reported', len(skipped) == 1 and 'SyntaxError' in skipped[0])
ok('never executed', not os.path.exists(marker))
text = C.render(found)
ok('clipped line', max(len(s) for s in text.split('\n')[1:]) == C.WIDTH)
cut = C.render(found, 2).split('\n')
ok('limit says what was cut', len(cut) == 3 and cut[-1].startswith('+1 more lines'))
ok('limit 0 = all', C.render(found, 0) == text)

r = run(os.path.join(T, 'app'))
ok('cli text', r.returncode == 0 and 'go - xxx' in r.stdout and 'skipped' in r.stderr and 'vendored' not in r.stdout)
r = run(cli, '--json')
data = json.loads(r.stdout)
ok('cli json', r.returncode == 0 and data[0]['groups'][0]['commands'][0]['name'] == 'go')
r = run(put('none.py', 'x = 1\n'))
ok('nothing found', r.returncode == 1 and 'no Click commands' in r.stdout)
r = run(os.path.join(T, 'missing'))
ok('missing path', r.returncode == 1 and 'no such path' in r.stderr)
ok('never executed by cli', not os.path.exists(marker))

lic = os.path.join(Z, 'third_party', 'cli-anything', 'LICENSE')
ok('licence kept', os.path.isfile(lic) and 'Apache License' in open(lic, encoding='utf-8').read(200))
done()

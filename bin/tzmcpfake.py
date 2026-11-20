#!/usr/bin/env python3
# Local MCP test server for `tz preflight --smoke` S4 (stdio, newline-delimited JSON-RPC 2.0, no network, no deps).
# One tool `bigtext`: returns ~20k chars; a salted code word sits only in the MIDDLE, so a model that can quote it
# received the untrimmed output (the trim keeps head + tail). Salt: env TZ_SMOKE_SALT.
import json, os, sys

SALT = os.environ.get('TZ_SMOKE_SALT', 'nosalt')


def text():
    filler = [f'line {i:04d} {SALT} filler text for the smoke test' for i in range(400)]
    filler[200] = f'MIDDLE-CODEWORD-{SALT}'
    return '\n'.join(filler)


def reply(i, result):
    sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': i, 'result': result}) + '\n'); sys.stdout.flush()


for line in sys.stdin:
    try:
        m = json.loads(line)
    except Exception:
        continue
    meth, i = m.get('method'), m.get('id')
    if i is None:  # notification (e.g. notifications/initialized)
        continue
    if meth == 'initialize':
        reply(i, {'protocolVersion': (m.get('params') or {}).get('protocolVersion', '2025-06-18'),
                  'capabilities': {'tools': {}}, 'serverInfo': {'name': 'tzsmoke', 'version': '1'}})
    elif meth == 'tools/list':
        reply(i, {'tools': [{'name': 'bigtext', 'description': 'Returns a long test text.',
                             'inputSchema': {'type': 'object', 'properties': {}}}]})
    elif meth == 'tools/call':
        reply(i, {'content': [{'type': 'text', 'text': text()}]})
    else:
        sys.stdout.write(json.dumps({'jsonrpc': '2.0', 'id': i, 'error': {'code': -32601, 'message': 'no method'}}) + '\n'); sys.stdout.flush()

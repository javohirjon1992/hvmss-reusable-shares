"""Exercise the local dashboard routes using a temporary loopback port."""
import json
import sys
import threading
from pathlib import Path
from urllib.request import Request, build_opener, ProxyHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Handler, ThreadingHTTPServer

client = build_opener(ProxyHandler({}))
with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:'+str(server.server_port)
    try:
        data = json.load(client.open(base+'/catalog'))
        assert len(data['records']) == 152 and len(data['figures']) == 7
        assert client.open(base+'/paper.pdf').read(4)==b'%PDF'
        for path in data['figures']:
            assert client.open(base+path).read(8)==b'\x89PNG\r\n\x1a\n'
        for variant in ['archived','specified','protocol']:
            for operation in ['HBV','RMSS']:
                req=Request(base+'/measure', data=json.dumps(dict(version=variant,operation=operation,n=8,k=4)).encode(),headers={'Content-Type':'application/json'})
                row=json.load(client.open(req))
                assert len(row['samples_ms'])==21 and row['q1_ms']<=row['median_ms']<=row['q3_ms']
        print('Passed: archive, PDF, seven figures and six benchmark combinations.')
    finally:
        server.shutdown()

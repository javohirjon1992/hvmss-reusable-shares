"""Local research dashboard. Start with python app.py; no third-party packages."""
import argparse
import csv
import json
import os
import platform
import statistics
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'reproducibility'))
from variant_check import implementation

FILES = {
    '/': (ROOT / 'ui/index.html', 'text/html; charset=utf-8'),
    '/paper.pdf': (ROOT / 'docs/paper.pdf', 'application/pdf'),
    '/recorded.csv': (ROOT / 'reproducibility/variant_observations/timings.csv', 'text/csv'),
}
for figure in sorted((ROOT / 'figures').glob('*.png')):
    FILES['/figures/' + figure.name] = (figure, 'image/png')
RUN_LOCK = threading.Lock()


def measure(options):
    if not isinstance(options, dict):
        raise ValueError('Expected an object.')
    version = options.get('version')
    operation = options.get('operation')
    n, k = options.get('n'), options.get('k')
    if version not in ('archived', 'specified', 'protocol') or operation not in ('HBV', 'RMSS'):
        raise ValueError('Unknown protocol or implementation.')
    if type(n) is not int or n not in (8, 16, 32, 64, 128, 256):
        raise ValueError('Unsupported committee size.')
    if type(k) is not int or k not in (1, 4, 16, 64):
        raise ValueError('Unsupported batch size.')
    m = implementation('code' if version == 'archived' else version)
    session = uuid.uuid4().hex
    t = n // 2
    secrets = list(range(1, k+1))
    if operation == 'HBV':
        pub, openings = m.hbv_deal(secrets, n, t, session)
        def verify():
            return m.hbv_verify(pub, openings[-1])
    else:
        setup, seeds, _ = m.rmss_setup(n, t)
        pub = m.rmss_add(secrets, session, setup, seeds)
        if not m.rmss_verify_public(setup, pub):
            raise RuntimeError('Public record check failed.')
        def verify():
            return m.rmss_verify_participant(setup, pub, n, seeds[-1])
    samples = []
    for i in range(24):
        start = time.perf_counter_ns()
        accepted = verify()
        elapsed = (time.perf_counter_ns() - start) / 1e6
        if not accepted:
            raise RuntimeError('Recipient verification failed.')
        if i >= 3:
            samples.append(elapsed)
    quartiles = statistics.quantiles(samples, method='inclusive')
    return dict(version=version, operation=operation, n=n, t=t, k=k,
                utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                os=platform.system()+' '+platform.release(), architecture=platform.machine(),
                processor=platform.processor() or os.environ.get('PROCESSOR_IDENTIFIER','') or 'unreported',
                warmups=3, repetitions=len(samples), median_ms=quartiles[1],
                q1_ms=quartiles[0], q3_ms=quartiles[2], samples_ms=samples)


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, data, kind='application/json'):
        if isinstance(data, dict) or isinstance(data, list):
            data = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/catalog':
            with FILES['/recorded.csv'][0].open(newline='') as f:
                records = list(csv.DictReader(f))
            self.respond(200, dict(records=records, figures=[s for s in FILES if s.startswith('/figures/')]))
        elif self.path in FILES:
            path, mime = FILES[self.path]
            self.respond(200, path.read_bytes(), mime)
        else:
            self.respond(404, dict(error='Unknown resource.'))

    def do_POST(self):
        host = '127.0.0.1:'+str(self.server.server_port)
        if self.path != '/measure' or self.headers.get('Host') != host or self.headers.get('Origin') not in (None,'http://'+host):
            return self.respond(403, dict(error='Local requests only.'))
        if self.headers.get_content_type() != 'application/json':
            return self.respond(415, dict(error='JSON required.'))
        if not RUN_LOCK.acquire(blocking=False):
            return self.respond(409, dict(error='A measurement is already running.'))
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 4096:
                raise ValueError('Invalid request size.')
            result = measure(json.loads(self.rfile.read(size)))
            self.respond(200, result)
        except (ValueError, TypeError) as exc:
            self.respond(400, dict(error=str(exc)))
        except RuntimeError as exc:
            self.respond(500, dict(error=str(exc)))
        finally:
            RUN_LOCK.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        address = 'http://127.0.0.1:'+str(server.server_port)
        print('HVMSS dashboard:', address, flush=True)
        if not args.no_browser:
            threading.Timer(.4, webbrowser.open, args=(address,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

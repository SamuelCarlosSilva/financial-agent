"""Upstream falso para o smoke test do proxy: devolve em JSON o que recebeu.

Responde 200 a qualquer método e caminho com `{method, path, query, headers}`, cabeçalhos em
minúsculas. Faz o papel da API em `scripts/proxy-smoke.sh`. Só usa a biblioteca padrão.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class Echo(BaseHTTPRequestHandler):
    def _reply(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        url = urlsplit(self.path)
        body = json.dumps(
            {
                "method": self.command,
                "path": url.path,
                "query": url.query,
                "headers": {k.lower(): v for k, v in self.headers.items()},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_DELETE = _reply

    def log_message(self, format: str, *args: object) -> None:
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Echo).serve_forever()

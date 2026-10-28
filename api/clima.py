import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from boletin.web import consultar  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        consulta = parse_qs(urlparse(self.path).query)
        ciudad = (consulta.get("ciudad") or [""])[0]
        pais = (consulta.get("pais") or [""])[0] or None
        estado, cuerpo = consultar(ciudad, pais)
        datos = json.dumps(cuerpo).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import subprocess

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        data = json.loads(self.rfile.read(length))
        
        # Guardar el input temporalmente
        with open('temp_input.json', 'w') as f:
            json.dump(data, f)
        
        # Correr el script
        result = subprocess.run(
            ['python', 'actualizar_2026.py', 'temp_input.json'],
            capture_output=True, text=True
        )
        
        self.send_response(200)
        self.end_headers()
        response = {'ok': result.returncode == 0, 'log': result.stdout}
        self.wfile.write(json.dumps(response).encode())

print('Servidor corriendo en http://localhost:8001')
HTTPServer(('localhost', 8001), Handler).serve_forever()
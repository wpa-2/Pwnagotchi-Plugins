import subprocess
import logging
from flask import Flask, request, render_template_string, Response
import pwnagotchi.plugins as plugins
from functools import wraps

class WebSSHPlugin(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '0.1.0'
    __license__ = 'GPL3'
    __description__ = 'A Plugin to issue SSH commands via a browser'

    def __init__(self, config=None):
        super().__init__()
        logging.debug("WebSSHPlugin created")
        self.app = Flask(__name__)
        self.config = config or {}
        self.options = {}

    def on_loaded(self):
        """Called when the plugin is loaded."""
        logging.info("WebSSHPlugin loaded")

        # Initialize self.options with default values
        self.options = {
            "username": self.config.get("main.plugins.webssh.username", "changeme"),
            "password": self.config.get("main.plugins.webssh.password", "changeme"),
            "port": self.config.get("main.plugins.webssh.port", 8082),
        }

        logging.debug(f"WebSSHPlugin config: {self.options}")

        # Set up Flask routes and start the server
        self.app.before_request(self.requires_auth)  # Attach auth check to all routes
        self._register_routes()
        self.app.run(host='::', port=self.options["port"])

    def _register_routes(self):
        """Register Flask routes."""
        @self.app.route('/')
        def index():
            """Home page for SSH command input."""
            return render_template_string("""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>WEB-SSH Command Executor</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            margin: 0;
                            padding: 0;
                            display: flex;
                            flex-direction: column;
                            align-items: center;
                            height: 100vh;
                            background-color: #f4f4f9;
                        }
                        .container {
                            text-align: center;
                            background: #ffffff;
                            padding: 20px;
                            border-radius: 8px;
                            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                            width: 90%;
                            max-width: 400px;
                            margin-top: 20px;
                        }
                        h1 {
                            font-size: 1.5rem;
                            margin-bottom: 20px;
                        }
                        form {
                            display: flex;
                            flex-direction: column;
                        }
                        input[type="text"] {
                            font-size: 1rem;
                            padding: 10px;
                            margin-bottom: 15px;
                            border: 1px solid #ccc;
                            border-radius: 4px;
                        }
                        input[type="submit"] {
                            font-size: 1rem;
                            padding: 10px;
                            color: #fff;
                            background-color: #007BFF;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                        }
                        input[type="submit"]:hover {
                            background-color: #0056b3;
                        }
                        .shortcuts {
                            margin-top: 20px;
                        }
                        .shortcuts button {
                            font-size: 1rem;
                            margin: 5px;
                            padding: 10px;
                            color: #fff;
                            background-color: #28a745;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                        }
                        .shortcuts button:hover {
                            background-color: #218838;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>WEB-SSH Command Executor</h1>
                        <form action="/execute" method="post">
                            <input type="text" id="commandInput" name="command" placeholder="Enter command" required>
                            <input type="submit" value="Execute">
                        </form>
                        <div class="shortcuts">
                            <h2>Command Shortcuts</h2>
                            <form action="/execute" method="post" style="display: inline;">
                                <input type="hidden" name="command" value="sudo shutdown -h now">
                                <button type="submit">Shutdown</button>
                            </form>
                            <form action="/execute" method="post" style="display: inline;">
                                <input type="hidden" name="command" value="sudo reboot">
                                <button type="submit">Reboot</button>
                            </form>
                            <form action="/execute" method="post" style="display: inline;">
                                <input type="hidden" name="command" value="ping -c 4 8.8.8.8">
                                <button type="submit">Ping</button>
                            </form>
                            <form action="/execute" method="post" style="display: inline;">
                                <input type="hidden" name="command" value="sudo pwngrid --inbox">
                                <button type="submit">Inbox</button>
                            </form>
                            <form action="/execute" method="post" style="display: inline;">
                                <input type="hidden" name="command" value="sudo killall -USR1 pwnagotchi">
                                <button type="submit">Pwnkill</button>
                            </form>
                            <form action="/execute" method="post" style="display: inline;">
                                <input type="hidden" name="command" value="ls /usr/local/share/pwnagotchi/custom-plugins">
                                <button type="submit">Plugins</button>
                            </form>
                        </div>
                    </div>
                </body>
                </html>
            """)

        @self.app.route('/execute', methods=['POST'])
        def execute_command():
            """Execute SSH command and return output."""
            command = request.form['command']
            output = self.ssh_execute_command(command)
            return render_template_string("""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Command Output</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            margin: 0;
                            padding: 20px;
                            background-color: #f4f4f9;
                        }
                        .output-container {
                            max-width: 800px;
                            margin: 0 auto;
                            background: #ffffff;
                            padding: 20px;
                            border-radius: 8px;
                            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                        }
                        h1 {
                            font-size: 1.5rem;
                            margin-bottom: 20px;
                        }
                        pre {
                            text-align: left;
                            background: #f8f9fa;
                            padding: 15px;
                            border-radius: 5px;
                            overflow-x: auto;
                            font-size: 0.9rem;
                        }
                        a {
                            display: inline-block;
                            margin-top: 15px;
                            font-size: 1rem;
                            text-decoration: none;
                            color: #007BFF;
                        }
                        a:hover {
                            text-decoration: underline;
                        }
                    </style>
                </head>
                <body>
                    <div class="output-container">
                        <h1>Command Output</h1>
                        <pre>{{ output }}</pre>
                        <a href="/">Back</a>
                    </div>
                </body>
                </html>
            """, output=output)

    def ssh_execute_command(self, command):
        """Executes the SSH command on the local device."""
        try:
            result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
            return result.decode('utf-8')
        except subprocess.CalledProcessError as e:
            return f"Error executing command: {e.output.decode('utf-8')}"

    def check_auth(self, username, password):
        """Check if username and password match."""
        return username == self.options["username"] and password == self.options["password"]

    def requires_auth(self, f=None):
        """Enforce basic authentication."""
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not self.check_auth(auth.username, auth.password):
                return self._unauthorized_response()
            return f(*args, **kwargs)

        # If no function is passed (e.g., as a before_request handler), just check auth
        if f is None:
            auth = request.authorization
            if not auth or not self.check_auth(auth.username, self.options["password"]):
                return self._unauthorized_response()
            return None

        return decorated

    def _unauthorized_response(self):
        """Generate a 401 Unauthorized response with the WWW-Authenticate header."""
        response = Response(
            'Unauthorized access. Please provide valid credentials.',
            status=401
        )
        response.headers['WWW-Authenticate'] = 'Basic realm="WebSSH"'
        return response

    def on_unload(self, ui):
        """Called when the plugin is unloaded."""
        logging.info("WebSSHPlugin unloaded")

import os
import subprocess
import uuid

import nest_asyncio
import uvicorn
from pyngrok import ngrok

try:
    from google.colab import drive

    colab_env = True
except ImportError:
    colab_env = False


EXTENSIONS = ["ms-python.python", "ms-toolsai.jupyter", "TabNine.tabnine-vscode", "vscodevim.vim"]
CODESERVER_VERSION = "3.8.0"


class ColabCode:
    def __init__(
        self,
        port=10000,
        password=None,
        authtoken=None,
        mount_drive=False,
        user_data_dir=None,
        config=None,
        extensions_dir=None,
        code=True,
        lab=False,
    ):
        self.port = port
        self.password = password
        self.authtoken = authtoken
        self._config = config
        self._extensions_dir = extensions_dir
        self._mount = mount_drive
        self._user_data_dir = user_data_dir
        self._code = code
        self._lab = lab
        if self._lab:
            self._start_server()
            self._run_lab()
        if self._code:
            self._install_code()
            self._install_extensions()
            self._start_server()
            self._run_code()

    @staticmethod
    def _install_code():
        subprocess.run(
            ["wget", "https://code-server.dev/install.sh"], stdout=subprocess.PIPE
        )
        subprocess.run(
            ["sh", "install.sh", "--version", f"{CODESERVER_VERSION}"],
            stdout=subprocess.PIPE,
        )

    def _install_extensions(self):
        for ext in EXTENSIONS:
            if self._extensions_dir:
                subprocess.run(
                    [
                        "code-server",
                        "--extensions-dir",
                        f"{self._extensions_dir}",
                        "--allow-http", "--no-auth",
                        "--install-extension",
                        f"{ext}",
                    ]
                )
            else:
                subprocess.run(["code-server", "--allow-http", "--no-auth", "--install-extension", f"{ext}"])

    def _start_server(self):
        if self.authtoken:
            ngrok.set_auth_token(self.authtoken)
        active_tunnels = ngrok.get_tunnels()
        for tunnel in active_tunnels:
            public_url = tunnel.public_url
            ngrok.disconnect(public_url)
        url = ngrok.connect(addr=self.port, options={"bind_tls": True})
        if self._code:
            print(f"Code Server can be accessed on: {url}")
        else:
            print(f"Public URL: {url}")

    def _run_lab(self):
        token = str(uuid.uuid1())
        print(f"Jupyter lab token: {token}")
        base_cmd = "jupyter-lab --ip='localhost' --allow-root --ServerApp.allow_remote_access=True --no-browser"
        os.system(f"fuser -n tcp -k {self.port}")
        if self._mount and colab_env:
            drive.mount("/content/drive")
        if self.password:
            lab_cmd = f" --ServerApp.token='{token}' --ServerApp.password='{self.password}' --port {self.port}"
        else:
            lab_cmd = f" --ServerApp.token='{token}' --ServerApp.password='' --port {self.port}"
        lab_cmd = base_cmd + lab_cmd
        with subprocess.Popen(
            [lab_cmd],
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as proc:
            for line in proc.stdout:
                print(line, end="")

    def _run_code(self):
        os.system(f"fuser -n tcp -k {self.port}")
        prefix = []
        suffix = []
        suffix.append(f"--port {self.port}")
        suffix.append(f"--disable-telemetry")
        code_cmd = "code-server "
        if self._mount and colab_env:
            drive.mount("/content/drive")
        if self.password:
            prefix.append(f"PASSWORD={self.password} ")
            suffix.append("--auth none")
        if self._config:
            suffix.append(f"--config {self._config}")
        if self._extensions_dir:
            suffix.append(f"--extensions-dir {self._extensions_dir}")
        if self._user_data_dir:
            suffix.append(f"--user-data-dir {self._user_data_dir}")
        code_cmd = " ".join(prefix) + code_cmd + " ".join(suffix)
        with subprocess.Popen(
            [code_cmd],
            shell=True,
            stdout=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as proc:
            for line in proc.stdout:
                print(line, end="")

    def run_app(self, app, workers=1):
        self._start_server()
        nest_asyncio.apply()
        uvicorn.run(app, host="127.0.0.1", port=self.port, workers=workers)

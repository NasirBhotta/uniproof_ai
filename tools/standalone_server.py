"""
Antigravity Standalone Language Server Launcher
Author: Nasir Bhutta
Description: Launches language_server_windows_x64.exe headlessly without needing
             the Antigravity IDE / VS Code GUI open, runs the full handshake,
             and exposes a live LLM session for custom agents and scripts.
"""

import os
import sys
import ssl
import json
import uuid
import time
import socket
import base64
import signal
import subprocess
import threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SESSION_FILE = os.path.join(PROJECT_ROOT, ".antigravity_session.json")
SERVICE = "/exa.language_server_pb.LanguageServerService"

# Default binary search paths
KNOWN_EXE_PATHS = [
    r"d:\Antigravity IDE\resources\app\extensions\antigravity\bin\language_server_windows_x64.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Antigravity\resources\app\extensions\antigravity\bin\language_server_windows_x64.exe"),
    os.path.expandvars(r"%PROGRAMFILES%\Antigravity\resources\app\extensions\antigravity\bin\language_server_windows_x64.exe"),
]


def find_language_server_binary() -> str:
    """Finds the language_server_windows_x64.exe binary on the system"""
    for path in KNOWN_EXE_PATHS:
        if os.path.exists(path):
            return path

    try:
        ps = 'Get-ChildItem -Path "C:\\", "D:\\" -Filter "language_server_windows_x64.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName'
        enc = base64.b64encode(ps.encode("utf-16le")).decode("ascii")
        res = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc], capture_output=True, text=True, timeout=10)
        found = res.stdout.strip()
        if found and os.path.exists(found):
            return found
    except Exception:
        pass

    raise FileNotFoundError("Could not find language_server_windows_x64.exe! Please check installation path.")


def find_free_port() -> int:
    """Finds a free TCP port on localhost"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_process_listening_port(pid: int) -> int:
    """Gets the active listening port for the spawned server PID"""
    ps = f"""
    $po = Get-NetTCPConnection -OwningProcess {pid} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort | Sort-Object
    $po | Select-Object -First 1
    """
    enc = base64.b64encode(ps.encode("utf-16le")).decode("ascii")
    for _ in range(15):
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc], capture_output=True, text=True)
            port_str = res.stdout.strip()
            if port_str and port_str.isdigit():
                return int(port_str)
        except Exception:
            pass
        time.sleep(0.5)
    return None


def make_grpc_call(base_url: str, endpoint: str, csrf_token: str, payload: dict = None) -> object:
    """Executes gRPC-web POST requests with correct headers"""
    url = f"{base_url}{SERVICE}/{endpoint}"
    body = json.dumps(payload if payload is not None else {}).encode("utf-8")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "vscode-file://vscode-app",
        "connect-protocol-version": "1",
        "x-codeium-csrf-token": csrf_token,
        "Content-Length": str(len(body)),
    }

    req = Request(url, data=body, method="POST", headers=headers)
    ctx = ssl._create_unverified_context()

    try:
        with urlopen(req, context=ctx, timeout=10) as resp:
            response_text = resp.read().decode("utf-8", errors="replace")
            return json.loads(response_text) if response_text.strip() else {}
    except HTTPError as e:
        print(f"[-] HTTP Error on {endpoint}: {e.code} - {e.read().decode('utf-8', errors='replace')}")
        return None
    except Exception as e:
        print(f"[-] Request failed on {endpoint}: {e}")
        return None


def save_session(port: int, csrf_token: str, conversation_id: str, workspace_uri: str, pid: int = None):
    """Saves session info so custom agents and scripts can reuse the exact same chat session"""
    data = {
        "port": int(port),
        "csrf_token": csrf_token,
        "conversation_id": conversation_id,
        "workspace_uri": workspace_uri,
        "server_pid": pid,
        "mode": "standalone",
        "updated_at": time.time()
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def start_standalone_server(custom_port: int = None, custom_csrf: str = None, workspace_path: str = None):
    """Launches and initializes the standalone Antigravity Language Server"""
    print("=" * 65)
    print(" [*] ANTIGRAVITY STANDALONE HEADLESS SERVER LAUNCHER")
    print("=" * 65)

    # 1. Locate binary
    exe_path = find_language_server_binary()
    print(f"[+] Found Binary : {exe_path}")

    # 2. Setup Tokens and Ports
    csrf_token = custom_csrf or str(uuid.uuid4())
    ext_csrf_token = str(uuid.uuid4())
    ext_port = custom_port or find_free_port()

    target_ws = Path(os.path.abspath(workspace_path or PROJECT_ROOT)).as_uri()

    print(f"[*] Assigned Port  : {ext_port}")
    print(f"[*] Assigned CSRF  : {csrf_token}")
    print(f"[*] Workspace URI  : {target_ws}")

    # 3. Launch Process
    cmd = [
        exe_path,
        "--csrf_token", csrf_token,
        "--extension_server_port", str(ext_port),
        "--extension_server_csrf_token", ext_csrf_token,
        "--app_data_dir", "antigravity-ide",
        "--subclient_type", "ide",
        "--cloud_code_endpoint", "https://cloudcode-pa.googleapis.com"
    ]

    print("\n[*] Spawning background Language Server process...")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    print(f"[+] Server Process Running with PID: {proc.pid}")

    def log_stream():
        for line in proc.stdout:
            if any(k in line.lower() for k in ["listening", "error", "ready", "started"]):
                print(f"    [SERVER] {line.strip()}")

    threading.Thread(target=log_stream, daemon=True).start()

    # 4. Wait for listening port
    print("[*] Detecting active listening port...")
    active_port = get_process_listening_port(proc.pid) or ext_port
    print(f"[+] Verified Active Listening Port: {active_port}")

    base_url = f"https://127.0.0.1:{active_port}"

    # 5. Execute 9-Step Handshake
    print("\n[*] Executing 9-Step Initialization Handshake...")
    time.sleep(1.0)

    make_grpc_call(base_url, "ListPages", csrf_token, {})
    make_grpc_call(base_url, "GetAgentScripts", csrf_token, {})
    make_grpc_call(base_url, "GetMendelFlags", csrf_token, {})
    make_grpc_call(base_url, "GetAgentScripts", csrf_token, {"workspaceUris": [target_ws]})
    make_grpc_call(base_url, "GetRepoInfos", csrf_token, {"repoUris": [target_ws]})
    make_grpc_call(base_url, "GetAllWorkflows", csrf_token, {"workspaceUris": [target_ws], "activeProfile": ""})
    make_grpc_call(base_url, "ListMcpPrompts", csrf_token, {})

    cascade_config = {
        "plannerConfig": {
            "conversational": {"plannerMode": "CONVERSATIONAL_PLANNER_MODE_DEFAULT", "agenticMode": False},
            "toolConfig": {"runCommand": {"autoCommandConfig": {}}, "notifyUser": {}},
            "requestedModel": {"model": "MODEL_PLACEHOLDER_M298"},
            "knowledgeConfig": {"enabled": False}
        },
        "conversationHistoryConfig": {"enabled": False}
    }
    make_grpc_call(base_url, "GetSlashCommands", csrf_token, {"cascadeConfig": cascade_config, "workspaceUris": [target_ws], "activeProfile": ""})
    make_grpc_call(base_url, "RefreshMcpServers", csrf_token, {})

    print("[+] Handshake Completed Successfully!")

    # 6. Start Live Cascade Chat
    conversation_id = str(uuid.uuid4())
    print(f"\n[*] Registering Chat Session with ID: {conversation_id}")

    start_payload = {
        "source": "CORTEX_TRAJECTORY_SOURCE_CASCADE_CLIENT",
        "cascadeId": conversation_id,
        "requestedModel": "MODEL_PLACEHOLDER_M298",
        "workspaceUris": [target_ws],
        "activeProfile": ""
    }

    res = make_grpc_call(base_url, "StartCascade", csrf_token, start_payload)
    if res is not None:
        print("[+] StartCascade Success! Session is 100% LIVE.")
        print(f"[+] Active Conversation ID: {conversation_id}")
        save_session(active_port, csrf_token, conversation_id, target_ws, proc.pid)
        print(f"[+] Saved session state to: {SESSION_FILE}")

    print("\n" + "=" * 65)
    print(" [+] STANDALONE SERVER READY! (No IDE window needed)")
    print(" You can now run your agents or test.py without opening IDE.")
    print(" Press Ctrl+C to stop the standalone server.")
    print("=" * 65 + "\n")

    def shutdown(signum=None, frame=None):
        print("\n[*] Shutting down Standalone Language Server...")
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        print("[+] Server stopped cleanly.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    start_standalone_server()

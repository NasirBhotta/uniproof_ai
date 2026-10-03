"""
Antigravity Language Server Auto-Connect & Session Initializer
Author: Nasir Bhutta
Description: Auto-detects the running Antigravity Language Server, executes the 9-step
             handshake, initializes a live cascade session, and writes session config
             to the project root .antigravity_session.json.
"""

import os
import sys
import re
import subprocess
import json
import ssl
import uuid
import time
import base64
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

# Root workspace directory & session file
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SESSION_FILE = os.path.join(PROJECT_ROOT, ".antigravity_session.json")

SERVICE = "/exa.language_server_pb.LanguageServerService"


def find_vscode_language_server_info():
    """Detects active Antigravity Language Server PID, Port, and CSRF Token via PowerShell"""
    ps_script = """
    $p = Get-CimInstance Win32_Process -Filter "Name LIKE '%language_server_windows_x64%'" | Select-Object -First 1
    if ($p) {
        $id = $p.ProcessId
        $po = Get-NetTCPConnection -OwningProcess $id -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LocalPort | Sort-Object
        [PSCustomObject]@{
            PID  = $id
            Port = ($po | Select-Object -First 1)
            Cmd  = $p.CommandLine
        } | ConvertTo-Json -Compress
    }
    """
    try:
        encoded_cmd = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded_cmd],
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        if not output:
            print("[-] Language Server process or listening port not found.")
            return None, None

        data = json.loads(output)
        port = int(data.get("Port"))
        cmd_line = data.get("Cmd", "")
        token_match = re.search(r"--csrf_token\s+([a-fA-F0-9-]+)", cmd_line)
        csrf_token = token_match.group(1) if token_match else None

        print(f"[+] Active PID    : {data.get('PID')}")
        print(f"[+] Selected Port : {port}")
        print(f"[+] CSRF Token    : {csrf_token}")

        return csrf_token, port
    except Exception as e:
        print(f"[-] Error detecting language server: {e}")
        return None, None


def save_session(port: int, csrf_token: str, conversation_id: str, workspace_uri: str):
    """Saves active session details to the root JSON file for provider and agents to reuse"""
    data = {
        "port": int(port),
        "csrf_token": csrf_token,
        "conversation_id": conversation_id,
        "workspace_uri": workspace_uri,
        "updated_at": time.time()
    }
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def make_grpc_call(base_url: str, endpoint: str, csrf_token: str, payload: dict = None) -> dict:
    """Helper function to make gRPC-web POST requests with correct headers"""
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
        print(f"[-] Failed on {endpoint}: {e}")
        return None


def auto_connect_session(workspace_dir: str = None) -> bool:
    print("[*] Scanning active Antigravity Language Server process...")
    csrf_token, port = find_vscode_language_server_info()

    if not csrf_token or not port:
        print("[-] Active Language Server or Port could not be auto-detected!")
        print("[-] Please make sure Antigravity IDE is running.")
        return False

    base_url = f"https://127.0.0.1:{port}"
    target_ws = Path(workspace_dir or PROJECT_ROOT).as_uri()
    print(f"[+] Active Workspace URI   : {target_ws}")

    print("\n[*] Starting 9-Step Initialization Handshake...")

    # 1. ListPages
    print("[1/9] Calling ListPages...")
    make_grpc_call(base_url, "ListPages", csrf_token, {})

    # 2. GetAgentScripts (Global check)
    print("[2/9] Calling GetAgentScripts (Global)...")
    make_grpc_call(base_url, "GetAgentScripts", csrf_token, {})

    # 3. GetMendelFlags
    print("[3/9] Fetching Mendel Flags & Experiment Configs...")
    make_grpc_call(base_url, "GetMendelFlags", csrf_token, {})

    # 4. GetAgentScripts (Workspace-bound)
    print("[4/9] Calling GetAgentScripts with Workspace...")
    make_grpc_call(base_url, "GetAgentScripts", csrf_token, {"workspaceUris": [target_ws]})

    # 5. GetRepoInfos
    print("[5/9] Fetching Repository Infos & Git Branch...")
    make_grpc_call(base_url, "GetRepoInfos", csrf_token, {"repoUris": [target_ws]})

    # 6. GetAllWorkflows
    print("[6/9] Syncing Workflows...")
    make_grpc_call(base_url, "GetAllWorkflows", csrf_token, {"workspaceUris": [target_ws], "activeProfile": ""})

    # 7. ListMcpPrompts
    print("[7/9] Discovering MCP Prompts...")
    make_grpc_call(base_url, "ListMcpPrompts", csrf_token, {})

    # 8. GetSlashCommands
    print("[8/9] Registering System Commands & Skills...")
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

    # 9. RefreshMcpServers
    print("[9/9] Refreshing MCP Servers...")
    make_grpc_call(base_url, "RefreshMcpServers", csrf_token, {})

    print("[+] Initialization Handshake Completed Successfully!")

    # Final: StartCascade Session
    conversation_id = str(uuid.uuid4())
    print(f"\n[*] Initializing Chat Session with ID: {conversation_id}")

    start_cascade_payload = {
        "source": "CORTEX_TRAJECTORY_SOURCE_CASCADE_CLIENT",
        "cascadeId": conversation_id,
        "requestedModel": "MODEL_PLACEHOLDER_M298",
        "workspaceUris": [target_ws],
        "activeProfile": ""
    }

    res = make_grpc_call(base_url, "StartCascade", csrf_token, start_cascade_payload)
    if res is not None:
        print("[+] StartCascade Success! Session is fully live and ready.")
        print(f"[+] Active Conversation ID: {conversation_id}")
        save_session(port, csrf_token, conversation_id, target_ws)
        print(f"[+] Saved active session to: {SESSION_FILE}")
        return True
    return False


if __name__ == "__main__":
    auto_connect_session()

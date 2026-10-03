"""
Antigravity Headless Background Service Launcher
Author: Nasir
Description: Starts the Antigravity background engine with fixed port and auto-auth,
             runs the full 9-step initialization handshake, and connects your agents
             without needing you to manually open or manage the IDE window.
"""

import os
import sys
import time
import json
import uuid
import base64
import subprocess
from pathlib import Path

# Import auto_connect from current directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import auto_connect

FIXED_PORT = 50262
SESSION_FILE = auto_connect.SESSION_FILE


def start_service(workspace_path: str = None):
    print("=" * 65)
    print(" [*] ANTIGRAVITY AUTHENTICATED BACKGROUND SERVICE LAUNCHER")
    print("=" * 65)

    ws_path = os.path.abspath(workspace_path or os.getcwd())
    ws_uri = Path(ws_path).as_uri()

    print(f"[*] Target Workspace: {ws_path}")
    print(f"[*] Workspace URI   : {ws_uri}")
    print(f"[*] Preferred Port  : {FIXED_PORT}")

    # Check if Language Server is already running
    csrf_token, active_port = auto_connect.find_vscode_language_server_info()

    if not csrf_token or not active_port:
        print("\n[*] Starting Antigravity Engine in 100% HIDDEN background mode (Zero GUI)...")
        
        exe_path = r"d:\Antigravity IDE\Antigravity.exe"
        if not os.path.exists(exe_path):
            exe_path = r"d:\Antigravity IDE\bin\antigravity-ide.cmd"

        ps_cmd = f"""
        $env:JETSKI_FIXED_SERVER_PORT = "{FIXED_PORT}"
        $env:JETSKI_FIXED_LSP_PORT = "{FIXED_PORT + 1}"
        Start-Process -FilePath "{exe_path}" -ArgumentList '"{ws_path}"' -WindowStyle Hidden
        """
        enc = base64.b64encode(ps_cmd.encode("utf-16le")).decode("ascii")
        subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", enc], capture_output=True)

        print("[*] Waiting for Antigravity engine to boot in background and authenticate...")
        for attempt in range(20):
            time.sleep(1.0)
            csrf_token, active_port = auto_connect.find_vscode_language_server_info()
            if csrf_token and active_port:
                print(f"[+] Engine Live on Port {active_port} with Valid OAuth Session!")
                break
            print(f"    ... waiting for background engine ({attempt + 1}/20)")

    if not csrf_token or not active_port:
        print("[-] Engine did not respond in time. Please check your Antigravity installation.")
        return

    # Run auto_connect handshake
    print("\n[*] Performing 9-Step Full Handshake & Registration...")
    base_url = f"https://127.0.0.1:{active_port}"

    auto_connect.make_grpc_call(base_url, "ListPages", csrf_token, {})
    auto_connect.make_grpc_call(base_url, "GetAgentScripts", csrf_token, {})
    auto_connect.make_grpc_call(base_url, "GetMendelFlags", csrf_token, {})
    auto_connect.make_grpc_call(base_url, "GetAgentScripts", csrf_token, {"workspaceUris": [ws_uri]})
    auto_connect.make_grpc_call(base_url, "GetRepoInfos", csrf_token, {"repoUris": [ws_uri]})
    auto_connect.make_grpc_call(base_url, "GetAllWorkflows", csrf_token, {"workspaceUris": [ws_uri], "activeProfile": ""})
    auto_connect.make_grpc_call(base_url, "ListMcpPrompts", csrf_token, {})

    cascade_config = {
        "plannerConfig": {
            "conversational": {"plannerMode": "CONVERSATIONAL_PLANNER_MODE_DEFAULT", "agenticMode": False},
            "toolConfig": {"runCommand": {"autoCommandConfig": {}}, "notifyUser": {}},
            "requestedModel": {"model": "MODEL_PLACEHOLDER_M298"},
            "knowledgeConfig": {"enabled": False}
        },
        "conversationHistoryConfig": {"enabled": False}
    }
    auto_connect.make_grpc_call(base_url, "GetSlashCommands", csrf_token, {"cascadeConfig": cascade_config, "workspaceUris": [ws_uri], "activeProfile": ""})
    auto_connect.make_grpc_call(base_url, "RefreshMcpServers", csrf_token, {})

    # Start live cascade session
    conv_id = str(uuid.uuid4())
    start_cascade_payload = {
        "source": "CORTEX_TRAJECTORY_SOURCE_CASCADE_CLIENT",
        "cascadeId": conv_id,
        "requestedModel": "MODEL_PLACEHOLDER_M298",
        "workspaceUris": [ws_uri],
        "activeProfile": ""
    }
    auto_connect.make_grpc_call(base_url, "StartCascade", csrf_token, start_cascade_payload)

    # Save session
    auto_connect.save_session(active_port, csrf_token, conv_id, ws_uri)

    print("\n" + "=" * 65)
    print(" [+] AUTHENTICATED BACKGROUND SERVICE IS 100% READY!")
    print(f" [+] Active Port     : {active_port}")
    print(f" [+] CSRF Token      : {csrf_token}")
    print(f" [+] Conversation ID : {conv_id}")
    print(f" [+] Session File    : {SESSION_FILE}")
    print("=" * 65)
    print("\nAap ab bina kisi pareshani ke direct 'uv run langgraph_1/agent.py'")
    print("ya 'python tools/working/test.py' chala sakte hain!\n")


if __name__ == "__main__":
    start_service()

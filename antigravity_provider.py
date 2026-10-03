"""
Antigravity LLM Provider & Adapter Implementation
Author: Nasir Bhutta
Description: Headless client for local Antigravity Language Server.
             Supports Pure LLM Mode, Agentic Mode, multi-turn conversations,
             and StructuredLLM extraction conforming to Pydantic schemas.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import struct
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, TypeVar
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

current_dir = os.path.abspath(os.path.dirname(__file__))
if os.path.exists(os.path.join(current_dir, "src")):
    PROJECT_ROOT = current_dir
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, ".."))

SESSION_FILE = os.path.join(PROJECT_ROOT, ".antigravity_session.json")
SERVICE = "/exa.language_server_pb.LanguageServerService"


def extract_json_text(text: str) -> str:
    """Extracts valid JSON string from potential markdown wrapper or conversational text."""
    if not text or not isinstance(text, str):
        return ""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    candidate = match.group(1).strip() if match else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        return candidate[start : end + 1]
    return candidate


def compact_verification_prompt(prompt: str, max_chars: int = 65000) -> str:
    """Compacts excessively large prompts containing multiple raw HTML/page dumps."""
    if len(prompt) <= max_chars:
        return prompt

    def shrink_raw(m):
        content = m.group(1)
        if len(content) > 3500:
            return f'"raw_content": "{content[:3500]}... [excerpt truncated for focused verification]"'
        return m.group(0)

    compacted = re.sub(r'"raw_content":\s*"([^"\\]*(?:\\.[^"\\]*)*)"', shrink_raw, prompt)
    if len(compacted) > max_chars:
        compacted = re.sub(r'\n{3,}', '\n\n', compacted)
    return compacted


class AntigravityLLMProvider:
    """Client for communicating with Antigravity Language Server."""

    def __init__(
        self,
        port: int | None = None,
        csrf_token: str | None = None,
        workspace_uri: str | None = None,
        system_prompt: str | None = None,
        agentic_mode: bool = False,
        new_chat: bool = False,
        session_file: str | None = None,
    ):
        self.session_file = session_file or SESSION_FILE
        self.system_prompt = system_prompt
        self.agentic_mode = agentic_mode
        self._turn_count = 0
        self.last_step_index = -1
        self._lock = threading.Lock()

        # 1. Resolve connection parameters
        loaded_sess = self._load_session_file()
        self.port = port or loaded_sess.get("port")
        self.csrf_token = csrf_token or loaded_sess.get("csrf_token") or os.environ.get("LANGUAGE_SERVER_CSRF")
        self.workspace_uri = workspace_uri or loaded_sess.get("workspace_uri") or Path(PROJECT_ROOT).as_uri()

        if not self.port or not self.csrf_token:
            self._auto_detect_connection()

        if not self.csrf_token:
            raise ValueError("CSRF token required! Could not auto-detect Antigravity Language Server.")

        self.base_url = f"https://127.0.0.1:{self.port}"

        # 2. Conversation Session Management
        if new_chat or not loaded_sess.get("conversation_id"):
            self.conversation_id = str(uuid.uuid4())
            self._initialized = False
        else:
            self.conversation_id = loaded_sess.get("conversation_id")
            self._initialized = True

    def _load_session_file(self) -> dict:
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _auto_detect_connection(self):
        try:
            from tools import auto_connect
            token, port = auto_connect.find_vscode_language_server_info()
            if token and port:
                self.csrf_token = token
                self.port = port
                return
        except Exception:
            pass

    def initialize_chat(self):
        """Registers a fresh Cascade session on the Language Server."""
        payload = {
            "source": "CORTEX_TRAJECTORY_SOURCE_CASCADE_CLIENT",
            "cascadeId": self.conversation_id,
            "requestedModel": "MODEL_PLACEHOLDER_M298",
            "workspaceUris": [self.workspace_uri],
            "activeProfile": "",
        }
        self._post_json(f"{SERVICE}/StartCascade", payload)
        self._initialized = True

    def chat(self, message: str, timeout: float = 120.0) -> str:
        """Sends a message and returns the model response."""
        if not self._initialized:
            self.initialize_chat()

        subscriber_id = str(uuid.uuid4())
        done_event = threading.Event()
        prev_idx = self.last_step_index
        latest_by_step: dict[int, str] = {}
        completed_steps: set[int] = set()

        # Build message with system prompt on first turn
        if self._turn_count == 0 and self.system_prompt:
            send_text = f"[System Instructions: {self.system_prompt}]\n\n{message}"
        else:
            send_text = message
        self._turn_count += 1

        # Background stream listener
        def listen_stream():
            stream_payload = {
                "conversationId": self.conversation_id,
                "subscriberId": subscriber_id,
                "initialStepsPageBounds": {"startIndex": -50},
                "initialGeneratorMetadatasPageBounds": {"startIndex": -1},
                "initialExecutorMetadatasPageBounds": {"endIndexExclusive": 0},
                "enableLatencyTelemetry": True,
            }
            body = (
                bytes([0])
                + struct.pack(">I", len(json.dumps(stream_payload).encode("utf-8")))
                + json.dumps(stream_payload).encode("utf-8")
            )
            req = Request(
                f"{self.base_url}{SERVICE}/StreamAgentStateUpdates",
                data=body,
                method="POST",
                headers={
                    "Accept": "application/connect+json",
                    "Content-Type": "application/connect+json",
                    "Content-Length": str(len(body)),
                    "Origin": "vscode-file://vscode-app",
                    "connect-protocol-version": "1",
                    "x-codeium-csrf-token": self.csrf_token,
                },
            )
            ctx = ssl._create_unverified_context()
            try:
                with urlopen(req, context=ctx) as resp:
                    buf = b""
                    while not done_event.is_set():
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while len(buf) >= 5:
                            fl = struct.unpack(">I", buf[1:5])[0]
                            if len(buf) < 5 + fl:
                                break
                            frame = buf[5 : 5 + fl]
                            buf = buf[5 + fl :]
                            try:
                                update = json.loads(frame.decode("utf-8"))
                                steps = (
                                    update.get("update", {})
                                    .get("mainTrajectoryUpdate", {})
                                    .get("stepsUpdate", {})
                                    .get("steps", [])
                                )
                                for s in steps:
                                    s_idx = (
                                        s.get("metadata", {})
                                        .get("sourceTrajectoryStepInfo", {})
                                        .get("stepIndex")
                                    )
                                    if s_idx is None:
                                        s_idx = s.get("stepIndex")
                                    pr = s.get("plannerResponse")
                                    if pr:
                                        txt = pr.get("modifiedResponse") or pr.get("response")
                                        idx_key = s_idx if s_idx is not None else 1
                                        with self._lock:
                                            if txt:
                                                latest_by_step[idx_key] = txt
                                            if (
                                                pr.get("stopReason")
                                                or s.get("status") == "CORTEX_STEP_STATUS_DONE"
                                            ):
                                                completed_steps.add(idx_key)
                                                done_event.set()
                            except Exception:
                                pass
            except Exception:
                pass

        stream_thread = threading.Thread(target=listen_stream, daemon=True)
        stream_thread.start()
        time.sleep(0.2)

        # Dispatch message
        planner_conf = {
            "conversational": {
                "plannerMode": "CONVERSATIONAL_PLANNER_MODE_DEFAULT",
                "agenticMode": self.agentic_mode,
            },
            "requestedModel": {"model": "MODEL_PLACEHOLDER_M298"},
            "knowledgeConfig": {"enabled": self.agentic_mode},
        }
        if self.agentic_mode:
            planner_conf["toolConfig"] = {
                "runCommand": {
                    "autoCommandConfig": {
                        "autoExecutionPolicy": "CASCADE_COMMANDS_AUTO_EXECUTION_EAGER"
                    }
                },
                "notifyUser": {"artifactReviewMode": "ARTIFACT_REVIEW_MODE_ALWAYS"},
                "permissionConfig": {"defaultGrants": {"ask": ["read_url(*)"]}},
            }

        send_payload = {
            "cascadeId": self.conversation_id,
            "items": [{"text": send_text}],
            "cascadeConfig": {
                "plannerConfig": planner_conf,
                "conversationHistoryConfig": {"enabled": True},
            },
            "deliveryStrategy": "MESSAGE_DELIVERY_STRATEGY_WHEN_IDLE",
            "activeProfile": "",
        }
        self._post_json(f"{SERVICE}/SendUserCascadeMessage", send_payload)

        # Signal page update
        page_update_payload = {
            "conversationId": self.conversation_id,
            "subscriberId": subscriber_id,
            "stepPageBounds": {},
        }
        self._post_json(f"{SERVICE}/RequestAgentStatePageUpdate", page_update_payload)

        # Wait for stream event or generation progress
        start_time = time.time()
        last_text_len = 0
        poll_step = 0
        while time.time() - start_time < timeout:
            if done_event.wait(timeout=1.0):
                break
            with self._lock:
                cand_steps = [idx for idx in completed_steps if idx > prev_idx or prev_idx == -1]
                if cand_steps:
                    break
                active_steps = [idx for idx in latest_by_step if idx > prev_idx or prev_idx == -1]
                if active_steps:
                    curr_len = len(latest_by_step[max(active_steps)])
                    if curr_len > last_text_len:
                        last_text_len = curr_len
                        # Reset start_time to keep waiting while model is actively generating tokens
                        start_time = time.time()

            # Active fallback check via GetTurnDiff every 2 seconds
            poll_step += 1
            if poll_step % 2 == 0:
                for diff_idx in (1, 0, 2):
                    try:
                        diff = self._post_json(
                            f"{SERVICE}/GetTurnDiff",
                            {"conversationId": self.conversation_id, "stepIndex": diff_idx},
                        )
                        if diff:
                            for s in diff.get("steps", []):
                                pr = s.get("plannerResponse")
                                if pr:
                                    txt = pr.get("modifiedResponse") or pr.get("response")
                                    if txt and (pr.get("stopReason") or s.get("status") == "CORTEX_STEP_STATUS_DONE"):
                                        with self._lock:
                                            latest_by_step[diff_idx] = txt
                                            completed_steps.add(diff_idx)
                                            done_event.set()
                                        break
                    except Exception:
                        pass
                if done_event.is_set():
                    break

        with self._lock:
            cand_steps = [idx for idx in completed_steps if idx > prev_idx or prev_idx == -1]
            if cand_steps:
                best_idx = max(cand_steps)
                self.last_step_index = best_idx
                return latest_by_step.get(best_idx, "")

            active_steps = [idx for idx in latest_by_step if idx > prev_idx or prev_idx == -1]
            if active_steps:
                best_idx = max(active_steps)
                self.last_step_index = best_idx
                return latest_by_step.get(best_idx, "")

        # Fallback to GetTurnDiff polling
        for diff_idx in (1, 0, 2, 3):
            try:
                diff = self._post_json(
                    f"{SERVICE}/GetTurnDiff",
                    {"conversationId": self.conversation_id, "stepIndex": diff_idx},
                )
                if diff:
                    for s in diff.get("steps", []):
                        txt = s.get("plannerResponse", {}).get("modifiedResponse") or s.get("plannerResponse", {}).get("response")
                        if txt:
                            self.last_step_index = diff_idx
                            return txt
            except Exception:
                pass

        return "[-] No response received from local server."

    def _post_json(self, path: str, payload: dict) -> Any:
        body = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{self.base_url}{path}",
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
                "Origin": "vscode-file://vscode-app",
                "connect-protocol-version": "1",
                "x-codeium-csrf-token": self.csrf_token,
            },
        )
        ctx = ssl._create_unverified_context()
        try:
            with urlopen(req, context=ctx, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {err}") from e


class AntigravityStructuredLLM:
    """Structured LLM adapter for France Admission Agent.

    Conforms to france_admission_agent.llm.StructuredLLM protocol.
    Directs extraction and review prompts to Antigravity Language Server.
    """

    def __init__(self, provider: AntigravityLLMProvider | None = None):
        self.provider = provider or AntigravityLLMProvider(agentic_mode=False)

    def generate_structured(
        self,
        *,
        system: str,
        prompt: str,
        response_model: type[T],
    ) -> T:
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        clean_prompt = compact_verification_prompt(prompt)
        instruction = (
            f"{clean_prompt}\n\n"
            f"You MUST output valid JSON strictly conforming to this JSON Schema:\n"
            f"```json\n{schema}\n```\n"
            f"Respond with the raw JSON object only. Do not include markdown preamble, commentary, or text outside the JSON."
        )

        last_error = None
        raw = ""
        for attempt in range(2):
            adapter = AntigravityLLMProvider(
                port=self.provider.port,
                csrf_token=self.provider.csrf_token,
                workspace_uri=self.provider.workspace_uri,
                system_prompt=system,
                agentic_mode=False,
                new_chat=True,
            )

            raw = adapter.chat(instruction, timeout=90.0)
            json_str = extract_json_text(raw)

            if json_str and json_str != "[-] No response received from local server.":
                try:
                    data = json.loads(json_str)
                    return response_model.model_validate(data)
                except Exception as e:
                    last_error = e
                    try:
                        return response_model.model_validate_json(json_str)
                    except Exception as e2:
                        last_error = e2

        # Safe fallback if verification timed out for an individual university lead
        if response_model.__name__ == "ProgrammeVerification":
            print("[!] Warning: Verification timed out for a lead. Returning safe unverified record to continue workflow.")
            u_match = re.search(r'"university":\s*"([^"]+)"', prompt)
            p_match = re.search(r'"programme":\s*"([^"]+)"', prompt)
            c_match = re.search(r'"city":\s*"([^"]+)"', prompt)
            u_name = u_match.group(1) if u_match else "Unknown University"
            p_name = p_match.group(1) if p_match else "Master Informatique"
            c_name = c_match.group(1) if c_match else "Unknown"
            try:
                return response_model.model_validate({
                    "university": u_name,
                    "programme": p_name,
                    "city": c_name,
                    "unresolved_questions": ["Official university requirements could not be verified automatically (LLM timed out)."]
                })
            except Exception:
                pass

        if last_error:
            raise RuntimeError(
                f"Failed to parse structured JSON for {response_model.__name__}: {last_error}\nRaw response:\n{raw[:500]}"
            )
        raise RuntimeError(
            f"Antigravity Language Server timed out or returned no response for {response_model.__name__}."
        )

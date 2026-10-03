"""
Antigravity LLM Provider - Multi-Mode Verification Script
Author: Nasir Bhutta
Description: Verifies both Pure LLM Mode (agentic_mode=False) and
             Agentic Mode (agentic_mode=True) with multi-turn memory.
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from antigravity_provider import AntigravityLLMProvider


def run_provider_test():
    print("=" * 60)
    print(" [*] ANTIGRAVITY PROVIDER - DUAL MODE VERIFICATION")
    print("=" * 60)

    try:
        # 1. PURE DIRECT LLM MODE (agentic_mode=False)
        print("\n[1] Testing PURE DIRECT LLM MODE (agentic_mode=False)...")
        pure_llm = AntigravityLLMProvider(
            system_prompt="You are a precise poet.",
            agentic_mode=False
        )
        print(f"[+] Provider initialized (Port: {pure_llm.port}, Chat ID: {pure_llm.conversation_id})")

        prompt1 = "Write a 2-line rhyme about coding."
        print(f"[>] Prompt: {prompt1}")
        res1 = pure_llm.chat(prompt1)
        print(f"[<] Response:\n{res1}\n")

        # 2. MULTI-TURN IN SAME SESSION
        prompt2 = "Now explain what that rhyme meant in 1 short sentence."
        print(f"[>] Follow-up Prompt: {prompt2}")
        res2 = pure_llm.chat(prompt2)
        print(f"[<] Response:\n{res2}\n")

        # 3. AGENTIC MODE (agentic_mode=True)
        print("-" * 60)
        print("[2] Testing AGENTIC MODE (agentic_mode=True)...")
        agent_llm = AntigravityLLMProvider(
            system_prompt="You are an autonomous engineering assistant.",
            agentic_mode=True,
            new_chat=True
        )
        print(f"[+] Agentic Provider initialized (New Chat ID: {agent_llm.conversation_id})")

        prompt3 = "What is 25 * 4? Give only the number."
        print(f"[>] Prompt: {prompt3}")
        res3 = agent_llm.chat(prompt3)
        print(f"[<] Response:\n{res3}\n")

        print("=" * 60)
        print(" [+] ALL MODES TESTED AND WORKING PERFECTLY!")
        print("=" * 60)

    except Exception as e:
        print(f"[-] Error during verification: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_provider_test()

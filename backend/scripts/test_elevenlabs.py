"""
Quick test: verify ElevenLabs TTS is working with your API key.

Usage:
    cd backend
    python scripts/test_elevenlabs.py

Requires ELEVENLABS_API_KEY in .env (or environment variable).
Optionally set ELEVENLABS_VOICE_ID (defaults to "Rachel").
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # Rachel


async def test_get_voices():
    """Verify the API key works by listing available voices."""
    print("=" * 60)
    print("TEST 1 — List voices (API key validation)")
    print("=" * 60)

    if not API_KEY:
        print("❌ ELEVENLABS_API_KEY is empty! Set it in backend/.env")
        return False

    print(f"   Key (first 8 chars): {API_KEY[:8]}...")

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": API_KEY}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                voices = resp.json().get("voices", [])
                print(f"   ✅ Status: {resp.status_code}")
                print(f"   Available voices: {len(voices)}")
                for v in voices[:5]:
                    print(f"      - {v['name']} ({v['voice_id'][:12]}...)")
                if len(voices) > 5:
                    print(f"      ... and {len(voices) - 5} more")
                return True
            elif resp.status_code == 401:
                print(f"   ❌ 401 Unauthorized — API key is invalid")
                return False
            else:
                print(f"   ❌ Status: {resp.status_code}")
                print(f"   Response: {resp.text[:300]}")
                return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_synthesize():
    """Generate a short TTS audio clip and save it locally."""
    print()
    print("=" * 60)
    print("TEST 2 — Text-to-Speech synthesis")
    print("=" * 60)

    if not API_KEY:
        print("❌ ELEVENLABS_API_KEY is empty!")
        return False

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": "Hello! This is a test of the ElevenLabs text to speech integration. If you can hear this, everything is working correctly.",
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code == 200:
                audio_bytes = resp.content
                size_kb = len(audio_bytes) / 1024

                print(f"   ✅ Status: {resp.status_code}")
                print(f"   Audio size: {size_kb:.1f} KB")
                print(f"   Content-Type: {resp.headers.get('content-type', 'unknown')}")

                # Save to a temp file so user can verify
                out_path = os.path.join(os.path.dirname(__file__), "test_output.mp3")
                with open(out_path, "wb") as f:
                    f.write(audio_bytes)
                print(f"   Saved to: {out_path}")
                print(f"   ▶ Open this file to verify the audio sounds correct")
                return True
            elif resp.status_code == 401:
                print(f"   ❌ 401 Unauthorized — API key is invalid")
                return False
            elif resp.status_code == 422:
                print(f"   ❌ 422 — Bad request (voice ID may be wrong)")
                print(f"   Voice ID used: {VOICE_ID}")
                print(f"   Response: {resp.text[:300]}")
                return False
            else:
                print(f"   ❌ Status: {resp.status_code}")
                print(f"   Response: {resp.text[:300]}")
                return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_quota():
    """Check remaining character quota."""
    print()
    print("=" * 60)
    print("TEST 3 — Subscription / quota check")
    print("=" * 60)

    if not API_KEY:
        print("❌ ELEVENLABS_API_KEY is empty!")
        return False

    url = "https://api.elevenlabs.io/v1/user/subscription"
    headers = {"xi-api-key": API_KEY}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                used = data.get("character_count", 0)
                limit = data.get("character_limit", 0)
                remaining = limit - used
                tier = data.get("tier", "unknown")

                print(f"   ✅ Plan: {tier}")
                print(f"   Characters used: {used:,} / {limit:,}")
                print(f"   Remaining: {remaining:,}")

                if remaining < 100:
                    print(f"   ⚠️  Very low quota! TTS calls will fail.")
                return True
            else:
                print(f"   ❌ Status: {resp.status_code}")
                return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def main():
    print()
    print("🔊  ELEVENLABS TTS — Integration Test")
    print()

    voices_ok = await test_get_voices()
    synth_ok = await test_synthesize()
    quota_ok = await test_quota()

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"   API Key (voices):  {'✅ PASS' if voices_ok else '❌ FAIL'}")
    print(f"   TTS Synthesis:     {'✅ PASS' if synth_ok else '❌ FAIL'}")
    print(f"   Quota Check:       {'✅ PASS' if quota_ok else '❌ FAIL'}")
    print()

    if voices_ok and synth_ok:
        print("🎉 ElevenLabs is fully working!")
        if synth_ok:
            print("   ▶ Play scripts/test_output.mp3 to hear the result.")
    elif not API_KEY:
        print("⚠️  Set ELEVENLABS_API_KEY in backend/.env and re-run.")
    else:
        print("⚠️  Check the errors above.")
    print()


if __name__ == "__main__":
    asyncio.run(main())

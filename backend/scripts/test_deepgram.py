"""
Quick test: verify Deepgram STT is working with your API key.

Usage:
    cd backend
    python scripts/test_deepgram.py

Requires DEEPGRAM_API_KEY in .env (or environment variable).
"""

import asyncio
import io
import math
import os
import struct
import sys
import wave

# Allow running from the backend/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEEPGRAM_API_KEY", "")


def _generate_wav(duration_s: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate a short WAV file with a 440 Hz sine wave (for testing only)."""
    buf = io.BytesIO()
    n_frames = int(sample_rate * duration_s)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(n_frames):
            sample = int(16000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            wf.writeframes(struct.pack("<h", sample))
    return buf.getvalue()


async def test_rest_api():
    """Test Deepgram REST API with generated audio bytes."""
    print("=" * 60)
    print("TEST 1 — Deepgram REST API (upload audio bytes)")
    print("=" * 60)

    if not API_KEY:
        print("❌ DEEPGRAM_API_KEY is empty! Set it in backend/.env")
        return False

    print(f"   Key (first 8 chars): {API_KEY[:8]}...")

    audio_data = _generate_wav()
    print(f"   Generated {len(audio_data)} bytes of test WAV audio")

    url = "https://api.deepgram.com/v1/listen?model=nova-2&punctuate=true&language=en"
    headers = {
        "Authorization": f"Token {API_KEY}",
        "Content-Type": "audio/wav",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, content=audio_data)

            if resp.status_code == 200:
                data = resp.json()
                channel = data.get("results", {}).get("channels", [{}])[0]
                alt = (channel.get("alternatives") or [{}])[0]
                transcript = alt.get("transcript", "")
                confidence = alt.get("confidence", 0)

                print(f"   ✅ Status: {resp.status_code}")
                print(f"   Transcript: \"{transcript[:120]}\"")
                print(f"   Confidence: {confidence:.2%}")
                print(f"   (A sine wave has no speech — empty transcript is expected)")
                return True
            else:
                print(f"   ❌ Status: {resp.status_code}")
                print(f"   Response: {resp.text[:300]}")
                return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


async def test_websocket():
    """Test Deepgram WebSocket (streaming) API with generated audio."""
    print()
    print("=" * 60)
    print("TEST 2 — Deepgram WebSocket streaming API")
    print("=" * 60)

    if not API_KEY:
        print("❌ DEEPGRAM_API_KEY is empty!")
        return False

    try:
        import websockets
    except ImportError:
        print("❌ 'websockets' package not installed. Run: pip install websockets")
        return False

    audio_data = _generate_wav(duration_s=2.0)
    print(f"   Generated {len(audio_data)} bytes of test audio")

    ws_url = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2&punctuate=true&language=en&endpointing=1000"
    )
    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with websockets.connect(ws_url, additional_headers=headers) as ws:
            print("   ✅ WebSocket connected to Deepgram!")

            # Send audio in chunks
            chunk_size = 8000
            for i in range(0, len(audio_data), chunk_size):
                await ws.send(audio_data[i : i + chunk_size])
                await asyncio.sleep(0.05)

            # Signal end of stream
            import json
            await ws.send(json.dumps({"type": "CloseStream"}))

            # Collect results
            result_count = 0
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") == "Results":
                        result_count += 1
                        ch = msg.get("channel", {})
                        alt = (ch.get("alternatives") or [{}])[0]
                        text = alt.get("transcript", "")
                        is_final = msg.get("is_final", False)
                        if text:
                            print(f"   [{'final' if is_final else 'interim'}] \"{text}\"")
            except websockets.exceptions.ConnectionClosed:
                pass

            print(f"   ✅ Received {result_count} result frame(s) from Deepgram")
            print(f"   (Sine wave has no speech — 0 transcripts is expected)")
            return True

    except Exception as e:
        print(f"   ❌ WebSocket error: {e}")
        return False


async def main():
    print()
    print("🎤  DEEPGRAM STT — Integration Test")
    print()

    rest_ok = await test_rest_api()
    ws_ok = await test_websocket()

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"   REST API:      {'✅ PASS' if rest_ok else '❌ FAIL'}")
    print(f"   WebSocket API: {'✅ PASS' if ws_ok else '❌ FAIL'}")
    print()

    if rest_ok and ws_ok:
        print("🎉 Deepgram is fully working!")
    elif not API_KEY:
        print("⚠️  Set DEEPGRAM_API_KEY in backend/.env and re-run.")
    else:
        print("⚠️  Check the errors above.")
    print()


if __name__ == "__main__":
    asyncio.run(main())

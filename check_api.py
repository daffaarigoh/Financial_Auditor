"""
Script untuk mengecek koneksi & ketersediaan semua model LLM.
Jalankan: python check_api.py
"""
import sys
import os
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(".env")

from config.settings import get_llm_client, MODELS, LLM_API_BASE

client = get_llm_client()

print("=" * 60)
print("  FINANCIAL AUDITOR -- API CONNECTION CHECK")
print("=" * 60)
print(f"  Endpoint : {LLM_API_BASE}")
print("=" * 60)

# -- 1. List available models ------------------------------------
print("\n[1] Mengambil daftar model yang tersedia...")
try:
    models_response = client.models.list()
    available_ids = [m.id for m in models_response.data]
    print(f"    [OK] Berhasil -- {len(available_ids)} model ditemukan:")
    for mid in available_ids:
        print(f"         - {mid}")
except Exception as e:
    available_ids = []
    print(f"    [GAGAL] Tidak bisa ambil daftar model: {e}")

print()

# -- 2. Test setiap model yang dikonfigurasi ---------------------
print("[2] Menguji setiap model yang dikonfigurasi...\n")

results = {}
for role, model_name in MODELS.items():
    configured = model_name in available_ids if available_ids else None

    print(f"  [{role.upper()}] Model: {model_name}")

    if available_ids and not configured:
        print(f"    [TIDAK DITEMUKAN] Model tidak ada di server\n")
        results[role] = "NOT_FOUND"
        continue

    # Quick ping test
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Say hello in one word."}],
            max_tokens=10,
            timeout=20
        )
        content = resp.choices[0].message.content
        reply = content.strip() if content else "(empty response — model mungkin butuh prompt lebih panjang)"
        status_tag = "OK" if content else "EMPTY_RESPONSE"
        print(f"    [{status_tag}] Response: '{reply}'")
        results[role] = status_tag
    except Exception as e:
        print(f"    [ERROR] {e}")
        results[role] = f"ERROR: {e}"
    print()

# -- 3. Summary --------------------------------------------------
print("=" * 60)
print("  RINGKASAN")
print("=" * 60)
all_ok = True
for role, status in results.items():
    icon = "[OK]   " if status == "OK" else "[ERROR]"
    model = MODELS[role]
    print(f"  {icon} {role.upper():8s} | {model:25s} | {status}")
    if status != "OK":
        all_ok = False

print()
if all_ok:
    print("  Semua model siap! Jalankan: python server.py")
else:
    print("  Beberapa model bermasalah.")
    if available_ids:
        print(f"\n  Model yang tersedia di server Anda:")
        for mid in available_ids:
            print(f"    - {mid}")
        print("\n  Sesuaikan nama model di config/settings.py atau pull model yang dibutuhkan.")
print("=" * 60)

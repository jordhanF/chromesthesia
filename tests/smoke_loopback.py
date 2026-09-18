"""Prova o caminho de audio do motor: WASAPI loopback -> float32 -> numpy."""
import numpy as np, pyaudiowpatch as pyaudio, time, wave, os

p = pyaudio.PyAudio()
try:
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
except OSError:
    raise SystemExit("WASAPI indisponivel")

spk = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
print(f"saida padrao: {spk['name']}")

loop = None
for d in p.get_loopback_device_info_generator():
    if spk["name"] in d["name"]:
        loop = d; break
if loop is None:
    raise SystemExit("nenhum dispositivo de loopback casou com a saida padrao")
print(f"loopback    : {loop['name']}  ({int(loop['defaultSampleRate'])} Hz, {loop['maxInputChannels']} ch)")

SR = int(loop["defaultSampleRate"]); CH = loop["maxInputChannels"]; SECS = 3
chunks = []
st = p.open(format=pyaudio.paFloat32, channels=CH, rate=SR,
            input=True, input_device_index=loop["index"], frames_per_buffer=1024)
t0 = time.time()
while time.time() - t0 < SECS:
    chunks.append(st.read(1024, exception_on_overflow=False))
st.close(); p.terminate()

a = np.frombuffer(b"".join(chunks), dtype=np.float32).reshape(-1, CH)
rms = float(np.sqrt((a ** 2).mean()))
peak = float(np.abs(a).max())
print(f"capturado   : {a.shape[0]} frames ({a.shape[0]/SR:.1f}s)  RMS={rms:.5f}  pico={peak:.4f}")

if peak < 1e-4:
    print("\n>>> PLUMBING OK, mas SILENCIO. Toque alguma coisa e rode de novo para capturar referencia.")
else:
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ref_capturada.wav")
    pcm16 = (np.clip(a, -1, 1) * 32767).astype(np.int16)
    with wave.open(dst, "wb") as w:
        w.setnchannels(CH); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm16.tobytes())
    print(f"\n>>> SINAL CAPTURADO -> {dst} ({os.path.getsize(dst)/1024:.0f} KB)")

"""Verifica se miniaudio entrega no formato que indexer/reference.py precisa:
float32, 44100 Hz, estereo, como array numpy."""
import wave, struct, math, os, sys
import numpy as np
import miniaudio

SCR = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(SCR, "_probe.wav")

# gera um wav de teste em 48kHz mono, para forcar conversao para 44100 estereo
sr_in, dur = 48000, 2.0
with wave.open(src, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr_in)
    w.writeframes(b"".join(struct.pack("<h", int(20000 * math.sin(2*math.pi*440*t/sr_in)))
                           for t in range(int(sr_in*dur))))
print(f"entrada: 48000 Hz, mono, {dur}s")

dec = miniaudio.decode_file(src, output_format=miniaudio.SampleFormat.FLOAT32,
                            nchannels=2, sample_rate=44100)
print(f"saida  : {dec.sample_rate} Hz, {dec.nchannels} canais, "
      f"{dec.num_frames} frames ({dec.num_frames/dec.sample_rate:.2f}s)")

a = np.asarray(dec.samples, dtype=np.float32)
print(f"numpy  : shape={a.shape} dtype={a.dtype} min={a.min():.3f} max={a.max():.3f}")

inter = a.reshape(-1, 2)
print(f"intercalado L/R: {inter.shape}  (e exatamente o layout que projectm_pcm_add_float espera)")

ok = (dec.sample_rate == 44100 and dec.nchannels == 2
      and a.dtype == np.float32 and abs(a).max() <= 1.001)
print("\n>>>", "COMPATIVEL" if ok else "INCOMPATIVEL")
os.remove(src)

"""Prova do pipeline de preview da Fase 1: headless + warmup AGC + glReadPixels + webp animado."""
import ctypes, os, sys, math, time, glob
import numpy as np
from PIL import Image

APP = r"C:\Users\Jordh\projectM\app\projectMSDL-2.0.0-win64"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "previews")
os.makedirs(OUT, exist_ok=True)
os.add_dll_directory(APP)

pm = ctypes.CDLL(os.path.join(APP, "projectM-4.dll"))
pm.projectm_create.restype = ctypes.c_void_p
for fn, at in [("projectm_destroy", [ctypes.c_void_p]),
               ("projectm_set_window_size", [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]),
               ("projectm_load_preset_file", [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_bool]),
               ("projectm_opengl_render_frame", [ctypes.c_void_p]),
               ("projectm_pcm_add_float", [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_uint, ctypes.c_int]),
               ("projectm_set_texture_search_paths", [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_size_t])]:
    getattr(pm, fn).argtypes = at

import glfw
from OpenGL.GL import glReadPixels, GL_RGB, GL_UNSIGNED_BYTE
glfw.init()
glfw.window_hint(glfw.VISIBLE, glfw.FALSE)          # <<< headless
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
W, H = 640, 360
win = glfw.create_window(W, H, "headless", None, None)
glfw.make_context_current(win)
glfw.swap_interval(0)                                # <<< sem vsync: renderiza o mais rapido possivel
glew = ctypes.CDLL(os.path.join(APP, "glew32.dll"))
ctypes.c_ubyte.in_dll(glew, "glewExperimental").value = 1
glew.glewInit()

FPS, N = 60, 576
def ref_signal(frame_idx):
    """Sinal de referencia sintetico determinístico: kick 120bpm + pad + hihat."""
    buf = (ctypes.c_float * (N * 2))()
    t0 = frame_idx * N
    beat = 60.0 / 120.0 * 44100
    for i in range(N):
        t = t0 + i
        env = math.exp(-((t % beat) / (beat * 0.12)))
        s = (0.8 * env * math.sin(2 * math.pi * 0.0012 * t)          # kick grave
             + 0.25 * math.sin(2 * math.pi * 0.030 * t)              # pad medio
             + 0.15 * env * math.sin(2 * math.pi * 0.150 * t))       # hihat agudo
        buf[i * 2] = s; buf[i * 2 + 1] = s
    return buf

def make_preview(preset_path, warmup_s=5.0, capture_frames=40, stride=3):
    h = pm.projectm_create()
    pm.projectm_set_window_size(h, W, H)
    tex = os.path.join(APP, "textures").encode()
    pm.projectm_set_texture_search_paths(h, (ctypes.c_char_p * 1)(tex), 1)
    pm.projectm_load_preset_file(h, preset_path.encode("utf-8"), True)
    f = 0
    for _ in range(int(warmup_s * FPS)):                 # <<< deixa o AGC assentar
        pm.projectm_pcm_add_float(h, ref_signal(f), N, 2)
        pm.projectm_opengl_render_frame(h); glfw.swap_buffers(win); f += 1
    frames = []
    for k in range(capture_frames * stride):
        pm.projectm_pcm_add_float(h, ref_signal(f), N, 2)
        pm.projectm_opengl_render_frame(h); glfw.swap_buffers(win); f += 1
        if k % stride == 0:
            raw = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
            a = np.frombuffer(raw, np.uint8).reshape(H, W, 3)[::-1]   # GL e bottom-up
            frames.append(Image.fromarray(a).resize((320, 180), Image.LANCZOS))
    pm.projectm_destroy(h)
    return frames

cands = []
for fam in ["Hypnotic", "Supernova", "Geometric"]:
    g = glob.glob(os.path.join(APP, "presets", "**", fam, "**", "*.milk"), recursive=True)
    if g: cands.append((fam, g[0]))

print(f"{'familia':<12} {'seg':>6} {'kb':>7}  arquivo")
total = 0.0
for fam, path in cands:
    t0 = time.time()
    frames = make_preview(path)
    dst = os.path.join(OUT, f"{fam}.webp")
    frames[0].save(dst, save_all=True, append_images=frames[1:], duration=50, loop=0,
                   format="WEBP", quality=72, method=4)
    dt = time.time() - t0; total += dt
    static = np.array(frames[0]).std()
    moved = np.abs(np.array(frames[0], float) - np.array(frames[-1], float)).mean()
    print(f"{fam:<12} {dt:>6.1f} {os.path.getsize(dst)/1024:>7.0f}  {os.path.basename(path)[:44]}")
    print(f"{'':12} contraste={static:.1f}  movimento entre 1o e ultimo frame={moved:.1f}")

glfw.terminate()
print(f"\nmedia por preset: {total/len(cands):.1f}s -> 9795 presets = {total/len(cands)*9795/3600:.1f}h")
print("previews em:", OUT)

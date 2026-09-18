"""Teste descartavel: prova que ctypes + GL + projectM funcionam juntos.
NAO e codigo do projeto - vive no scratchpad e morre aqui."""
import ctypes, os, sys, math, time

APP = r"C:\Users\Jordh\projectM\app\projectMSDL-2.0.0-win64"
DLL = os.path.join(APP, "projectM-4.dll")

print("1. add_dll_directory ...", end=" ")
os.add_dll_directory(APP)
print("ok")

print("2. carregar DLL ...", end=" ")
pm = ctypes.CDLL(DLL)
print("ok")

print("3. resolver simbolos ...", end=" ")
pm.projectm_create.restype = ctypes.c_void_p
pm.projectm_destroy.argtypes = [ctypes.c_void_p]
pm.projectm_set_window_size.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t]
pm.projectm_load_preset_file.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_bool]
pm.projectm_opengl_render_frame.argtypes = [ctypes.c_void_p]
pm.projectm_pcm_add_float.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float),
                                      ctypes.c_uint, ctypes.c_int]
pm.projectm_set_texture_search_paths.argtypes = [ctypes.c_void_p,
                                                 ctypes.POINTER(ctypes.c_char_p), ctypes.c_size_t]
pm.projectm_write_debug_image_on_next_frame.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
pm.projectm_get_version_string.restype = ctypes.c_char_p
print("ok ->", pm.projectm_get_version_string().decode())

print("4. contexto OpenGL via glfw ...", end=" ")
import glfw
if not glfw.init():
    sys.exit("glfw.init() falhou")
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
W, H = 960, 540
win = glfw.create_window(W, H, "smoke test - projectM via ctypes", None, None)
if not win:
    glfw.terminate(); sys.exit("create_window falhou")
glfw.make_context_current(win)
glfw.swap_interval(1)
print("ok")

print("4b. glewInit() (o que faltava) ...", end=" ")
glew = ctypes.CDLL(os.path.join(APP, "glew32.dll"))
try:
    ctypes.c_ubyte.in_dll(glew, "glewExperimental").value = 1
    print("[experimental=1]", end=" ")
except ValueError:
    print("[sem glewExperimental]", end=" ")
glew.glewInit.restype = ctypes.c_uint
err = glew.glewInit()
print("ok" if err == 0 else f"ERRO glew={err}")

print("5. projectm_create() (RISCO PRINCIPAL) ...", end=" ")
h = pm.projectm_create()
if not h:
    sys.exit("projectm_create devolveu NULL")
print("ok -> handle", hex(h))

pm.projectm_set_window_size(h, W, H)

tex = os.path.join(APP, "textures").encode()
arr = (ctypes.c_char_p * 1)(tex)
pm.projectm_set_texture_search_paths(h, arr, 1)

print("6. carregar um preset ...", end=" ")
import glob
cands = glob.glob(os.path.join(APP, "presets", "**", "Hypnotic", "**", "*.milk"), recursive=True)
if not cands:
    cands = glob.glob(os.path.join(APP, "presets", "**", "*.milk"), recursive=True)
preset = cands[0]
pm.projectm_load_preset_file(h, preset.encode("utf-8"), False)
print("ok ->", os.path.basename(preset)[:60])

print("7. render 180 frames com sinal sintetico ...", end=" ")
N = 576
buf = (ctypes.c_float * (N * 2))()
t0 = time.time(); frames = 0; phase = 0.0
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_frame.tga")
while frames < 180 and not glfw.window_should_close(win):
    for i in range(N):
        s = (0.6 * math.sin(phase * 0.08) +
             0.3 * math.sin(phase * 0.55) +
             0.2 * math.sin(phase * 2.10))
        buf[i * 2] = s; buf[i * 2 + 1] = s
        phase += 1.0
    pm.projectm_pcm_add_float(h, buf, N, 2)
    if frames == 150:
        pm.projectm_write_debug_image_on_next_frame(h, out.encode())
    pm.projectm_opengl_render_frame(h)
    glfw.swap_buffers(win); glfw.poll_events()
    frames += 1
dt = time.time() - t0
print(f"ok -> {frames} frames em {dt:.1f}s ({frames/dt:.0f} fps)")

print("8. dump de frame gerado?", os.path.exists(out),
      f"({os.path.getsize(out)} bytes)" if os.path.exists(out) else "")

pm.projectm_destroy(h)
glfw.terminate()
print("\n>>> TUBO COMPLETO FUNCIONANDO <<<")

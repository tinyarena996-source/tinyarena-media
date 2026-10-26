"""o01 v2 - 3D pendulum wave (Blender / Cycles). A/B partner of 12-pendulum-wave.

v2 (owner 2026-10-26: "material looks odd, too bright, the view must be the same as 2D"):
the camera now looks at the scene exactly like the 2D video. 1 Blender unit = 1000 video
pixels, everything sits where 12 draws it (shared pivot at (540, 486), pendulum lengths
232..1010 px, bob radius 15 px, release slots, dotted target line), seen through an
orthographic camera, so every frame lines up pixel for pixel with 12. What makes it 3D:
real lit spheres, soft shadows on a dark back wall 120 px behind, real strings, a metal
mount, motion blur instead of drawn trails. Dark scene (wall ~= the 2D background colour),
satin balls (no clear-coat, no emission on the balls except a soft flash on each hit).

Same motion clock as 12 (15 bobs, bob i makes K+(N-1-i) swings per 1224-frame cycle,
amplitude 0.415 rad, frame 0 = 6 frames after release, perfect line at frame 1218, then
0.2x slow motion), so 12's sound track, hook and banner are reused unchanged.

Glow values are animated as OBJECT custom properties read by an Attribute node (no
per-frame material changes, so Cycles does not re-sync shaders every frame).

Run (Blender 4.2+ / 5.x), always with an ABSOLUTE output folder:
  blender -b --factory-startup --python o01_pendulum3d.py -- OUT_DIR [--scale 1.0]
        [--samples 32] [--frames 0-1309] [--gpu]
Also works with the pip `bpy` module: python3 o01_pendulum3d.py -- OUT_DIR ...
"""
import math
import os
import sys

import bpy
from mathutils import Vector

# ------------------------------------------------------------------ args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "o01_out")
opt = {"--scale": "1.0", "--samples": "32", "--frames": "0-1309"}
flags = set()
i = 1
while i < len(argv):
    if argv[i] in opt:
        opt[argv[i]] = argv[i + 1]
        i += 2
    else:
        flags.add(argv[i])
        i += 1
SCALE = float(opt["--scale"])
SAMPLES = int(opt["--samples"])
FA, FB = [int(x) for x in opt["--frames"].split("-")]
os.makedirs(OUT, exist_ok=True)

# ------------------------------------------------------------------ motion (= 12)
TAU = 2 * math.pi
N, K, CYCLE_F, F0, AMP, SLOWMO = 15, 5, 1224, 6, 0.415, 0.2
ALIGN_F = CYCLE_F - F0          # 1218: video frame of the perfect line
NSW = [K + (N - 1 - i) for i in range(N)]   # i=0 inner/shortest/fastest
PX, PY = 540.0, 486.0           # shared pivot (video px)
R_IN, R_OUT = 232.0, 1010.0
RS = [R_IN + (R_OUT - R_IN) * i / (N - 1) for i in range(N)]
BOB_R, SLOT_R = 15.0, 21.0
NEAR = 0.035


def sim_f(f):
    return ALIGN_F + SLOWMO * (f - ALIGN_F) if f > ALIGN_F else f


def theta(i, f):
    g = sim_f(f) + F0
    return AMP * math.cos(TAU * ((NSW[i] * g) % CYCLE_F) / CYCLE_F)


def hit_frames(i):
    out, c = [], 1
    while True:
        tf = c * CYCLE_F / NSW[i] - F0
        if tf > ALIGN_F + 0.5:
            return out
        if tf >= 0:
            out.append(tf)
        c += 1


def W(x, y, depth=0.0):
    """video pixel (x, y down) -> world (X right, Y into the screen, Z up)."""
    return Vector(((x - 540.0) / 1000.0, depth, (960.0 - y) / 1000.0))


def pos_px(i, th):
    return (PX + RS[i] * math.sin(th), PY + RS[i] * math.cos(th))


# palette (= simreel.palette) -> linear
BG = (7, 7, 12)
WHITE = (242, 242, 247)
YELLOW = (255, 200, 59)
RAINBOW = [(255, 59, 107), (255, 138, 59), (255, 200, 59), (59, 255, 154), (59, 167, 255),
           (179, 107, 255)]


def mix(a, b, t):
    return tuple(round(a[k] + (b[k] - a[k]) * t) for k in range(3))


def gradient(t):                 # simreel.palette.gradient with RAINBOW (wraps)
    n = len(RAINBOW)
    x = (t % 1.0) * n
    k = int(x) % n
    return mix(RAINBOW[k], RAINBOW[(k + 1) % n], x - int(x))


def lin(c):
    def f(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


COL = [gradient(i / (N - 1) * 5.0 / 6.0) for i in range(N)]

# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
try:
    sc.cycles.denoising_use_gpu = True
except AttributeError:
    pass
sc.cycles.max_bounces = 4
sc.cycles.diffuse_bounces = 2
sc.cycles.glossy_bounces = 2
sc.cycles.transmission_bounces = 0
# LOOK presets (owner picks one from sample stills): satin (default), glossy, glass, metal,
# clay (matte balls + visible shadows on a lit wall), neon (self-lit glowing balls)
LOOK = os.environ.get("O1_LOOK", "satin")
if LOOK == "glass":
    sc.cycles.transmission_bounces = 6
    sc.cycles.max_bounces = 8
sc.render.use_persistent_data = True
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.5
sc.render.resolution_x = round(1080 * SCALE)
sc.render.resolution_y = round(1920 * SCALE)
sc.render.fps = 60
sc.frame_start, sc.frame_end = FA, FB
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"

if "--gpu" in flags:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                sc.cycles.device = "GPU"
                print("GPU:", kind, [d.name for d in devs])
                break
        except Exception:
            continue

world = bpy.data.worlds.new("w")
sc.world = world
world.use_nodes = True
wbg = world.node_tree.nodes["Background"]
wbg.inputs[0].default_value = lin(BG)
wbg.inputs[1].default_value = 1.0


def material(name, color, rough=0.35, metal=0.0, glow_color=None, glow_base=0.0, glow_gain=0.0):
    """Principled material. If glow_color is set, Emission Strength =
    glow_base + glow_gain * (object property "glow"), via an Attribute node."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if glow_color is not None:
        b.inputs["Emission Color"].default_value = glow_color
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_type = "OBJECT"
        at.attribute_name = "glow"
        mad = nt.nodes.new("ShaderNodeMath")
        mad.operation = "MULTIPLY_ADD"
        mad.inputs[1].default_value = glow_gain
        mad.inputs[2].default_value = glow_base
        nt.links.new(at.outputs["Fac"], mad.inputs[0])
        nt.links.new(mad.outputs[0], b.inputs["Emission Strength"])
    return m


def emissive(name, color, strength=1.0, gain=0.0, fade=False):
    """Pure emission (no lighting), strength + gain * object["glow"].
    fade=True: fully transparent while glow is 0 (fades in with glow)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = color
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "OBJECT"
    at.attribute_name = "glow"
    mad = nt.nodes.new("ShaderNodeMath")
    mad.operation = "MULTIPLY_ADD"
    mad.inputs[1].default_value = gain
    mad.inputs[2].default_value = strength
    nt.links.new(at.outputs["Fac"], mad.inputs[0])
    nt.links.new(mad.outputs[0], em.inputs["Strength"])
    out = em.outputs[0]
    if fade:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mx = nt.nodes.new("ShaderNodeMixShader")
        cl = nt.nodes.new("ShaderNodeMath")
        cl.operation = "MINIMUM"
        cl.inputs[1].default_value = 1.0
        nt.links.new(at.outputs["Fac"], cl.inputs[0])
        nt.links.new(cl.outputs[0], mx.inputs[0])
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(em.outputs[0], mx.inputs[2])
        out = mx.outputs[0]
    nt.links.new(out, nt.nodes["Material Output"].inputs[0])
    return m


def cyl(name, p1, p2, r, mat, verts=12):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=verts,
                                        location=(p1 + p2) / 2)
    o = bpy.context.object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    o.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return o


def sphere(name, loc, r, mat, seg=32):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=seg // 2,
                                         location=loc)
    o = bpy.context.object
    o.name = name
    bpy.ops.object.shade_smooth()
    o.data.materials.append(mat)
    return o


def set_glow(o, v, f):
    o["glow"] = float(v)
    o.keyframe_insert('["glow"]', frame=f)


# back wall: 120 px behind the pendulums, close to the 2D background colour; it only
# catches the soft shadows and a faint pool of light around the rig
wall_m = material("wall", lin((24, 24, 34) if LOOK == "clay" else (10, 10, 16)), rough=0.9)
for _k in ("Specular IOR Level", "Specular"):          # no sheen: the wall stays near-black
    if _k in wall_m.node_tree.nodes["Principled BSDF"].inputs:
        wall_m.node_tree.nodes["Principled BSDF"].inputs[_k].default_value = 0.0
        break
bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.12, 0), rotation=(math.pi / 2, 0, 0))
bpy.context.object.data.materials.append(wall_m)

steel = material("steel", lin((170, 172, 182)), rough=0.3, metal=1.0)
string_m = material("string", lin((225, 225, 232)), rough=0.5)
knob_m = material("knob", lin((235, 235, 240)), rough=0.35, metal=0.6)

# mount: the white bar + stub + pivot knob of the 2D video, as metal parts
cyl("bar", W(PX - 70, PY - 16), W(PX + 70, PY - 16), 0.0042, steel, 24)
cyl("stub", W(PX, PY - 16), W(PX, PY), 0.002, steel)
sphere("knob", W(PX, PY), 0.0085, knob_m)

# dotted target line (pivot -> outer release slot), faint like the 2D dots
dot_m = emissive("dots", lin(WHITE), strength=0.22)
ex, ey = pos_px(N - 1, AMP)
for k in range(1, 70):
    u = k / 70
    d = sphere(f"dot{k}", W(PX + (ex - PX) * u, PY + (ey - PY) * u, 0.004), 0.0018, dot_m, 8)
    d.visible_shadow = False

# gold line that lights up at the perfect line-up
gold_m = emissive("gold", lin(YELLOW), strength=0.0, gain=5.0, fade=True)
gold = cyl("goldline", W(PX, PY, -0.002), W(ex + (ex - PX) * 0.04, ey + (ey - PY) * 0.04, -0.002),
           0.0035, gold_m, 12)
gold.visible_shadow = False

# release slots: thin rings in each bob's colour, dim, lit while the bob sits in them
slots = []
for i in range(N):
    sx, sy = pos_px(i, AMP)
    bpy.ops.mesh.primitive_torus_add(major_radius=SLOT_R / 1000, minor_radius=0.0016,
                                     major_segments=48, minor_segments=8,
                                     location=W(sx, sy), rotation=(math.pi / 2, 0, 0))
    o = bpy.context.object
    o.name = f"slot{i}"
    o.data.materials.append(emissive(f"slotm{i}", lin(COL[i]), strength=0.12, gain=1.6))
    o.visible_shadow = False
    slots.append(o)

# pendulums: pivot empty rotated about Y (screen-plane swing), string + bob as children
pivots, bobs = [], []
for i in range(N):
    bpy.ops.object.empty_add(location=W(PX, PY))
    pv = bpy.context.object
    pv.name = f"pivot{i}"
    bob_m = material(f"bob{i}", lin(COL[i]), rough=0.25, glow_color=lin(COL[i]),
                     glow_base=0.0, glow_gain=1.2)
    bsdf = bob_m.node_tree.nodes["Principled BSDF"]
    if LOOK == "glossy":
        bsdf.inputs["Roughness"].default_value = 0.05
        bsdf.inputs["Coat Weight"].default_value = 1.0
        bsdf.inputs["Coat Roughness"].default_value = 0.02
    elif LOOK == "glass":
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.04
        bsdf.inputs["IOR"].default_value = 1.45
        mad = [n for n in bob_m.node_tree.nodes if n.type == "MATH"][0]
        mad.inputs[2].default_value = 0.6          # faint inner light so the glass reads on black
    elif LOOK == "metal":
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.18
    elif LOOK == "clay":
        bsdf.inputs["Roughness"].default_value = 0.75
    elif LOOK == "neon":
        bsdf.inputs["Roughness"].default_value = 0.2
        mad = [n for n in bob_m.node_tree.nodes if n.type == "MATH"][0]
        mad.inputs[2].default_value = 2.2          # self-lit core
        mad.inputs[1].default_value = 3.0
    b = sphere(f"bob{i}", W(PX, PY + RS[i]), BOB_R / 1000, bob_m, 32)
    s = cyl(f"str{i}", W(PX, PY), W(PX, PY + RS[i] - BOB_R * 0.6), 0.0009, string_m, 6)
    for o in (b, s):
        o.parent = pv
        o.matrix_parent_inverse = pv.matrix_world.inverted()
    pivots.append(pv)
    bobs.append(b)


# lights: soft key from the upper left (shadows fall down-right onto the wall), a faint
# cool fill from the right, and a dim pool on the wall behind the rig
def area(name, loc, target, energy, size, color=(1, 1, 1)):
    bpy.ops.object.light_add(type="AREA", location=loc)
    o = bpy.context.object
    o.name = name
    o.data.energy = energy
    o.data.size = size
    o.data.color = color
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y")
    return o


area("key", (-0.9, -1.4, 1.4), (0, 0, 0.1), float(os.environ.get("O1_KEY", "120" if LOOK in ("metal", "glass") else "80")), 0.8,
     (1.0, 0.97, 0.93))
area("fill", (1.2, -1.2, -0.2), (0, 0, 0.1), float(os.environ.get("O1_FILL", "10")), 1.2,
     (0.8, 0.88, 1.0))

if LOOK in ("glossy", "metal", "glass"):   # a long soft strip light for crisp reflections
    _st = area("strip", (0.6, -1.0, 1.0), (0, 0, 0.1), 40.0, 0.3, (1.0, 1.0, 1.0))
    _st.data.shape = "RECTANGLE"
    _st.data.size_y = 2.0

# orthographic camera = the 2D video's pixel grid
bpy.ops.object.camera_add(location=(0, -3.0, 0), rotation=(math.pi / 2, 0, 0))
cam = bpy.context.object
sc.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = 1.92
cam.data.sensor_fit = "VERTICAL"
cam.data.clip_end = 10

# ------------------------------------------------------------------ animation
FLASH = 0.3 * 60
hits = [hit_frames(i) for i in range(N)]
for f in range(FA, FB + 1):
    lit = 0.0
    if f >= ALIGN_F:
        lit = 1.0 - min(1.0, max(0.0, ((f - ALIGN_F) / 60 - 0.5) / 1.2)) ** 2 * 0.55
    for i in range(N):
        th = theta(i, f)
        pivots[i].rotation_euler = (0, -th, 0)     # +th swings the bob to screen-right
        pivots[i].keyframe_insert("rotation_euler", frame=f)
        age = min([f - h for h in hits[i] if f - h >= 0] + [9e9])
        if f >= ALIGN_F:
            age = min(age, f - ALIGN_F)
        g = max(0.0, 1.0 - age / FLASH) if age < 9e8 else 0.0
        set_glow(bobs[i], g * g, f)
        near = max(0.0, 1.0 - abs(th - AMP) / NEAR)
        set_glow(slots[i], max(near, lit), f)
    a = max(0.0, 1.0 - (f - ALIGN_F) / 90.0) if f >= ALIGN_F else 0.0
    set_glow(gold, a, f)

for o in pivots:
    ad = o.animation_data
    if ad and ad.action:
        try:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        except AttributeError:
            pass

# ------------------------------------------------------------------ render
sc.render.image_settings.file_format = "PNG"
sc.render.use_overwrite = False     # re-running the same command resumes where it stopped
sc.render.use_placeholder = True
sc.render.filepath = os.path.join(OUT, "f_####")
bpy.ops.render.render(animation=True)
print("DONE", OUT)

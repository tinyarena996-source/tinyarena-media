"""o01 - 3D pendulum wave (Blender / Cycles). A/B partner of 12-pendulum-wave.

Same motion clock as scenes/12-pendulum-wave.py (15 bobs, bob i makes K+(N-1-i)
swings per 1224-frame cycle, amplitude 0.415 rad, video frame 0 = 6 frames after
release, perfect line-up at video frame 1218, then 0.2x slow motion), so the
2D video's sound track, hook and banner can be reused unchanged: the ONLY
difference in the A/B test is 2D vs 3D look.

This script only renders the picture (no text, no sound). The cloud then
composites hook + banner + sound with scenes/o01-pendulum-3d.py.

Run (Blender 4.2+ / 5.x):
  blender -b --factory-startup --python o01_pendulum3d.py -- OUT_DIR [--scale 1.0]
        [--samples 64] [--frames 0-1309] [--gpu] [--video]
  --frames a-b      render only these video frames (inclusive), PNGs OUT_DIR/f_0000.png
  --video           write one high-quality mp4 (OUT_DIR/o01_3d.mp4) instead of PNGs
Also works with the pip `bpy` module: python3 o01_pendulum3d.py -- OUT_DIR ...
"""
import math
import os
import sys

import bpy
from mathutils import Vector

# ------------------------------------------------------------------ args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "o01_out"
opt = {"--scale": "1.0", "--samples": "64", "--frames": "0-1309"}
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
TOTAL_F = 1310                  # = 12's video length (21.833 s)
NSW = [K + (N - 1 - i) for i in range(N)]   # i=0 shortest/fastest


def sim_f(f):
    return ALIGN_F + SLOWMO * (f - ALIGN_F) if f > ALIGN_F else f


def theta(i, f):
    g = sim_f(f) + F0
    return AMP * math.cos(TAU * ((NSW[i] * g) % CYCLE_F) / CYCLE_F)


def hit_frames(i):
    """video frames (float) when bob i is back in its release slot (= its note in 12)."""
    out = []
    c = 1
    while True:
        tf = c * CYCLE_F / NSW[i] - F0
        if tf > ALIGN_F + 0.5:
            break
        if tf >= 0:
            out.append(tf)
        c += 1
    return out


# palette (simreel.palette) -> linear
def srgb(c):
    def f(u):
        u /= 255.0
        return u / 12.92 if u <= 0.04045 else ((u + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]), 1.0)


RAINBOW = [(255, 59, 107), (255, 138, 59), (255, 200, 59), (59, 255, 154), (59, 167, 255),
           (179, 107, 255)]


def gradient(t):
    t = min(1.0, max(0.0, t)) * (len(RAINBOW) - 1)
    k = min(int(t), len(RAINBOW) - 2)
    u = t - k
    a, b = RAINBOW[k], RAINBOW[k + 1]
    return tuple(a[j] + (b[j] - a[j]) * u for j in range(3))


# outer (long, slow) = purple, inner (short, fast) = pink, like 12
COL = [gradient(i / (N - 1) * 5 / 6) for i in range(N)]

# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 6
sc.cycles.glossy_bounces = 3
sc.cycles.transmission_bounces = 2
sc.cycles.diffuse_bounces = 2
sc.render.use_persistent_data = True
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.5
sc.render.resolution_x = round(1080 * SCALE)
sc.render.resolution_y = round(1920 * SCALE)
sc.render.fps = 60
sc.frame_start, sc.frame_end = FA, FB
try:
    sc.view_settings.view_transform = os.environ.get("O1_VT", "Standard")
except Exception:
    pass
sc.view_settings.exposure = 0.0

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
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = srgb((7, 7, 12))
bg.inputs[1].default_value = 1.0


def mat(name, color, rough=0.25, metal=0.0, coat=0.0, emit=None, emit_s=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for k in ("Coat Weight", "Clearcoat"):
        if k in b.inputs:
            b.inputs[k].default_value = coat
            break
    if emit is not None:
        b.inputs["Emission Color"].default_value = emit
        b.inputs["Emission Strength"].default_value = emit_s
    return m


def cyl(name, p1, p2, r, material, verts=16):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, vertices=verts,
                                        location=(p1 + p2) / 2)
    o = bpy.context.object
    o.name = name
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    o.data.materials.append(material)
    bpy.ops.object.shade_smooth()
    return o


# geometry (metres-ish). Bar along X at height TOP; bobs swing in the Y-Z plane.
TOP = 2.2
X0, X1 = -1.4, 1.4            # bob 0 (short) at X0 ... bob 14 (long) at X1
L_SHORT, L_LONG = 0.75, 1.75
BOB_R = 0.088
XS = [X0 + (X1 - X0) * i / (N - 1) for i in range(N)]
LS = [L_SHORT + (L_LONG - L_SHORT) * i / (N - 1) for i in range(N)]

steel = mat("steel", srgb((150, 155, 168)), rough=0.28, metal=1.0)
dark = mat("dark", srgb((26, 27, 36)), rough=0.5, metal=0.6)
string = mat("string", srgb((205, 208, 220)), rough=0.6)
floor_m = mat("floor", srgb((6, 6, 10)), rough=0.45)

# floor (glossy dark, soft reflections) - large disc fading into the background
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=9, fill_type="NGON", location=(0, 0, 0))
fl = bpy.context.object
fl.data.materials.append(floor_m)

# frame: the bar hangs from two thin rods that run up out of shot (no legs in the way
# of the camera), with a small end cap at each end
cyl("bar", (X0 - 0.35, 0, TOP), (X1 + 0.35, 0, TOP), 0.03, steel, 32)
for x in (X0 - 0.3, X1 + 0.3):
    cyl("rod", (x, 0, TOP), (x, 2.6, TOP + 5.0), 0.012, steel)   # leans away from camera
for x in (X0 - 0.35, X1 + 0.35):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.045, location=(x, 0, TOP))
    bpy.context.object.data.materials.append(dark)
    bpy.ops.object.shade_smooth()

# release target line: the line every bob starts on (and comes back to at the end)
gold = mat("gold", srgb((120, 95, 30)), rough=0.3, emit=srgb((255, 200, 59)), emit_s=0.0)


def slot(i):
    a = AMP
    return Vector((XS[i], LS[i] * math.sin(a), TOP - LS[i] * math.cos(a)))


line = cyl("target", slot(0) + (slot(0) - slot(N - 1)) * 0.06,
           slot(N - 1) + (slot(N - 1) - slot(0)) * 0.06, 0.006, gold)
line.visible_shadow = False

# pendulums: a pivot empty per bob, rotated about X; V-shaped double string + bob
pivots, bobs, bob_mats = [], [], []
for i in range(N):
    bpy.ops.object.empty_add(location=(XS[i], 0, TOP))
    pv = bpy.context.object
    pv.name = f"pivot{i}"
    m = mat(f"bob{i}", srgb(COL[i]), rough=0.12, coat=1.0, emit=srgb(COL[i]), emit_s=0.0)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=BOB_R, segments=48, ring_count=24,
                                         location=(XS[i], 0, TOP - LS[i]))
    b = bpy.context.object
    b.name = f"bob{i}"
    bpy.ops.object.shade_smooth()
    b.data.materials.append(m)
    b.parent = pv
    b.matrix_parent_inverse = pv.matrix_world.inverted()
    bob_top = Vector((XS[i], 0, TOP - LS[i] + BOB_R * 0.8))
    for dx in (-0.06, 0.06):
        s = cyl(f"str{i}", (XS[i] + dx, 0, TOP), bob_top, 0.0028, string, 8)
        s.parent = pv
        s.matrix_parent_inverse = pv.matrix_world.inverted()
        s.visible_shadow = False
    pivots.append(pv)
    bobs.append(b)
    bob_mats.append(m)

# lights: big soft key from upper front-left, cool rim from behind, warm fill
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


area("key", (0.5, -1.8, 5.5), (0, 0, 1.4), 900, 2.5, (1.0, 0.97, 0.93))
area("rim", (2.5, 4.0, 3.5), (0, 0, 1.4), 650, 2.5, (0.75, 0.85, 1.0))
area("fill", (4.0, -3.0, 1.2), (0, 0, 1.2), 180, 4.0, (1.0, 0.9, 0.85))

# camera: slow arc. Frame 0 = 3/4 view from the front; it drifts round towards the
# side so the snake waves read in depth; the line-up is seen from a raised 3/4 view.
CAM = [float(v) for v in os.environ.get("O1_CAM", "3.6,-1.0,2.9,-0.1,0.2,1.25,27").split(",")]
bpy.ops.object.camera_add()
cam = bpy.context.object
sc.camera = cam
cam.data.lens = CAM[6]
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 4.0
bpy.ops.object.empty_add(location=(CAM[3], CAM[4], CAM[5]))
aim = bpy.context.object
tc = cam.constraints.new("TRACK_TO")
tc.target = aim
tc.track_axis = "TRACK_NEGATIVE_Z"
tc.up_axis = "UP_Y"
cam.data.dof.focus_object = aim


def cam_at(f):
    # looks down the bar from the long-pendulum end, so the row of bobs runs up the
    # phone screen and every swing is a left-right move (the snake reads clearly)
    u = 0.5 - 0.5 * math.cos(math.pi * min(1.0, f / ALIGN_F))
    sway = 0.35 * (u - 0.5)
    return Vector((CAM[0], CAM[1] + sway, CAM[2] - 0.15 * u))


# ------------------------------------------------------------------ animation
FLASH = 0.3 * 60   # frames a bob glows after reaching its slot (same as 12)
hits = [hit_frames(i) for i in range(N)]
for f in range(FA, FB + 1):
    sc.frame_set(f)
    for i in range(N):
        pivots[i].rotation_euler = (theta(i, f), 0, 0)
        pivots[i].keyframe_insert("rotation_euler", frame=f)
        age = min([f - h for h in hits[i] if f - h >= 0] + [9e9])
        if f >= ALIGN_F:
            age = min(age, f - ALIGN_F)
        g = max(0.0, 1.0 - age / FLASH) if age < 9e8 else 0.0
        bsdf = bob_mats[i].node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Emission Strength"].default_value = 2.5 * g * g
        bsdf.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    lit = 0.0
    if f >= ALIGN_F:
        a = (f - ALIGN_F) / 60.0
        lit = max(0.0, 1.0 - a / 1.5)
    gb = gold.node_tree.nodes["Principled BSDF"]
    gb.inputs["Emission Strength"].default_value = 0.08 + 14.0 * lit
    gb.inputs["Emission Strength"].keyframe_insert("default_value", frame=f)
    cam.location = cam_at(f)
    cam.keyframe_insert("location", frame=f)

for o in [cam] + pivots:
    if o.animation_data and o.animation_data.action:
        try:
            for fc in o.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        except AttributeError:
            pass

# ------------------------------------------------------------------ render
if "--video" in flags:
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
    sc.render.ffmpeg.ffmpeg_preset = "GOOD"
    sc.render.filepath = os.path.join(OUT, "o01_3d.mp4")
    bpy.ops.render.render(animation=True)
else:
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = os.path.join(OUT, "f_####")
    if "--blend" in flags:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "o01.blend"))
    bpy.ops.render.render(animation=True)
print("DONE", OUT)

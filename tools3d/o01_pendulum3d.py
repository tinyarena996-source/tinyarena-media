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
BOB_R = float(os.environ.get("O1_BOB", "15"))   # 2D video: 15 px
SLOT_R = BOB_R + 6.0
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
# clay (matte balls + visible shadows on a lit wall), neon (self-lit glowing balls),
# premium blackgold / jewel / pearl, toon comic / anime / pop (see "toon looks")
LOOK = os.environ.get("O1_LOOK", "satin")
PREMIUM = LOOK in ("blackgold", "jewel", "pearl")
TOON = LOOK in ("comic", "anime", "pop")
if LOOK in ("glass", "jewel"):
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


shadow_pivots = []
# ------------------------------------------------------------------ toon looks
# comic (US comic: cream paper, ink outlines, halftone shadows, flat drop shadow),
# anime (cel: 2D dark background, two-tone shading, coloured outlines),
# pop (pop art: yellow halftone paper, thick ink, solid black drop shadow).
# All pure emission computed from the surface normal, so no lights, no noise, fast.
if TOON:
    TS = {
        "comic": dict(paper=(246, 236, 212), pdot=(228, 205, 165), pdot_sp=14, pdot_r=(0.06, 0.34),
                      ink=(28, 22, 34), line=3.5, shadow=(214, 199, 168), sh_off=(6, 8),
                      shade=0.62, tone=True, string=(28, 22, 34), dots=(28, 22, 34),
                      gold=(230, 57, 70)),
        "anime": dict(paper=(12, 12, 22), pdot=None, ink=None, line=2.5, shadow=None,
                      shade=0.6, tone=False, string=(225, 225, 235), dots=WHITE, gold=YELLOW),
        "pop": dict(paper=(255, 222, 74), pdot=(255, 190, 70), pdot_sp=18, pdot_r=(0.24, 0.30),
                    ink=(15, 12, 18), line=4.5, shadow=(15, 12, 18), sh_off=(7, 9),
                    shade=0.6, tone=True, string=(15, 12, 18), dots=(15, 12, 18),
                    gold=(255, 40, 120)),
    }[LOOK]
    sc.cycles.use_denoising = False
    sc.render.use_motion_blur = False
    sc.cycles.max_bounces = 0
    wbg.inputs[0].default_value = lin(TS["paper"])
    L1 = Vector((-0.45, -0.7, 0.55)).normalized()      # key light direction (upper left, front)
    L2 = Vector((-0.38, -0.82, 0.43)).normalized()     # highlight spot

    def _node(nt, typ, **kw):
        n = nt.nodes.new(typ)
        for k, v in kw.items():
            setattr(n, k, v)
        return n

    def _math(nt, op, a, b):
        n = _node(nt, "ShaderNodeMath", operation=op)
        for k, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs[0]

    def _vmath(nt, op, a, b=None):
        n = _node(nt, "ShaderNodeVectorMath", operation=op)
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (tuple, Vector)):
                n.inputs[k].default_value = tuple(v)[:3]
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH") else n.outputs["Vector"]

    def _mix(nt, fac, a, b):
        n = _node(nt, "ShaderNodeMix", data_type="RGBA")
        for sock, v in ((n.inputs[0], fac), (n.inputs[6], a), (n.inputs[7], b)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            elif isinstance(v, tuple):
                sock.default_value = v
            else:
                nt.links.new(v, sock)
        return n.outputs[2]

    def _win(nt):
        return _node(nt, "ShaderNodeTexCoord").outputs["Window"]

    def _halftone(nt, spacing, radius):
        g = _vmath(nt, "MULTIPLY", _win(nt), (1080 / spacing, 1920 / spacing, 0))
        g = _vmath(nt, "SUBTRACT", _vmath(nt, "FRACTION", g), (0.5, 0.5, 0))
        return _math(nt, "LESS_THAN", _vmath(nt, "LENGTH", g), radius)

    def _glow(nt):
        a = _node(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="glow")
        return a.outputs["Fac"]

    def _emit(m, nt, col, alpha=None):
        em = _node(nt, "ShaderNodeEmission")
        nt.links.new(col, em.inputs["Color"]) if not isinstance(col, tuple) else None
        if isinstance(col, tuple):
            em.inputs["Color"].default_value = col
        out = em.outputs[0]
        if alpha is not None:
            tr = _node(nt, "ShaderNodeBsdfTransparent")
            mx = _node(nt, "ShaderNodeMixShader")
            nt.links.new(alpha, mx.inputs[0])
            nt.links.new(tr.outputs[0], mx.inputs[1])
            nt.links.new(out, mx.inputs[2])
            out = mx.outputs[0]
        nt.links.new(out, nt.nodes["Material Output"].inputs[0])

    def _new(name):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        for n in list(m.node_tree.nodes):
            if n.type != "OUTPUT_MATERIAL":
                m.node_tree.nodes.remove(n)
        return m, m.node_tree

    def flat(name, c):
        m, nt = _new(name)
        _emit(m, nt, lin(c))
        return m

    def toon(name, c, flash=0.0, spot=True):
        """cel-shaded ball: lit / shadow bands from the normal, halftone dots in the shadow,
        a hard white highlight spot, and a flash toward white with object["glow"]."""
        m, nt = _new(name)
        nrm = _node(nt, "ShaderNodeNewGeometry").outputs["Normal"]
        d1 = _vmath(nt, "DOT_PRODUCT", nrm, L1)
        lit = _math(nt, "GREATER_THAN", d1, 0.05)
        shc = mix(c, (40, 30, 90), 0.18)
        shc = tuple(round(v * TS["shade"]) for v in shc)
        shadow = lin(shc)
        if TS["tone"]:
            dk = lin(tuple(round(v * 0.55) for v in shc))
            shadow = _mix(nt, _halftone(nt, 5.0, 0.32), lin(shc), dk)
        col = _mix(nt, lit, shadow, lin(c))
        if spot:
            hi = _math(nt, "GREATER_THAN", _vmath(nt, "DOT_PRODUCT", nrm, L2), 0.93)
            col = _mix(nt, hi, col, lin((255, 255, 255)))
        if flash:
            f = _math(nt, "MINIMUM", _math(nt, "MULTIPLY", _glow(nt), flash), 1.0)
            col = _mix(nt, f, col, lin((255, 255, 250)))
        _emit(m, nt, col)
        return m

    def fade_ring(name, c0, c1):
        """emission colour c0 -> c1 with object["glow"] (release slots)."""
        m, nt = _new(name)
        _emit(m, nt, _mix(nt, _math(nt, "MINIMUM", _glow(nt), 1.0), lin(c0), lin(c1)))
        return m

    # paper: flat colour plus halftone dots that grow toward the corners
    m, nt = _new("paper")
    col = lin(TS["paper"])
    if TS["pdot"]:
        w = _vmath(nt, "MULTIPLY", _vmath(nt, "SUBTRACT", _win(nt), (0.5, 0.5, 0)), (1.0, 1.78, 0))
        r0, r1 = TS["pdot_r"]
        rad = _math(nt, "ADD", _math(nt, "MULTIPLY", _vmath(nt, "LENGTH", w), r1 - r0), r0)
        col = _mix(nt, _halftone(nt, TS["pdot_sp"], rad), lin(TS["paper"]), lin(TS["pdot"]))
    _emit(m, nt, col)
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.3, 0), rotation=(math.pi / 2, 0, 0))
    bpy.context.object.data.materials.append(m)

    LW = TS["line"] / 1000.0
    ink_c = TS["ink"]

    # mount
    metal_c = (60, 60, 72) if LOOK != "anime" else (200, 202, 214)
    m_mount = toon("mount", metal_c)
    out_m = flat("ink", ink_c if ink_c else (5, 5, 10))
    cyl("bar", W(PX - 70, PY - 16), W(PX + 70, PY - 16), 0.0042, m_mount, 24)
    cyl("bar_o", W(PX - 70 - TS["line"], PY - 16, 0.01), W(PX + 70 + TS["line"], PY - 16, 0.01),
        0.0042 + LW, out_m, 24)
    cyl("stub", W(PX, PY - 16), W(PX, PY), 0.002, m_mount)
    sphere("knob", W(PX, PY), 0.0085, m_mount)
    sphere("knob_o", W(PX, PY, 0.01), 0.0085 + LW, out_m)

    # target dots + line-up line
    dot_m = flat("dots", mix(TS["dots"], TS["paper"], 0.55))
    ex, ey = pos_px(N - 1, AMP)
    for k in range(1, 70):
        u = k / 70
        sphere(f"dot{k}", W(PX + (ex - PX) * u, PY + (ey - PY) * u, 0.02), 0.0018, dot_m, 8)
    m, nt = _new("gold")
    _emit(m, nt, lin(TS["gold"]), alpha=_math(nt, "MINIMUM", _glow(nt), 1.0))
    gold = cyl("goldline", W(PX, PY, 0.015), W(ex + (ex - PX) * 0.04, ey + (ey - PY) * 0.04, 0.015),
               0.0045, m, 12)

    slots = []
    for i in range(N):
        sx, sy = pos_px(i, AMP)
        bpy.ops.mesh.primitive_torus_add(major_radius=SLOT_R / 1000, minor_radius=0.0018,
                                         major_segments=48, minor_segments=8,
                                         location=W(sx, sy, 0.02), rotation=(math.pi / 2, 0, 0))
        o = bpy.context.object
        o.name = f"slot{i}"
        o.data.materials.append(fade_ring(f"slotm{i}", mix(COL[i], TS["paper"], 0.6), COL[i]))
        slots.append(o)

    # pendulums (+ outlines behind, + a flat drop shadow pendulum offset down-right)
    pivots, bobs = [], []
    string_m = flat("string", TS["string"])
    shadow_m = flat("dropshadow", TS["shadow"]) if TS["shadow"] else None
    for i in range(N):
        bpy.ops.object.empty_add(location=W(PX, PY))
        pv = bpy.context.object
        pv.name = f"pivot{i}"
        oc = ink_c if ink_c else tuple(round(v * 0.42) for v in COL[i])
        parts = [sphere(f"bob{i}", W(PX, PY + RS[i]), BOB_R / 1000, toon(f"bob{i}", COL[i], 0.75), 32),
                 sphere(f"bob{i}_o", W(PX, PY + RS[i], 0.01), BOB_R / 1000 + LW, flat(f"bo{i}", oc), 32),
                 cyl(f"str{i}", W(PX, PY), W(PX, PY + RS[i] - BOB_R * 0.6), 0.0011, string_m, 6)]
        bobs.append(parts[0])
        for o in parts:
            o.parent = pv
            o.matrix_parent_inverse = pv.matrix_world.inverted()
        pivots.append(pv)
        if shadow_m:
            dx, dy = TS["sh_off"]
            bpy.ops.object.empty_add(location=W(PX + dx, PY + dy, 0.2))
            sp = bpy.context.object
            sp.name = f"shpivot{i}"
            sparts = [sphere(f"sh{i}", W(PX + dx, PY + dy + RS[i], 0.2), BOB_R / 1000 + LW, shadow_m, 24)]
            if LOOK == "comic":     # pop: ball shadows only (string shadows read as double lines)
                sparts.append(cyl(f"shs{i}", W(PX + dx, PY + dy, 0.2), W(PX + dx, PY + dy + RS[i], 0.2),
                                  0.0011, shadow_m, 6))
            for o in sparts:
                o.parent = sp
                o.matrix_parent_inverse = sp.matrix_world.inverted()
            shadow_pivots.append((i, sp))


if not TOON:
    # back wall: 120 px behind the pendulums, close to the 2D background colour; it only
    # catches the soft shadows and a faint pool of light around the rig
    wall_m = material("wall", lin((24, 24, 34) if LOOK == "clay" else (8, 8, 11) if PREMIUM
                                  else (10, 10, 16)), rough=0.9)
    for _k in ("Specular IOR Level", "Specular"):          # no sheen: the wall stays near-black
        if _k in wall_m.node_tree.nodes["Principled BSDF"].inputs:
            wall_m.node_tree.nodes["Principled BSDF"].inputs[_k].default_value = 0.0
            break
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0.12, 0), rotation=(math.pi / 2, 0, 0))
    bpy.context.object.data.materials.append(wall_m)

    steel = material("steel", lin((170, 172, 182)), rough=0.3, metal=1.0)
    string_m = material("string", lin((225, 225, 232)), rough=0.5)
    knob_m = material("knob", lin((235, 235, 240)), rough=0.35, metal=0.6)
    if LOOK == "blackgold":          # brushed gold mount, fine gold wires
        steel = material("gold_metal", lin((255, 196, 110)), rough=0.22, metal=1.0)
        string_m = material("gold_wire", lin((240, 190, 110)), rough=0.3, metal=1.0)
        knob_m = steel
    elif LOOK == "jewel":            # polished silver
        steel = material("silver", lin((235, 235, 242)), rough=0.12, metal=1.0)
        string_m = material("silver_wire", lin((225, 225, 235)), rough=0.2, metal=1.0)
        knob_m = steel
    elif LOOK == "pearl":            # champagne metal
        steel = material("champagne", lin((235, 215, 185)), rough=0.25, metal=1.0)
        string_m = material("champ_wire", lin((235, 220, 200)), rough=0.3, metal=1.0)
        knob_m = steel

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
        elif LOOK == "blackgold":      # deep lacquer, mirror coat
            bsdf.inputs["Roughness"].default_value = 0.12
            bsdf.inputs["Coat Weight"].default_value = 1.0
            bsdf.inputs["Coat Roughness"].default_value = 0.01
        elif LOOK == "jewel":          # cut-glass gem with a faint inner light
            bsdf.inputs["Transmission Weight"].default_value = 1.0
            bsdf.inputs["Roughness"].default_value = 0.0
            bsdf.inputs["IOR"].default_value = 1.7
            mad = [n for n in bob_m.node_tree.nodes if n.type == "MATH"][0]
            mad.inputs[2].default_value = 0.9
        elif LOOK == "pearl":          # glazed porcelain
            bsdf.inputs["Roughness"].default_value = 0.4
            bsdf.inputs["Coat Weight"].default_value = 1.0
            bsdf.inputs["Coat Roughness"].default_value = 0.04
            bsdf.inputs["Sheen Weight"].default_value = 0.4
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
        o.visible_camera = False        # lights show up in reflections, never as shapes in shot
        return o


    area("key", (-0.9, -1.4, 1.4), (0, 0, 0.1), float(os.environ.get("O1_KEY", "120" if LOOK in ("metal", "glass") else "80")), 0.8,
         (1.0, 0.97, 0.93))
    area("fill", (1.2, -1.2, -0.2), (0, 0, 0.1), float(os.environ.get("O1_FILL", "10")), 1.2,
         (0.8, 0.88, 1.0))

    if PREMIUM:
        # product-shot lighting: a soft spot pool on the backdrop behind the rig (vignette),
        # two rim lights from behind that draw a thin bright edge on every ball and wire
        bpy.ops.object.light_add(type="SPOT", location=(0, -1.6, 1.1))
        sp = bpy.context.object
        sp.data.energy = float(os.environ.get("O1_POOL", "160"))
        sp.data.spot_size = math.radians(38)
        sp.data.spot_blend = 1.0
        sp.data.shadow_soft_size = 0.4
        sp.data.color = (1.0, 0.93, 0.85) if LOOK != "jewel" else (0.85, 0.9, 1.0)
        sp.rotation_mode = "QUATERNION"
        sp.rotation_quaternion = (Vector((0, 0.12, 0.08)) - sp.location).to_track_quat("-Z", "Y")
        rim = float(os.environ.get("O1_RIM", "60"))
        area("rimL", (-1.2, 0.08, 0.95), (0.2, -1.0, 0.1), rim, 0.3, (1.0, 0.95, 0.88))
        area("rimR", (1.2, 0.08, -0.45), (-0.2, -1.0, 0.2), rim, 0.3, (0.85, 0.9, 1.0))
    if LOOK in ("glossy", "metal", "glass", "blackgold", "jewel", "pearl"):   # long soft strip light for crisp reflections
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
    for i, sp in shadow_pivots:
        sp.rotation_euler = pivots[i].rotation_euler
        sp.keyframe_insert("rotation_euler", frame=f)
    a = max(0.0, 1.0 - (f - ALIGN_F) / 90.0) if f >= ALIGN_F else 0.0
    set_glow(gold, a, f)

for o in pivots + [sp for _, sp in shadow_pivots]:
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

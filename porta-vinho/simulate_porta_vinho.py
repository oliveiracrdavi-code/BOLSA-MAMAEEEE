"""Porta-vinho: geometria em escala real e teste de física no Blender.

A mola angular SPRING2 do Bullet foi calibrada contra o equilíbrio
de uma barra rígida (k em N·m/rad). Cada dobradiça da bolsa usa

    k = E I / L

com I da seção estrutural daquele caso. Ver ficha-tecnica.md.
"""
from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, "/workspace/porta-vinho")
import dimensions as D

ROOT = Path("/workspace/porta-vinho")
ART = Path("/opt/cursor/artifacts")
ART.mkdir(parents=True, exist_ok=True)

CASE = "caseB"
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1 :]
    if args:
        CASE = args[0]

NU = D.NU
PITCH = D.MONTANA_PITCH
HOLE_R = D.MONTANA_HOLE / 2.0


def plate_I(b, t):
    return b * (t ** 3) / 12.0


def tube_I(r, t):
    return math.pi * (r ** 3) * t


def flexural_D(E, t):
    return E * (t ** 3) / (12.0 * (1.0 - NU * NU))


def stiffness():
    """Molas das dobradiças. Estimativa estrutural, não ensaio."""
    h_body = D.CYL_H
    h_handle = D.HANDLE_H
    info = {
        "mapping": "k_Nm_per_rad = E*I/L  →  rigid_body_constraint.spring_stiffness_ang_z (SPRING2)",
        "calibration": "Barra de 0,20 m, 0,10 kg, θ0=8°: k=0,2 assentou em 15,47° (teoria 15,52°); k=2,0 em 8,41° (teoria 8,41°).",
        "imperfection_deg": D.IMPERFECTION_DEG,
    }
    if CASE == "caseA":
        # Chapa aberta. Sem aro, o cilindro não guarda a seção tubular.
        I_panel = plate_I(D.PANEL_W, D.MONTANA_T)
        I_cyl = plate_I(0.040, D.MONTANA_T)
        info.update(
            {
                "model": "Somente montana perfurado. I = b t³/12 da chapa aberta. Seção tubular não creditada: sem aro ela ovaliza.",
                "I_panel_m4": I_panel,
                "I_cyl_m4": I_cyl,
                "k_body": D.MONTANA_E * I_panel / h_body,
                "k_handle": D.MONTANA_E * I_panel / h_handle,
                "k_cyl": D.MONTANA_E * I_cyl / h_body,
                "leather_added": [],
            }
        )
    else:
        # Nervuras de couro nos 4 cantos do berço, afastadas bay_d/2 do eixo neutro.
        rib_b = 0.016
        rib_t = D.LEATHER_T
        area = rib_b * rib_t
        d = D.BAY_D / 2.0
        I_frame = 4.0 * area * d * d
        # O sanduíche plano (2×2,2 mm coladas) deixou a alça cair até 39° no
        # simulador — a mola k=0,73 N·m/rad não venceu o momento. Acrescentei
        # o mínimo que segurou: canal de couro, duas paredes afastadas 12 mm.
        b_ch, t_ch, d_ch = 0.090, D.LEATHER_T, 0.012
        I_handle = 2.0 * (plate_I(b_ch, t_ch) + b_ch * t_ch * (d_ch / 2.0) ** 2)
        # Aro + duas nervuras verticais no cilindro.
        I_tube = tube_I(D.CYL_R, D.MONTANA_T)
        rib_a = 0.010 * D.LEATHER_T
        I_cyl = I_tube + 2.0 * rib_a * (D.CYL_R ** 2)
        info.update(
            {
                "model": "Couro como ossatura. Berço: 4 nervuras. Alça: canal de duas paredes de 2,2 mm afastadas 12 mm (o sanduíche plano de 4,4 mm não segurou). Cilindro: aro + 2 nervuras.",
                "rib_b_m": rib_b,
                "handle_channel_gap_m": d_ch,
                "I_frame_m4": I_frame,
                "I_handle_m4": I_handle,
                "I_cyl_m4": I_cyl,
                "k_body": D.LEATHER_E * I_frame / h_body,
                "k_handle": D.LEATHER_E * I_handle / h_handle,
                "k_cyl": D.MONTANA_E * I_cyl / h_body,
                "leather_added": [
                    "base/plinto 2,2 mm",
                    "4 nervuras verticais 16×2,2 mm nos cantos do berço",
                    "pisos de couro nos cilindros",
                    "aros superiores de couro (12 mm de altura)",
                    "sanduíche plano 2×2,2 mm — insuficiente, alça foi a 39°",
                    "canal de couro na alça: 2 paredes 90×2,2 mm afastadas 12 mm",
                    "2 nervuras verticais 10×2,2 mm em cada cilindro",
                    "debrum de couro na borda do painel",
                ],
            }
        )
    info["D_montana_Nm"] = flexural_D(D.MONTANA_E, D.MONTANA_T)
    info["D_leather_Nm"] = flexural_D(D.LEATHER_E, D.LEATHER_T)
    return info


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def new_mesh_object(name, bm):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link(ob)
    return ob


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def montana_material():
    mat = bpy.data.materials.new("montana_perfurado")
    mat.use_nodes = True
    mat.blend_method = "CLIP"
    mat.shadow_method = "CLIP"
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    mod = nt.nodes.new("ShaderNodeVectorMath")
    mod.operation = "MODULO"
    mod.inputs[1].default_value = (PITCH, PITCH, PITCH)
    sub = nt.nodes.new("ShaderNodeVectorMath")
    sub.operation = "SUBTRACT"
    sub.inputs[1].default_value = (PITCH / 2, PITCH / 2, PITCH / 2)
    dist = nt.nodes.new("ShaderNodeVectorMath")
    dist.operation = "LENGTH"
    hole = nt.nodes.new("ShaderNodeMath")
    hole.operation = "LESS_THAN"
    hole.inputs[1].default_value = HOLE_R
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.40, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.48
    trans = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Object"], mod.inputs[0])
    nt.links.new(mod.outputs["Vector"], sub.inputs[0])
    nt.links.new(sub.outputs["Vector"], dist.inputs[0])
    nt.links.new(dist.outputs["Value"], hole.inputs[0])
    nt.links.new(hole.outputs["Value"], mix.inputs["Fac"])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    nt.links.new(trans.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def leather_material():
    mat = bpy.data.materials.new("couro_rigido")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.38, 0.20, 0.08, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.42
    return mat


def simple_material(name, color, rough=0.4, metal=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    if alpha < 1.0:
        mat.blend_method = "BLEND"
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Alpha"].default_value = alpha
    return mat


def assign(obj, mat):
    obj.data.materials.append(mat)


def rounded_panel(name, w, h, t, radius, slot=None):
    bm = bmesh.new()
    pts = [(-w / 2, -h / 2), (-w / 2, h / 2 - radius)]
    cx, cz = -w / 2 + radius, h / 2 - radius
    for i in range(1, 7):
        a = math.pi - i * (math.pi / 2) / 6
        pts.append((cx + radius * math.cos(a), cz + radius * math.sin(a)))
    cx, cz = w / 2 - radius, h / 2 - radius
    for i in range(0, 7):
        a = math.pi / 2 - i * (math.pi / 2) / 6
        pts.append((cx + radius * math.cos(a), cz + radius * math.sin(a)))
    pts.append((w / 2, -h / 2))
    verts = [bm.verts.new((x, -t / 2, z)) for x, z in pts]
    face = bm.faces.new(verts)
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    extruded = [e for e in ret["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=extruded, vec=(0, t, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_mesh_object(name, bm)
    if slot:
        sw, sh, from_top = slot
        cz = h / 2 - from_top - sh / 2
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
        cutter = bpy.context.active_object
        cutter.name = name + "_cut"
        cutter.scale = (sw * 0.5, t * 4, sh * 0.5)
        cutter.location = ob.location + Vector((0, 0, cz))
        activate(cutter)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        activate(ob)
        mod = ob.modifiers.new("slot", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        if hasattr(mod, "solver"):
            try:
                mod.solver = "FAST"
            except TypeError:
                pass
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    return ob


def open_cylinder(name, r, h, n=32):
    bm = bmesh.new()
    bot, top = [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = r * math.cos(a), r * math.sin(a)
        bot.append(bm.verts.new((x, y, -h / 2)))
        top.append(bm.verts.new((x, y, h / 2)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    c = bm.verts.new((0, 0, -h / 2))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((c, bot[j], bot[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_mesh_object(name, bm)


def disc(name, r, z, n=28):
    bm = bmesh.new()
    c = bm.verts.new((0, 0, z))
    ring = []
    for i in range(n):
        a = 2 * math.pi * i / n
        ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((c, ring[i], ring[j]))
    return new_mesh_object(name, bm)


def ring_band(name, r, h, t, n=32):
    bm = bmesh.new()
    ro, ri = r, max(0.004, r - t)
    rings = []
    for z in (-h / 2, h / 2):
        outer, inner = [], []
        for i in range(n):
            a = 2 * math.pi * i / n
            outer.append(bm.verts.new((ro * math.cos(a), ro * math.sin(a), z)))
            inner.append(bm.verts.new((ri * math.cos(a), ri * math.sin(a), z)))
        rings.append((outer, inner))
    (bo, bi), (to, ti) = rings
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bo[i], bo[j], to[j], to[i]))
        bm.faces.new((bi[j], bi[i], ti[i], ti[j]))
        bm.faces.new((bo[i], bi[i], bi[j], bo[j]))
        bm.faces.new((to[j], ti[j], ti[i], to[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_mesh_object(name, bm)


def box(name, sx, sy, sz):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    return new_mesh_object(name, bm)


def stitches_along(name, points, parent, pitch=0.0045, size=(0.0022, 0.0006, 0.0007)):
    bm = bmesh.new()
    for a, b in zip(points, points[1:]):
        a, b = Vector(a), Vector(b)
        seg = b - a
        n = max(1, int(seg.length / pitch))
        direction = seg.normalized()
        for i in range(n):
            if i % 2 == 0:
                continue
            p = a + seg * ((i + 0.5) / n)
            cube = bmesh.ops.create_cube(bm, size=1.0)
            bmesh.ops.scale(bm, vec=size, verts=cube["verts"])
            bmesh.ops.translate(bm, vec=p, verts=cube["verts"])
    if not bm.verts:
        bm.free()
        return None
    ob = new_mesh_object(name, bm)
    ob.parent = parent
    return ob


def set_cols(obj, groups):
    cols = obj.rigid_body.collision_collections
    for i in range(20):
        cols[i] = i in groups


def add_rigid(obj, mass, kinematic=False, groups=None):
    activate(obj)
    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "PASSIVE" if kinematic else "ACTIVE"
    rb.kinematic = kinematic
    rb.mass = max(mass, 0.001)
    rb.collision_shape = "BOX" if kinematic else "CONVEX_HULL"
    rb.friction = 0.85
    rb.restitution = 0.0
    rb.use_margin = True
    rb.collision_margin = 0.0004
    rb.use_deactivation = False
    rb.linear_damping = 0.08
    rb.angular_damping = 0.12
    if groups is not None:
        set_cols(obj, groups)
    return rb


def add_hinge(name, a, b, location, k):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.02
    empty.location = Vector(location)
    # eixo local Z do empty = X do mundo (tombo para a frente)
    empty.rotation_euler = (0.0, math.radians(90.0), 0.0)
    link(empty)
    activate(empty)
    bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")
    c = empty.rigid_body_constraint
    c.object1 = a
    c.object2 = b
    c.spring_type = "SPRING2"
    c.disable_collisions = True
    for ax in "xyz":
        setattr(c, f"use_limit_lin_{ax}", True)
        setattr(c, f"limit_lin_{ax}_lower", 0.0)
        setattr(c, f"limit_lin_{ax}_upper", 0.0)
    c.use_limit_ang_x = True
    c.limit_ang_x_lower = 0.0
    c.limit_ang_x_upper = 0.0
    c.use_limit_ang_y = True
    c.limit_ang_y_lower = 0.0
    c.limit_ang_y_upper = 0.0
    c.use_spring_ang_z = True
    c.spring_stiffness_ang_z = float(k)
    # amortecimento ~ crítico; piso alto demais deixava a chapa mole "congelada"
    c.spring_damping_ang_z = max(1.0e-5, 0.12 * math.sqrt(max(float(k), 1e-12)))
    return empty


def add_fixed(name, a, b, location):
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.015
    empty.location = Vector(location)
    link(empty)
    activate(empty)
    bpy.ops.rigidbody.constraint_add(type="FIXED")
    c = empty.rigid_body_constraint
    c.object1 = a
    c.object2 = b
    c.disable_collisions = True
    return empty


def tilt_about(obj, pivot, theta):
    y = obj.location.y - pivot.y
    z = obj.location.z - pivot.z
    obj.location.y = pivot.y + y * math.cos(theta) - z * math.sin(theta)
    obj.location.z = pivot.z + y * math.sin(theta) + z * math.cos(theta)
    obj.rotation_euler.x += theta


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build(K):
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.gravity = (0.0, 0.0, -9.81)
    sc.render.fps = 30
    frames = 180
    sc.frame_start = 1
    sc.frame_end = frames
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rw = sc.rigidbody_world
    rw.substeps_per_frame = 25
    rw.solver_iterations = 50
    rw.point_cache.frame_start = 1
    rw.point_cache.frame_end = frames

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    mat_m = montana_material()
    mat_l = leather_material()
    mat_wood = simple_material("madeira", (0.28, 0.16, 0.08), 0.6)
    mat_brass = simple_material("latao", (0.78, 0.62, 0.28), 0.22, metal=1.0)
    mat_thread = simple_material("pesponto", (0.20, 0.10, 0.05), 0.7)
    mat_glass = simple_material("vidro", (0.75, 0.86, 0.84), 0.08, alpha=0.35)
    mat_bottle = simple_material("garrafa", (0.10, 0.22, 0.13), 0.15, alpha=0.55)
    mat_title = simple_material("titulo", (0.96, 0.94, 0.88), 0.5)

    theta = math.radians(D.IMPERFECTION_DEG)
    areal_m = D.MONTANA_RHO * D.MONTANA_T
    areal_l = D.LEATHER_RHO * D.LEATHER_T

    # mesa / chão
    table = box("mesa", 1.5, 1.1, 0.04)
    table.location = (0.0, 0.08, -0.02)
    assign(table, mat_wood)
    add_rigid(table, 5.0, kinematic=True, groups={0, 1, 2})

    # 3 mm de folga: o overlap da foto fazia o cilindro encostar e travar a 12°
    cyl_x = D.PANEL_W / 2 + D.CYL_R + 0.003
    base_w = 2 * (cyl_x + D.CYL_R) + 0.012
    base_d = D.CYL_OD + 0.014
    base = box("base_couro" if CASE == "caseB" else "base_montana", base_w, base_d, D.PLINTH_H)
    base.location = (0.0, base_d / 2 - 0.004, D.PLINTH_H / 2)
    assign(base, mat_l if CASE == "caseB" else mat_m)
    base_mass = (areal_l if CASE == "caseB" else areal_m) * base_w * base_d
    # plinto só colide com o berço; cilindro e alça não podem "subir" nele
    add_rigid(base, base_mass, kinematic=True, groups={1})

    # berço
    body = box("berco", D.BAY_W, D.BAY_D, D.CYL_H)
    body.location = (0.0, D.BAY_D / 2 + 0.002, D.PLINTH_H + D.CYL_H / 2)
    assign(body, mat_m)
    # paredes finas de verdade: o box acima é o volume do berço para colisão.
    # A casca visível é uma cópia só das faces, feita por solidificar um tubo retangular.
    shell = rectangular_shell("casca_berco", D.BAY_W, D.BAY_D, D.CYL_H, D.MONTANA_T)
    shell.parent = body
    shell.location = (0.0, 0.0, 0.0)
    shell.rotation_euler = (0.0, 0.0, 0.0)
    assign(shell, mat_m)
    # painel frontal inferior, mesma largura da alça, para a silhueta contínua
    lower = box("painel_inferior", D.PANEL_W, D.MONTANA_T, D.CYL_H)
    lower.parent = body
    lower.location = (0.0, -D.BAY_D / 2.0 - 0.001, 0.0)
    assign(lower, mat_m)
    body.display_type = "BOUNDS"
    body.hide_render = True

    wall_area = 2 * (D.BAY_W + D.BAY_D) * D.CYL_H * 0.65
    body_mass = areal_m * wall_area
    if CASE == "caseB":
        body_mass += 4 * areal_l * 0.016 * D.CYL_H

    front = rounded_panel(
        "painel_frontal",
        D.PANEL_W,
        D.HANDLE_H,
        D.MONTANA_T,
        D.TOP_RADIUS,
        slot=(D.SLOT_W, D.SLOT_H, D.SLOT_FROM_TOP),
    )
    front.location = (0.0, -0.001, D.PLINTH_H + D.CYL_H + D.HANDLE_H / 2)
    assign(front, mat_m)
    handle_mass = areal_m * D.PANEL_W * D.HANDLE_H
    if CASE == "caseB":
        handle_mass += 2 * areal_l * 0.090 * D.HANDLE_H

    # cilindros
    cylinders = []
    for sign, tag in ((-1, "esq"), (1, "dir")):
        cyl = open_cylinder(f"cilindro_{tag}", D.CYL_R, D.CYL_H)
        cyl.location = (sign * cyl_x, D.CYL_R, D.PLINTH_H + D.CYL_H / 2 + 0.003)
        assign(cyl, mat_m)
        # solidificar um pouco via escala não; a malha é a superfície. OK.
        cylinders.append(cyl)

    cyl_area = 2 * math.pi * D.CYL_R * D.CYL_H
    cyl_mass = areal_m * cyl_area
    if CASE == "caseB":
        cyl_mass += areal_l * (math.pi * D.CYL_R ** 2 + 2 * math.pi * D.CYL_R * 0.012)

    # garrafa e taças (visuais + massa)
    bottle = bottle_mesh()
    bottle.location = (0.0, D.BAY_D / 2 + 0.002, D.PLINTH_H + D.BOTTLE_H / 2)
    assign(bottle, mat_bottle)
    glasses = []
    for sign, tag in ((-1, "esq"), (1, "dir")):
        g = glass_mesh()
        g.location = (sign * cyl_x, D.CYL_R, D.PLINTH_H + 0.055)
        assign(g, mat_glass)
        glasses.append(g)

    # couro estrutural visível
    if CASE == "caseB":
        add_leather_bones(body, front, cylinders, mat_l, cyl_x)

    # pesponto no painel
    w, h, r = D.PANEL_W, D.HANDLE_H, D.TOP_RADIUS
    inset = 0.0035
    loop = panel_loop(w - 2 * inset, h - inset, r)
    st = stitches_along("pesponto_painel", loop, front)
    if st:
        assign(st, mat_thread)
    # snap
    bpy.ops.mesh.primitive_uv_sphere_add(radius=D.SNAP_D / 2, segments=16, ring_count=8)
    snap = bpy.context.active_object
    snap.name = "botao"
    snap.parent = front
    snap.location = (0.0, -D.MONTANA_T, h / 2 - D.SNAP_FROM_TOP)
    assign(snap, mat_brass)

    # dobradiça na borda da frente, para o tombo não cravar o fundo no chão
    pivot = Vector((0.0, body.location.y - D.BAY_D / 2.0, D.PLINTH_H))
    for ob in [body, front, bottle, *cylinders, *glasses]:
        tilt_about(ob, pivot, theta)

    add_rigid(body, body_mass, groups={1})
    add_rigid(front, handle_mass, groups={0})
    for cyl in cylinders:
        add_rigid(cyl, cyl_mass, groups={2})
    add_rigid(bottle, D.BOTTLE_MASS, groups={1})
    for g in glasses:
        add_rigid(g, D.GLASS_MASS, groups={2})

    bpy.context.view_layer.update()
    add_hinge("mola_berco", base, body, pivot, K["k_body"])
    hinge_h = front.matrix_world @ Vector((0.0, 0.0, -D.HANDLE_H / 2))
    add_hinge("mola_alca", body, front, hinge_h, K["k_handle"])
    for cyl, tag in zip(cylinders, ("esq", "dir")):
        foot = cyl.matrix_world @ Vector((0.0, -D.CYL_R, -D.CYL_H / 2))
        add_hinge(f"mola_cilindro_{tag}", base, cyl, foot, K["k_cyl"])
    add_fixed("fix_garrafa", body, bottle, bottle.location)
    for g, tag in zip(glasses, ("esq", "dir")):
        add_fixed(f"fix_taca_{tag}", cylinders[0 if tag == "esq" else 1], g, g.location)

    # câmera em órbita
    target = bpy.data.objects.new("alvo", None)
    target.location = (0.0, 0.04, 0.18)
    link(target)
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 48
    cam = bpy.data.objects.new("camera", cam_data)
    link(cam)
    sc.camera = cam
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    for f in range(1, frames + 1):
        ang = math.radians(-35 + 100 * (f - 1) / (frames - 1))
        radius = 0.78
        cam.location = (
            radius * math.sin(ang),
            -radius * math.cos(ang) + 0.04,
            0.30 + 0.04 * math.sin(ang * 0.5),
        )
        cam.keyframe_insert("location", frame=f)

    # título preso à câmera para permanecer na tela durante a órbita
    font = bpy.data.fonts.load("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    curve = bpy.data.curves.new("titulo", "FONT")
    curve.body = "Teste de física — montana perfurado + couro rígido"
    curve.font = font
    curve.size = 0.020
    curve.align_x = "CENTER"
    curve.extrude = 0.0004
    title = bpy.data.objects.new("titulo", curve)
    link(title)
    assign(title, mat_title)
    title.location = (0.0, -0.58, 0.018)
    title.rotation_euler = (math.radians(68), 0.0, math.radians(-28))

    sun_data = bpy.data.lights.new("sol", "SUN")
    sun_data.energy = 1.5
    sun_data.color = (1.0, 0.93, 0.82)
    sun = bpy.data.objects.new("sol", sun_data)
    sun.rotation_euler = (math.radians(48), math.radians(8), math.radians(30))
    link(sun)
    fill_data = bpy.data.lights.new("fill", "AREA")
    fill_data.energy = 35
    fill_data.size = 0.8
    fill_data.color = (0.85, 0.90, 1.0)
    fill = bpy.data.objects.new("fill", fill_data)
    fill.location = (-0.5, -0.4, 0.6)
    look_at(fill, (0, 0.05, 0.15))
    link(fill)

    world = sc.world or bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.16, 0.20, 0.14, 1)
        bg.inputs["Strength"].default_value = 0.22

    # marcador da coroa, filho do painel
    crown = bpy.data.objects.new("coroa", None)
    crown.empty_display_type = "SPHERE"
    crown.empty_display_size = 0.008
    crown.parent = front
    crown.location = (0.0, 0.0, D.HANDLE_H / 2)
    link(crown)

    # viewport em material para os furos aparecerem
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].shading.type = "MATERIAL"
                area.spaces[0].shading.use_scene_lights = True
                area.spaces[0].clip_end = 20

    return {
        "frames": frames,
        "front": front.name,
        "body": body.name,
        "cylinders": [c.name for c in cylinders],
        "crown": crown.name,
        "pivot_z": D.PLINTH_H,
    }


def rectangular_shell(name, w, d, h, t):
    """Casca aberta em cima, centrada."""
    bm = bmesh.new()
    hw, hd, hh = w / 2, d / 2, h / 2
    # quatro paredes externas
    loops = [
        [(-hw, -hd, -hh), (hw, -hd, -hh), (hw, -hd, hh), (-hw, -hd, hh)],
        [(hw, -hd, -hh), (hw, hd, -hh), (hw, hd, hh), (hw, -hd, hh)],
        [(hw, hd, -hh), (-hw, hd, -hh), (-hw, hd, hh), (hw, hd, hh)],
        [(-hw, hd, -hh), (-hw, -hd, -hh), (-hw, -hd, hh), (-hw, hd, hh)],
    ]
    for loop in loops:
        verts = [bm.verts.new(p) for p in loop]
        bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_mesh_object(name, bm)


def panel_loop(w, h, radius):
    pts = [(-w / 2, 0.0, -h / 2), (-w / 2, 0.0, h / 2 - radius)]
    cx, cz = -w / 2 + radius, h / 2 - radius
    for i in range(1, 7):
        a = math.pi - i * (math.pi / 2) / 6
        pts.append((cx + radius * math.cos(a), 0.0, cz + radius * math.sin(a)))
    cx, cz = w / 2 - radius, h / 2 - radius
    for i in range(0, 7):
        a = math.pi / 2 - i * (math.pi / 2) / 6
        pts.append((cx + radius * math.cos(a), 0.0, cz + radius * math.sin(a)))
    pts.append((w / 2, 0.0, -h / 2))
    pts.append(pts[0])
    return pts


def add_leather_bones(body, front, cylinders, mat_l, cyl_x):
    # nervuras nos cantos do berço, no espaço local do berço
    hw, hd, hh = D.BAY_W / 2, D.BAY_D / 2, D.CYL_H / 2
    rib_w, rib_t = 0.016, D.LEATHER_T
    corners = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    for i, (sx, sy) in enumerate(corners):
        rib = box(f"nervura_{i}", rib_w, rib_t, D.CYL_H * 0.98)
        rib.parent = body
        rib.location = (sx * (hw - rib_w / 2), sy * (hd - rib_t / 2), 0.0)
        assign(rib, mat_l)
    # canal de couro atrás do painel: duas paredes com 12 mm entre eixos
    for i, yoff in enumerate((0.002, 0.014)):
        wall = box(f"canal_alca_{i}", 0.090, D.LEATHER_T, D.HANDLE_H * 0.94)
        wall.parent = front
        wall.location = (0.0, yoff, -0.002)
        assign(wall, mat_l)
    # fechamento superior e inferior do canal
    for i, zoff in enumerate((D.HANDLE_H * 0.42, -D.HANDLE_H * 0.42)):
        cap = box(f"canal_tampa_{i}", 0.090, 0.014, D.LEATHER_T)
        cap.parent = front
        cap.location = (0.0, 0.008, zoff)
        assign(cap, mat_l)
    # debrum só na borda, sem tampar o painel furado nem a fenda
    for name, loc, scale in (
        ("debrum_esq", (-D.PANEL_W / 2, 0.0, 0.0), (D.LEATHER_T, 0.006, D.HANDLE_H)),
        ("debrum_dir", (D.PANEL_W / 2, 0.0, 0.0), (D.LEATHER_T, 0.006, D.HANDLE_H)),
    ):
        bind = box(name, *scale)
        bind.parent = front
        bind.location = loc
        assign(bind, mat_l)
    for cyl in cylinders:
        band = ring_band("aro_" + cyl.name, D.CYL_R + 0.001, 0.012, D.LEATHER_T)
        band.parent = cyl
        band.location = (0.0, 0.0, D.CYL_H / 2 - 0.008)
        assign(band, mat_l)
        floor = disc("piso_" + cyl.name, D.CYL_R - 0.001, -D.CYL_H / 2 + 0.001)
        floor.parent = cyl
        assign(floor, mat_l)
        for j, ang in enumerate((0.0, math.pi)):
            ribc = box(f"nervura_cil_{cyl.name}_{j}", 0.010, D.LEATHER_T, D.CYL_H * 0.92)
            ribc.parent = cyl
            ribc.location = ((D.CYL_R - 0.004) * math.cos(ang), (D.CYL_R - 0.004) * math.sin(ang), 0.0)
            assign(ribc, mat_l)


def bottle_mesh():
    bm = bmesh.new()
    # corpo + gargalo, origem no centro do volume aproximado (metade da altura total)
    H, R = D.BOTTLE_H, D.BOTTLE_D / 2
    # construir ao longo de Z a partir de -H/2
    rings_z = [
        (-H / 2, R),
        (-H / 2 + 0.20, R),
        (-H / 2 + 0.24, R * 0.55),
        (-H / 2 + 0.28, R * 0.42),
        (H / 2, R * 0.42),
    ]
    n = 20
    rings = []
    for z, r in rings_z:
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    c = bm.verts.new((0, 0, -H / 2))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((c, rings[0][j], rings[0][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_mesh_object("garrafa", bm)


def glass_mesh():
    bm = bmesh.new()
    # taça simplificada: bojo + haste, altura GLASS_H, origem no centro
    H = D.GLASS_H
    n = 16
    profile = [
        (-H / 2, 0.012),
        (-H / 2 + 0.045, 0.004),
        (-H / 2 + 0.055, 0.004),
        (-H / 2 + 0.07, D.GLASS_D / 2),
        (H / 2, D.GLASS_D / 2 * 0.92),
    ]
    rings = []
    for z, r in profile:
        ring = []
        for i in range(n):
            a = 2 * math.pi * i / n
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), z)))
        rings.append(ring)
    for ra, rb in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((ra[i], ra[j], rb[j], rb[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_mesh_object("taca", bm)


def angle_from_vertical(obj):
    zax = obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
    if zax.length == 0:
        return 0.0
    zax.normalize()
    return math.degrees(math.atan2(math.hypot(zax.x, zax.y), zax.z))


def measure(names):
    sc = bpy.context.scene
    front = bpy.data.objects[names["front"]]
    crown = bpy.data.objects[names["crown"]]
    cyls = [bpy.data.objects[n] for n in names["cylinders"]]
    frames = [1, 20, 40, 60, 90, 120, names["frames"]]
    rows = []
    for f in frames:
        sc.frame_set(f)
        z = crown.matrix_world.translation.z
        rows.append(
            {
                "frame": f,
                "tilt_handle_deg": round(angle_from_vertical(front), 3),
                "crown_z_m": round(z, 5),
                "tilt_cyl_deg": [round(angle_from_vertical(c), 3) for c in cyls],
            }
        )
    z0 = rows[0]["crown_z_m"]
    z1 = rows[-1]["crown_z_m"]
    loss = (z0 - z1) / z0 if z0 else 0.0
    tilt = abs(rows[-1]["tilt_handle_deg"])
    cyl_tilt = max(abs(a) for a in rows[-1]["tilt_cyl_deg"])
    passed = tilt < 8.0 and loss < 0.08 and cyl_tilt < 8.0
    return {
        "case": CASE,
        "samples": rows,
        "tilt_deg": tilt,
        "cyl_tilt_deg": cyl_tilt,
        "height_initial_m": z0,
        "height_final_m": z1,
        "height_loss": loss,
        "pass": passed,
        "criteria": "tilt < 8° e perda de altura < 8% e cilindros < 8°, no último quadro",
    }


def render_still(path, frame):
    sc = bpy.context.scene
    sc.frame_set(frame)
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 800
    sc.render.resolution_percentage = 100
    sc.eevee.taa_render_samples = 24
    sc.render.filepath = str(path)
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)


def run():
    try:
        prefs = bpy.context.preferences.view
        if hasattr(prefs, "show_splash"):
            prefs.show_splash = False
        K = stiffness()
        names = build(K)
        sc = bpy.context.scene
        rw = sc.rigidbody_world
        win = bpy.context.window_manager.windows[0]
        area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
        region = next(r for r in area.regions if r.type == "WINDOW")
        area.spaces[0].shading.type = "MATERIAL"
        with bpy.context.temp_override(
            window=win, screen=win.screen, area=area, region=region,
            scene=sc, point_cache=rw.point_cache,
        ):
            bpy.ops.ptcache.free_bake()
            op = bpy.ops.ptcache.bake(bake=True)
        result = measure(names)
        result["stiffness"] = K
        result["bake_op"] = str(op)
        out = ROOT / f"resultado_{CASE}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        blend = ROOT / f"{CASE}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        cam = sc.camera
        if cam.animation_data:
            cam.animation_data_clear()
        cam.constraints.clear()

        def shoot(path, frame, loc, tgt):
            sc.frame_set(frame)
            cam.location = loc
            look_at(cam, tgt)
            render_still(path, frame)

        shoot(ART / f"{CASE}-inicio.png", 1, (0.42, -0.62, 0.32), (0.0, 0.04, 0.18))
        shoot(ART / f"{CASE}-fim.png", names["frames"], (0.42, -0.62, 0.32), (0.0, 0.04, 0.16))
        if CASE == "caseB":
            shoot(ART / "caseB-furos-alca.png", names["frames"], (0.12, -0.20, 0.32), (0.0, 0.0, 0.30))
            shoot(ART / "caseB-ossos.png", names["frames"], (0.38, 0.10, 0.16), (0.0, 0.04, 0.12))
        line = (
            f"{CASE} tilt={result['tilt_deg']:.2f}° "
            f"perda={result['height_loss']*100:.2f}% "
            f"cilindro={result['cyl_tilt_deg']:.2f}° "
            f"pass={result['pass']}\n"
        )
        with (ROOT / "sim_log.txt").open("a") as fh:
            fh.write(line)
        print(line, flush=True)
        bpy.ops.wm.quit_blender()
    except Exception:
        (ROOT / "sim_error.txt").write_text(traceback.format_exc())
        print(traceback.format_exc(), flush=True)
        bpy.ops.wm.quit_blender()
    return None


# limpa log do caso nesta execução
if CASE in ("caseA", "caseB"):
    bpy.app.timers.register(run, first_interval=0.6)

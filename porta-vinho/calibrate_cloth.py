"""Calibrate Blender cloth bending stiffness against beam theory.

Estimates, not lab data. Target flexural rigidity:

    D = E t^3 / (12 (1-nu^2))
    EI = E b t^3 / 12

Cantilever, uniform self-weight, small deflection:

    delta = w L^4 / (8 E I)

Mesh edge length matches the bag (8 mm) so the fitted bending
parameter transfers.
"""
import math
import json
import sys

import bpy

EDGE = 0.008  # m


def clear():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.gravity = (0.0, 0.0, -9.81)
    sc.render.fps = 30
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


def make_cantilever(length, width, areal_kg_m2, bend, tension=400.0):
    clear()
    nx = max(2, int(round(length / EDGE)))
    ny = max(1, int(round(width / EDGE)))
    # build grid in XY, length along X
    mesh = bpy.data.meshes.new("beam")
    obj = bpy.data.objects.new("beam", mesh)
    bpy.context.scene.collection.objects.link(obj)
    verts = []
    for j in range(ny + 1):
        for i in range(nx + 1):
            verts.append((i * length / nx, j * width / ny, 0.0))
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + 1 + (nx + 1), a + (nx + 1)))
    mesh.from_pydata(verts, [], faces)
    mesh.update()

    vg = obj.vertex_groups.new(name="pin")
    root = [v.index for v in mesh.vertices if v.co.x < 1e-6]
    vg.add(root, 1.0, "REPLACE")

    area = length * width
    total_mass = areal_kg_m2 * area
    n = len(mesh.vertices)
    mod = obj.modifiers.new("Cloth", "CLOTH")
    cs = mod.settings
    cs.mass = total_mass / n
    cs.air_damping = 0.8
    cs.quality = 16
    cs.time_scale = 1.0
    cs.tension_stiffness = tension
    cs.compression_stiffness = tension
    cs.shear_stiffness = tension * 0.4
    cs.bending_stiffness = bend
    cs.bending_model = "ANGULAR"
    cs.bending_damping = 1.0
    cs.tension_damping = 2.0
    cs.compression_damping = 2.0
    cs.shear_damping = 2.0
    cs.pin_stiffness = 1.0
    cs.vertex_group_mass = "pin"
    col = mod.collision_settings
    col.use_collision = False
    col.use_self_collision = False
    cache = mod.point_cache
    cache.frame_start = 1
    cache.frame_end = 120
    bpy.context.scene.frame_end = 120
    return obj, nx


def simulate(obj, length, nframes=120):
    scene = bpy.context.scene
    scene.frame_set(1)
    samples = {}
    for f in range(1, nframes + 1):
        scene.frame_set(f)
        if f in (30, 60, 90, nframes) or f == nframes:
            deps = bpy.context.evaluated_depsgraph_get()
            ev = obj.evaluated_get(deps)
            zs = [v.co.z for v in ev.data.vertices if v.co.x > length - EDGE * 0.75]
            samples[f] = (sum(zs) / len(zs) if zs else None, len(zs))
    return samples


def run_case(name, length, width, areal, e_pa, t_m, bends):
    nu = 0.40
    I = width * (t_m ** 3) / 12.0
    EI = e_pa * I
    w = areal * width * 9.81
    delta = w * (length ** 4) / (8.0 * EI)
    D = e_pa * (t_m ** 3) / (12.0 * (1.0 - nu * nu))
    print(f"\n== {name} L={length:.3f} target delta={delta*1000:.2f} mm  EI={EI:.6e} D={D:.6e}")
    results = []
    for b in bends:
        obj, nx = make_cantilever(length, width, areal, b)
        samples = simulate(obj, length)
        z = samples[120][0]
        zmm = None if z is None else z * 1000.0
        print(
            f"  bend={b:10.4g}  samples_mm="
            + " ".join(
                f"f{fr}:{'nan' if samples[fr][0] is None else f'{samples[fr][0]*1000:.2f}'}"
                for fr in samples
            )
            + f"  target={-delta*1000:.2f}",
            flush=True,
        )
        results.append({"bend": b, "tip_mm": zmm, "samples_mm": {
            str(fr): (None if samples[fr][0] is None else samples[fr][0] * 1000.0)
            for fr in samples
        }})
    return {
        "name": name,
        "length_m": length,
        "width_m": width,
        "areal_kg_m2": areal,
        "E_Pa": e_pa,
        "t_m": t_m,
        "EI": EI,
        "D_Nm": D,
        "target_delta_mm": -delta * 1000.0,
        "trials": results,
    }


def main():
    montana_bends = [0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
    leather_bends = [0.01, 0.1, 1.0, 10.0, 50.0, 200.0, 1000.0]
    out = {
        "note": "Estimates mapped into Blender cloth angular bending. Not lab data.",
        "edge_m": EDGE,
        "formula": "delta = w L^4 / (8 EI), EI = E b t^3 / 12",
        "montana": run_case(
            "montana",
            length=0.064,
            width=0.024,
            areal=900 * 0.0011,
            e_pa=30e6,
            t_m=0.0011,
            bends=montana_bends,
        ),
        "leather": run_case(
            "leather",
            length=0.200,
            width=0.024,
            areal=950 * 0.0022,
            e_pa=250e6,
            t_m=0.0022,
            bends=leather_bends,
        ),
    }
    path = "/workspace/porta-vinho/calibration.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("WROTE", path)


if __name__ == "__main__":
    main()

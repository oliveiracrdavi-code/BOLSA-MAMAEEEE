"""Reenquadra os stills sem rebaker a física."""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ART = Path("/opt/cursor/artifacts")
CASE = "caseB"
if "--" in sys.argv:
    args = sys.argv[sys.argv.index("--") + 1 :]
    if args:
        CASE = args[0]


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def shoot(sc, cam, path, frame, loc, tgt):
    sc.frame_set(frame)
    cam.location = loc
    look_at(cam, tgt)
    bpy.context.view_layer.update()
    title = bpy.data.objects.get("titulo")
    if title:
        title.parent = None
        mw = cam.matrix_world.copy()
        mw.translation = cam.matrix_world @ Vector((0.0, 0.12, -0.62))
        title.matrix_world = mw
        title.data.size = 0.0105
        if title.data.materials:
            mat = title.data.materials[0]
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf and "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Base Color"].default_value = (1, 0.96, 0.82, 1)
                bsdf.inputs["Emission Color"].default_value = (1, 0.96, 0.82, 1)
                bsdf.inputs["Emission Strength"].default_value = 2.0
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("WROTE", path, flush=True)


def run():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1280
    sc.render.resolution_y = 800
    sc.eevee.taa_render_samples = 16
    sc.render.image_settings.file_format = "PNG"
    cam = sc.camera
    if cam.animation_data:
        cam.animation_data_clear()
    for c in list(cam.constraints):
        cam.constraints.remove(c)
    deb = bpy.data.objects.get("debrum")
    if deb:
        bpy.data.objects.remove(deb, do_unlink=True)
    title = bpy.data.objects.get("titulo")
    end = sc.frame_end
    front = (0.62, -0.95, 0.46)
    tgt = (0.0, 0.04, 0.22)
    shoot(sc, cam, ART / f"{CASE}-inicio.png", 1, front, tgt)
    shoot(sc, cam, ART / f"{CASE}-fim.png", end, front, tgt)
    if CASE == "caseB":
        shoot(sc, cam, ART / "caseB-furos-alca.png", end, (0.22, -0.28, 0.34), (0.0, 0.0, 0.32))
        shoot(sc, cam, ART / "caseB-ossos.png", end, (0.28, -0.05, 0.18), (-0.02, 0.05, 0.14))
    bpy.ops.wm.save_mainfile()
    print("DONE", CASE, flush=True)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=0.8)

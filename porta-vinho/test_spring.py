"""SPRING2 hinge, COM away from the pivot. Compare to rigid-bar equilibrium."""
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else ["0.05", "8"]
K = float(argv[0])
TH0_DEG = float(argv[1])


def run():
    L = 0.20
    mass = 0.10
    frames = 160
    sc = bpy.context.scene
    sc.gravity = (0.0, 0.0, -9.81)
    sc.render.fps = 30
    sc.frame_start = 1
    sc.frame_end = frames
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rw = sc.rigidbody_world
    rw.substeps_per_frame = 20
    rw.solver_iterations = 40
    rw.point_cache.frame_start = 1
    rw.point_cache.frame_end = frames

    bpy.ops.mesh.primitive_cube_add(size=0.06, location=(0, 0, -0.04))
    base = bpy.context.active_object
    base.name = "base"
    bpy.ops.rigidbody.object_add()
    base.rigid_body.type = "PASSIVE"
    base.rigid_body.kinematic = True

    th0 = math.radians(TH0_DEG)
    # origin at the COM; bottom edge sits on the hinge after the tilt
    oy = -(L / 2.0) * math.sin(th0)
    oz = (L / 2.0) * math.cos(th0)
    import bmesh
    mesh = bpy.data.meshes.new("beam")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 0.02
        v.co.y *= 0.004
        v.co.z *= L / 2.0
    bm.to_mesh(mesh)
    bm.free()
    beam = bpy.data.objects.new("beam", mesh)
    beam.location = (0.0, oy, oz)
    beam.rotation_euler = (th0, 0.0, 0.0)
    bpy.context.collection.objects.link(beam)
    bpy.context.view_layer.objects.active = beam
    beam.select_set(True)
    bpy.ops.rigidbody.object_add()
    beam.rigid_body.type = "ACTIVE"
    beam.rigid_body.mass = mass
    beam.rigid_body.collision_shape = "CONVEX_HULL"
    beam.rigid_body.use_deactivation = False
    beam.rigid_body.linear_damping = 0.1
    beam.rigid_body.angular_damping = 0.2

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    empty = bpy.context.active_object
    empty.rotation_euler = (0.0, math.radians(90.0), 0.0)  # local Z = world X
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = empty
    if K <= 0:
        bpy.ops.rigidbody.constraint_add(type="HINGE")
        c = empty.rigid_body_constraint
        c.object1 = base
        c.object2 = beam
        c.disable_collisions = True
    else:
        bpy.ops.rigidbody.constraint_add(type="GENERIC_SPRING")
        c = empty.rigid_body_constraint
        c.object1 = base
        c.object2 = beam
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
        c.spring_stiffness_ang_z = K
        c.spring_damping_ang_z = max(0.02, 0.25 * math.sqrt(max(K, 1e-6)))

    pre = beam.matrix_world.translation
    open("/workspace/porta-vinho/spring_test.log", "a").write(
        f"PRE k={K} loc=({pre.x:.4f},{pre.y:.4f},{pre.z:.4f}) rot={tuple(round(math.degrees(a),2) for a in beam.rotation_euler)}\n"
    )
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=sc, point_cache=rw.point_cache):
        bpy.ops.ptcache.free_bake()
        op = bpy.ops.ptcache.bake(bake=True)

    def ang():
        # angle from vertical of the vector from pivot (0,0,0) to beam origin (COM)
        p = beam.matrix_world.translation
        return math.degrees(math.atan2(math.hypot(p.x, p.y), p.z)), p

    hist = []
    for f in (1, 20, 40, 80, 120, frames):
        sc.frame_set(f)
        a, p = ang()
        hist.append((f, round(a, 2), round(p.z, 4)))

    mgL2 = mass * 9.81 * (L / 2.0)

    def fth(th):
        return K * (th - th0) - mgL2 * math.sin(th)

    lo, hi = th0, math.pi * 0.999
    pred = None
    if fth(lo) == 0:
        pred = TH0_DEG
    elif fth(lo) * fth(hi) < 0:
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            if fth(lo) * fth(mid) <= 0:
                hi = mid
            else:
                lo = mid
        pred = round(math.degrees(0.5 * (lo + hi)), 2)
    elif fth(th0) < 0 and fth(hi) < 0:
        # spring cannot hold any angle: falls past the search bracket
        pred = "collapsed"

    line = f"RESULT k={K} theta0={TH0_DEG} hist={hist} analytic={pred} op={op}\n"
    open("/workspace/porta-vinho/spring_test.log", "a").write(line)
    print(line, flush=True)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(run, first_interval=0.5)

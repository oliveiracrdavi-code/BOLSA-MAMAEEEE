#!/usr/bin/env python3
"""Gera o modelo 3D, o ensaio de rigidez e o PDF de moldes do porta-vinho."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from fpdf import FPDF
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figuras"
OUT = ROOT / "saida"
FIG.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# Medidas acabadas, em milímetros. O Montana fica por fora; o couro é a casca.
FACE = 106.0          # largura externa da frente
DEPTH = 106.0         # profundidade externa do corpo
BOX_H = 318.0         # altura do corpo da garrafa
HANDLE_H = 142.0      # alça acima do corpo
TOTAL_H = BOX_H + HANDLE_H
CUP_H = 180.0
CUP_ID = 94.0         # diâmetro interno do copo
LEATHER_PANEL = 2.8  # mm
LEATHER_CUP = 2.2
LEATHER_BASE = 3.2
MONTANA = 1.0
SA = 8.0
CUP_OD = CUP_ID + 2 * LEATHER_CUP + 2 * MONTANA
WALL = LEATHER_PANEL + MONTANA
INNER_W = FACE - 2 * WALL
INNER_D = DEPTH - 2 * WALL
INNER_H = BOX_H - LEATHER_BASE - MONTANA
WIN_W, WIN_H = 58.0, 34.0
WIN_TOP = 66.0
SNAP_FROM_TOP = 18.0
TOP_R = FACE / 2

# Módulos usados no ensaio. São valores de projeto, não um laudo de laboratório
# do rolo específico da cliente. A conclusão não muda dentro da faixa testada.
E_LEATHER = 180e6     # Pa, vaqueta firme
E_MONTANA = 8e6       # Pa, efetivo do furadinho em flexão
NU_L = 0.35
RHO_L = 900.0
RHO_M = 750.0
G = 9.81


def beam2d_stiffness(E, A, I, L):
    k = np.zeros((6, 6))
    ea, ei = E * A, E * I
    k[0, 0] = k[3, 3] = ea / L
    k[0, 3] = k[3, 0] = -ea / L
    k[1, 1] = k[4, 4] = 12 * ei / L**3
    k[1, 4] = k[4, 1] = -12 * ei / L**3
    k[1, 2] = k[2, 1] = 6 * ei / L**2
    k[1, 5] = k[5, 1] = 6 * ei / L**2
    k[4, 2] = k[2, 4] = -6 * ei / L**2
    k[4, 5] = k[5, 4] = -6 * ei / L**2
    k[2, 2] = k[5, 5] = 4 * ei / L
    k[2, 5] = k[5, 2] = 2 * ei / L
    return k


def transform(k, c, s):
    T = np.zeros((6, 6))
    R = np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])
    T[0:3, 0:3] = R
    T[3:6, 3:6] = R
    return T.T @ k @ T


def ring_test(E, t, width, radius, load, n=32):
    """Fecha o diâmetro de um anel sob duas forças opostas. Valida contra Roark."""
    area = width * t
    inertia = width * t**3 / 12.0
    theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
    xy = np.stack([radius * np.cos(theta), radius * np.sin(theta)], axis=1)
    ndof = n * 3
    K = np.zeros((ndof, ndof))
    for i in range(n):
        j = (i + 1) % n
        dx, dy = xy[j] - xy[i]
        length = float(np.hypot(dx, dy))
        k = transform(beam2d_stiffness(E, area, inertia, length), dx / length, dy / length)
        dofs = [i * 3, i * 3 + 1, i * 3 + 2, j * 3, j * 3 + 1, j * 3 + 2]
        for a in range(6):
            for b in range(6):
                K[dofs[a], dofs[b]] += k[a, b]
    force = np.zeros(ndof)
    right, left, top = 0, n // 2, n // 4
    force[right * 3] = -load
    force[left * 3] = load
    fixed = {right * 3 + 1, right * 3 + 2, top * 3}
    free = [i for i in range(ndof) if i not in fixed]
    disp = np.zeros(ndof)
    disp[free] = np.linalg.solve(K[np.ix_(free, free)], force[free])
    closure = -disp[right * 3] + disp[left * 3]
    formula = (np.pi / 4 - 2 / np.pi) * load * radius**3 / (E * inertia)
    xy_def = xy.copy()
    xy_def[:, 0] += disp[0::3]
    xy_def[:, 1] += disp[1::3]
    return {
        "closure_mm": closure * 1000,
        "formula_mm": formula * 1000,
        "ratio": closure / formula,
        "xy": xy,
        "xy_def": xy_def,
    }


def finger_defl_mm(E, t_mm, width_mm, span_mm, load_n):
    """Flecha no meio de uma faixa engastada nas duas bordas verticais."""
    t, width, span = t_mm / 1000, width_mm / 1000, span_mm / 1000
    inertia = width * t**3 / 12.0
    return load_n * span**3 / (192.0 * E * inertia) * 1000.0


def tip_metrics(mass_kg, com_z_mm, half_depth_mm, half_width_mm, push_height_mm):
    weight = mass_kg * G
    angle_depth = np.degrees(np.arctan(half_depth_mm / com_z_mm))
    angle_width = np.degrees(np.arctan(half_width_mm / com_z_mm))
    force_depth = weight * (half_depth_mm / 1000) / (push_height_mm / 1000)
    force_width = weight * (half_width_mm / 1000) / (push_height_mm / 1000)
    return angle_depth, angle_width, force_depth, force_width


def run_physics():
    radius = (CUP_ID / 2 + LEATHER_CUP / 2) / 1000
    leather_cup = ring_test(E_LEATHER, LEATHER_CUP / 1000, CUP_H / 1000, radius, 3.0)
    montana_cup = ring_test(E_MONTANA, MONTANA / 1000, CUP_H / 1000, radius, 3.0)
    leather_hoop = ring_test(E_LEATHER, LEATHER_PANEL / 1000, 0.014, radius, 3.0)

    span = INNER_W
    finger = {
        "montana_painel": finger_defl_mm(E_MONTANA, MONTANA, 30, span, 2.0),
        "couro_painel": finger_defl_mm(E_LEATHER, LEATHER_PANEL, 30, span, 2.0),
        "montana_vao_50": finger_defl_mm(E_MONTANA, MONTANA, 30, 50, 2.0),
        "montana_vao_30": finger_defl_mm(E_MONTANA, MONTANA, 30, 30, 2.0),
        "montana_vao_20": finger_defl_mm(E_MONTANA, MONTANA, 30, 20, 2.0),
    }
    sens = []
    for modulus in (8e6, 20e6, 40e6):
        sens.append(
            {
                "E_MPa": modulus / 1e6,
                "dedo_mm": finger_defl_mm(modulus, MONTANA, 30, span, 2.0),
                "copo_mm": ring_test(modulus, MONTANA / 1000, CUP_H / 1000, radius, 3.0)["closure_mm"],
            }
        )

    area_leather = (
        2 * (FACE / 1000) * (TOTAL_H / 1000)
        + 2 * (DEPTH / 1000) * (BOX_H / 1000)
        + (FACE / 1000) * (DEPTH / 1000)
        + 2 * np.pi * (CUP_OD / 2000) * (CUP_H / 1000)
        + 2 * np.pi * (CUP_ID / 2000) ** 2
    )
    mass_bag = area_leather * (LEATHER_PANEL / 1000) * RHO_L + area_leather * (MONTANA / 1000) * RHO_M
    mass_bottle, mass_glass = 1.25, 0.28
    mass_loaded = mass_bag + mass_bottle + 2 * mass_glass
    com_loaded = (
        mass_bag * 150 + mass_bottle * 155 + 2 * mass_glass * 90
    ) / mass_loaded
    half_depth = DEPTH / 2
    half_width = FACE / 2 + CUP_OD
    tip_empty = tip_metrics(mass_bag, 155, half_depth, half_width, TOTAL_H - 20)
    tip_loaded = tip_metrics(mass_loaded, com_loaded, half_depth, half_width, TOTAL_H - 20)

    side_leather = (FACE - WIN_W) / 2
    area_window = 2 * (side_leather / 1000) * (LEATHER_PANEL / 1000)
    lift = mass_loaded * G
    stress_leather = lift / area_window / 1e6
    area_mont = 2 * (side_leather / 1000) * (MONTANA / 1000)
    stress_mont = lift / area_mont / 1e6

    return {
        "leather_cup": {k: leather_cup[k] for k in ("closure_mm", "formula_mm", "ratio")},
        "montana_cup": {k: montana_cup[k] for k in ("closure_mm", "formula_mm", "ratio")},
        "leather_hoop": {k: leather_hoop[k] for k in ("closure_mm", "formula_mm", "ratio")},
        "finger": finger,
        "sensitivity": sens,
        "mass_bag_kg": mass_bag,
        "mass_loaded_kg": mass_loaded,
        "com_loaded_mm": com_loaded,
        "tip_empty": tip_empty,
        "tip_loaded": tip_loaded,
        "lift_n": lift,
        "stress_leather_mpa": stress_leather,
        "stress_montana_mpa": stress_mont,
        "rings": {
            "leather": (leather_cup["xy"], leather_cup["xy_def"]),
            "montana": (montana_cup["xy"], montana_cup["xy_def"]),
        },
        "inner_w": INNER_W,
        "inner_d": INNER_D,
        "inner_h": INNER_H,
        "cup_od": CUP_OD,
    }


def save_views(phys):
    mustard = "#C4842A"
    edge = "#6A3E12"
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 4.4))

    ax = axes[0]
    ax.set_title("Frente")
    ax.add_patch(Rectangle((-FACE / 2, 0), FACE, BOX_H, fc=mustard, ec=edge, lw=1.2))
    ax.add_patch(Rectangle((-FACE / 2, BOX_H), FACE, HANDLE_H - TOP_R, fc=mustard, ec=edge, lw=1.2))
    cap = plt.matplotlib.patches.Wedge(
        (0, TOTAL_H - TOP_R), TOP_R, 0, 180, fc=mustard, ec=edge, lw=1.2
    )
    ax.add_patch(cap)
    for sign in (-1, 1):
        cx = sign * (FACE / 2 + CUP_OD / 2)
        ax.add_patch(Rectangle((cx - CUP_OD / 2, 0), CUP_OD, CUP_H, fc="#D39A45", ec=edge, lw=1.2))
    ax.add_patch(Rectangle((-WIN_W / 2, TOTAL_H - WIN_TOP - WIN_H), WIN_W, WIN_H, fc="#1c1c1c", ec=edge))
    ax.scatter([0], [TOTAL_H - SNAP_FROM_TOP], s=28, c="#8A6A32", zorder=5)
    ax.annotate("", xy=(FACE / 2 + CUP_OD + 8, 0), xytext=(FACE / 2 + CUP_OD + 8, TOTAL_H),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(FACE / 2 + CUP_OD + 12, TOTAL_H / 2, f"{TOTAL_H:.0f}", va="center", fontsize=8)
    ax.annotate("", xy=(-FACE / 2 - CUP_OD, -12), xytext=(FACE / 2 + CUP_OD, -12),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(0, -28, f"{FACE + 2 * CUP_OD:.0f}", ha="center", fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(-190, 230)
    ax.set_ylim(-45, 490)
    ax.axis("off")

    ax = axes[1]
    ax.set_title("Lado")
    ax.add_patch(Rectangle((-DEPTH / 2, 0), DEPTH, BOX_H, fc=mustard, ec=edge, lw=1.2))
    # A alça é a frente que continua para cima, com as duas placas costuradas.
    ax.add_patch(Rectangle((DEPTH / 2 - 12, BOX_H), 12, HANDLE_H - TOP_R, fc=mustard, ec=edge, lw=1.2))
    ax.add_patch(plt.matplotlib.patches.Wedge((DEPTH / 2 - 6, TOTAL_H - TOP_R), 6, 0, 180, fc=mustard, ec=edge, lw=1.0))
    ax.add_patch(Rectangle((-CUP_OD / 2, 0), CUP_OD, CUP_H, fc="#D39A45", ec=edge, lw=1.0, alpha=0.35))
    ax.annotate("", xy=(DEPTH / 2 + 18, 0), xytext=(DEPTH / 2 + 18, BOX_H),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(DEPTH / 2 + 22, BOX_H / 2, f"{BOX_H:.0f}", fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(-90, 120)
    ax.set_ylim(-10, 490)
    ax.axis("off")

    ax = axes[2]
    ax.set_title("Topo")
    ax.add_patch(Rectangle((-FACE / 2, -DEPTH / 2), FACE, DEPTH, fc=mustard, ec=edge, lw=1.2))
    for sign in (-1, 1):
        ax.add_patch(Circle((sign * (FACE / 2 + CUP_OD / 2), 0), CUP_OD / 2, fc="#D39A45", ec=edge, lw=1.2))
    ax.annotate("", xy=(-DEPTH / 2 - 8, -DEPTH / 2), xytext=(-DEPTH / 2 - 8, DEPTH / 2),
                arrowprops=dict(arrowstyle="<->", color="#222"))
    ax.text(-DEPTH / 2 - 28, 0, f"{DEPTH:.0f}", ha="center", va="center", fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.axis("off")

    fig.suptitle("Medidas acabadas, em milímetros", fontsize=12)
    fig.tight_layout()
    path = FIG / "vistas.png"
    fig.savefig(path, dpi=140)
    plt.close()
    return path


def _quads_box(x0, y0, z0, x1, y1, z1):
    return [
        [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
        [(x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1)],
        [(x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0)],
        [(x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (x0, y1, z0)],
        [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)],
    ]


def _face_with_window(x0, x1, y, z0, z1, xw0, xw1, zw0, zw1):
    """Face em y constante, com um furo retangular passante na alça."""
    frame = [
        [(x0, y, z0), (x1, y, z0), (x1, y, zw0), (x0, y, zw0)],
        [(x0, y, zw1), (x1, y, zw1), (x1, y, z1), (x0, y, z1)],
        [(x0, y, zw0), (xw0, y, zw0), (xw0, y, zw1), (x0, y, zw1)],
        [(xw1, y, zw0), (x1, y, zw0), (x1, y, zw1), (xw1, y, zw1)],
    ]
    return frame


def bag_parts():
    """Malha rígida nas medidas do molde. A alça é a frente, larga, com topo arredondado e janela."""
    thick = 8.0
    y_front = DEPTH / 2
    y_back = y_front - thick
    body = _quads_box(-FACE / 2, -DEPTH / 2, 0, FACE / 2, DEPTH / 2, BOX_H)
    # O tampo do corpo fica livre para a garrafa; a faixa da frente é a base da alça.
    body[1] = [
        (-FACE / 2, -DEPTH / 2, BOX_H),
        (-FACE / 2, y_back, BOX_H),
        (FACE / 2, y_back, BOX_H),
        (FACE / 2, -DEPTH / 2, BOX_H),
    ]
    z_rect = TOTAL_H - TOP_R
    x0, x1 = -FACE / 2, FACE / 2
    xw0, xw1 = -WIN_W / 2, WIN_W / 2
    zw1 = TOTAL_H - WIN_TOP
    zw0 = zw1 - WIN_H
    handle = []
    handle += _face_with_window(x0, x1, y_front, BOX_H, z_rect, xw0, xw1, zw0, zw1)
    handle += _face_with_window(x0, x1, y_back, BOX_H, z_rect, xw0, xw1, zw0, zw1)
    # paredes do furo
    handle += [
        [(xw0, y_back, zw0), (xw1, y_back, zw0), (xw1, y_front, zw0), (xw0, y_front, zw0)],
        [(xw0, y_front, zw1), (xw1, y_front, zw1), (xw1, y_back, zw1), (xw0, y_back, zw1)],
        [(xw0, y_back, zw0), (xw0, y_front, zw0), (xw0, y_front, zw1), (xw0, y_back, zw1)],
        [(xw1, y_front, zw0), (xw1, y_back, zw0), (xw1, y_back, zw1), (xw1, y_front, zw1)],
    ]
    # laterais e base da placa da alça
    handle += [
        [(x0, y_back, BOX_H), (x0, y_front, BOX_H), (x0, y_front, z_rect), (x0, y_back, z_rect)],
        [(x1, y_front, BOX_H), (x1, y_back, BOX_H), (x1, y_back, z_rect), (x1, y_front, z_rect)],
        [(x0, y_back, BOX_H), (x1, y_back, BOX_H), (x1, y_front, BOX_H), (x0, y_front, BOX_H)],
    ]
    cap = []
    n = 19
    ang = np.linspace(0, np.pi, n)
    front_arc = [(TOP_R * np.cos(a), y_front, z_rect + TOP_R * np.sin(a)) for a in ang]
    back_arc = [(TOP_R * np.cos(a), y_back, z_rect + TOP_R * np.sin(a)) for a in ang]
    for i in range(n - 1):
        cap.append((front_arc[i], front_arc[i + 1], back_arc[i + 1], back_arc[i]))
        cap.append(((0.0, y_front, z_rect), front_arc[i], front_arc[i + 1], front_arc[i + 1]))
        cap.append(((0.0, y_back, z_rect), back_arc[i + 1], back_arc[i], back_arc[i]))
    # botão, um disco baixo no centro do topo
    snap = []
    snap_z = TOTAL_H - SNAP_FROM_TOP
    sr, sh = 6.0, 2.2
    sang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    outer = [(sr * np.cos(a), y_front + sh, snap_z + sr * np.sin(a)) for a in sang]
    inner = [(sr * np.cos(a), y_front, snap_z + sr * np.sin(a)) for a in sang]
    for i in range(12):
        j = (i + 1) % 12
        snap.append((outer[i], outer[j], inner[j], inner[i]))
        snap.append(((0.0, y_front + sh, snap_z), outer[i], outer[j], outer[j]))
    cups = []
    cn = 24
    cang = np.linspace(0, 2 * np.pi, cn, endpoint=False)
    for sign in (-1, 1):
        cx = sign * (FACE / 2 + CUP_OD / 2)
        r = CUP_OD / 2
        ring0 = [(cx + r * np.cos(a), r * np.sin(a), 0.0) for a in cang]
        ring1 = [(cx + r * np.cos(a), r * np.sin(a), CUP_H) for a in cang]
        for i in range(cn):
            j = (i + 1) % cn
            cups.append((ring0[i], ring0[j], ring1[j], ring1[i]))
            cups.append(((cx, 0.0, CUP_H), ring1[i], ring1[j], ring1[j]))
    return body, handle, cap, snap, cups


def save_3d():
    fig = plt.figure(figsize=(6.2, 5.4))
    ax = fig.add_subplot(111, projection="3d")
    mustard = np.array([196, 132, 42]) / 255
    cupc = np.array([211, 154, 69]) / 255
    snap_c = np.array([138, 106, 50]) / 255
    body, handle, cap, snap, cups = bag_parts()

    def paint(quads, color, edges="#5a3410", lw=0.25):
        ax.add_collection3d(
            Poly3DCollection(quads, facecolors=color, edgecolors=edges, linewidths=lw, alpha=0.97)
        )

    paint(body, mustard)
    paint(handle, mustard)
    paint(cap, mustard, edges=mustard, lw=0.15)
    paint(snap, snap_c, edges=snap_c, lw=0.1)
    paint(cups, cupc, lw=0.15)
    # Quase de frente, um pouco de lado, como a foto de referência.
    ax.view_init(elev=12, azim=-102)
    ax.set_box_aspect((FACE + 2 * CUP_OD, DEPTH + 20, TOTAL_H))
    lim = FACE / 2 + CUP_OD + 10
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-DEPTH, DEPTH)
    ax.set_zlim(0, TOTAL_H + 10)
    ax.set_axis_off()
    ax.set_title("Modelo 3D rígido, nas medidas do molde")
    path = FIG / "modelo3d.png"
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close()
    return path


def save_rings(phys):
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.2))
    for ax, key, title in (
        (axes[0], "leather", "Copo com casca de couro 2,2 mm"),
        (axes[1], "montana", "Copo só de Montana 1,0 mm"),
    ):
        xy, xy_def = phys["rings"][key]
        xy, xy_def = xy * 1000, xy_def * 1000
        ax.plot(np.r_[xy[:, 0], xy[0, 0]], np.r_[xy[:, 1], xy[0, 1]], color="#888", lw=1.5, label="antes")
        ax.plot(np.r_[xy_def[:, 0], xy_def[0, 0]], np.r_[xy_def[:, 1], xy_def[0, 1]], color="#A33B24", lw=1.8, label="sob 3 N")
        ax.set_aspect("equal")
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8, loc="upper right")
        ax.set_xlabel("mm")
    fig.suptitle("Ensaio do anel: deslocamento real, sem exagero", fontsize=12)
    fig.tight_layout()
    path = FIG / "aneis.png"
    fig.savefig(path, dpi=140)
    plt.close()
    return path


def save_bars(phys):
    labels = ["Montana\nno painel", "Couro 2,8\nno painel", "Montana\nvão 50 mm", "Montana\nvão 30 mm", "Copo\nMontana", "Copo\ncouro 2,2"]
    vals = [
        phys["finger"]["montana_painel"],
        phys["finger"]["couro_painel"],
        phys["finger"]["montana_vao_50"],
        phys["finger"]["montana_vao_30"],
        phys["montana_cup"]["closure_mm"],
        phys["leather_cup"]["closure_mm"],
    ]
    shown = [min(v, 80) for v in vals]
    colors = ["#A33B24" if v > 3 else "#1B7A3A" for v in vals]
    fig, ax = plt.subplots(figsize=(8.4, 4.0))
    bars = ax.bar(labels, shown, color=colors)
    for bar, real in zip(bars, vals):
        txt = f"{real:.0f}" if real >= 10 else f"{real:.1f}"
        ax.text(bar.get_x() + bar.get_width() / 2, min(real, 80) + 1.5, txt + " mm", ha="center", fontsize=8)
    ax.axhline(3, color="#1B7A3A", ls="--", lw=1, label="limite de 3 mm")
    ax.set_ylabel("Flecha (escala cortada em 80 mm)")
    ax.set_title("Quanto a parede cede")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 95)
    fig.tight_layout()
    path = FIG / "barras.png"
    fig.savefig(path, dpi=140)
    plt.close()
    return path


def write_obj():
    verts, faces = [], []

    def add_quad(quad):
        a, b, c, d = quad
        i = len(verts)
        verts.extend([a, b, c, d])
        if np.allclose(c, d):
            faces.append((i + 1, i + 2, i + 3))
        else:
            faces.append((i + 1, i + 2, i + 3, i + 4))

    body, handle, cap, snap, cups = bag_parts()
    for quad in body + handle + cap + snap + cups:
        add_quad(quad)
    path = OUT / "porta-vinho.obj"
    with path.open("w") as fh:
        fh.write("# Porta-vinho rigido, unidades em milimetros. Eixo Z para cima.\n")
        fh.write("# A alca e a frente continuada, com janela. Os copos nascem no fundo.\n")
        for v in verts:
            fh.write(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}\n")
        for f in faces:
            fh.write("f " + " ".join(str(i) for i in f) + "\n")
    return path


def write_ring_obj(name, xy_def):
    path = OUT / name
    pts = xy_def * 1000
    with path.open("w") as fh:
        fh.write("# secao do copo deformada, mm\n")
        for p in pts:
            fh.write(f"v {p[0]:.4f} {p[1]:.4f} 0\n")
        fh.write("l " + " ".join(str(i) for i in range(1, len(pts) + 1)) + " 1\n")
    return path


def frente_polylines():
    """y = 0 no topo da peça acabada. Duas polilinhas: acabada e de corte."""
    finished = []
    # tampa semicircular, da esquerda para a direita pelo topo
    arc = np.linspace(np.pi, 0, 25)
    for a in arc:
        finished.append((TOP_R + TOP_R * np.cos(a), TOP_R - TOP_R * np.sin(a)))
    finished += [(FACE, TOP_R), (FACE, TOTAL_H), (0, TOTAL_H), (0, TOP_R)]
    cut = []
    for a in arc:
        cut.append((TOP_R + TOP_R * np.cos(a), TOP_R - TOP_R * np.sin(a)))
    y_join = HANDLE_H
    cut += [
        (FACE, TOP_R),
        (FACE, y_join),
        (FACE + SA, y_join),
        (FACE + SA, TOTAL_H + SA),
        (-SA, TOTAL_H + SA),
        (-SA, y_join),
        (0, y_join),
        (0, TOP_R),
    ]
    return finished, cut


def clip_seg(p, q, x0, y0, x1, y1):
    left, right, bottom, top = 1, 2, 4, 8

    def code(x, y):
        c = 0
        if x < x0:
            c |= left
        elif x > x1:
            c |= right
        if y < y0:
            c |= bottom
        elif y > y1:
            c |= top
        return c

    xa, ya = p
    xb, yb = q
    c1, c2 = code(xa, ya), code(xb, yb)
    for _ in range(12):
        if not (c1 | c2):
            return (xa, ya), (xb, yb)
        if c1 & c2:
            return None
        c = c1 or c2
        if c & top:
            x = xa + (xb - xa) * (y1 - ya) / (yb - ya)
            y = y1
        elif c & bottom:
            x = xa + (xb - xa) * (y0 - ya) / (yb - ya)
            y = y0
        elif c & right:
            y = ya + (yb - ya) * (x1 - xa) / (xb - xa)
            x = x1
        else:
            y = ya + (yb - ya) * (x0 - xa) / (xb - xa)
            x = x0
        if c == c1:
            xa, ya, c1 = x, y, code(x, y)
        else:
            xb, yb, c2 = x, y, code(x, y)
    return None


def clip_poly(poly, y0, y1, x0=None, x1=None):
    segs = []
    pts = poly + [poly[0]]
    xa0 = -1e9 if x0 is None else x0
    xa1 = 1e9 if x1 is None else x1
    for a, b in zip(pts, pts[1:]):
        clipped = clip_seg(a, b, xa0, y0, xa1, y1)
        if clipped:
            segs.append(clipped)
    return segs


class Doc(FPDF):
    def __init__(self):
        super().__init__(unit="mm", format="A4")
        self.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        self.add_font("DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        self.set_auto_page_break(True, 16)

    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 6, f"Porta-vinho com duas taças  ·  página {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def h1(self, text):
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "B", 16)
        self.multi_cell(0, 8, text)
        self.ln(1)

    def h2(self, text):
        self.ln(1)
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "B", 12)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def p(self, text):
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "", 10)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_x(self.l_margin)
        self.set_font("DejaVu", "", 10)
        self.multi_cell(0, 5, "•  " + text)

    def ensure(self, height):
        if self.get_y() + height > 280:
            self.add_page()


def build_pdf(phys, images):
    pdf = Doc()
    pdf.add_page()
    pdf.h1("Porta-vinho com duas taças")
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 6, "Molde, medidas e ensaio de rigidez para Montana furadinho com casca de couro.")
    pdf.ln(2)
    pdf.p(
        "A peça segue a referência: corpo alto para uma garrafa, um copo aberto de cada lado, "
        "alça com janela retangular e botão no topo. A marca gravada na foto de referência não entra no molde."
    )
    pdf.set_fill_color(232, 245, 233)
    pdf.set_font("DejaVu", "B", 11)
    pdf.multi_cell(
        0, 6,
        "Veredito: fica em pé e durinha se o Montana for só a capa. "
        "Por baixo, frente, costas, laterais, fundo e os dois copos precisam ser couro firme contínuo. "
        "Nervuras soltas não passam no ensaio.",
        fill=True,
    )
    pdf.ln(3)
    pdf.image(str(images["vistas"]), w=180)
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 9)
    pdf.multi_cell(0, 4, "Frente, lado e topo nas medidas acabadas. Os copos nascem no fundo e param aos 180 mm.")

    pdf.add_page()
    pdf.h1("O que a cliente pediu")
    pdf.p(
        "O material principal à vista é Montana furadinho, o sintético perfurado. "
        "A sustentação pedida era couro duro em alguns pontos. A bolsa tem de ficar igual à foto e não pode molengar."
    )
    pdf.h2("Por que ponto de couro não resolve")
    pdf.p(
        "O furadinho dobra com o próprio peso. Um dedo de 2 N no meio do painel, entre as laterais, "
        f"afunda o Montana cerca de {phys['finger']['montana_painel']:.0f} mm. "
        f"Com uma nervura a cada 50 mm, a flecha ainda fica em {phys['finger']['montana_vao_50']:.0f} mm. "
        f"A cada 30 mm, fica em {phys['finger']['montana_vao_30']:.0f} mm. "
        "Para chegar perto de 4 mm seria preciso uma nervura a cada 20 mm, o que já é uma chapa."
    )
    pdf.p(
        "Quando a flecha calculada passa de 20 mm, o número deixa de ser uma medida e passa a dizer que a peça dobra. "
        f"A mesma pressão na casca de couro de {LEATHER_PANEL:.1f} mm cede {phys['finger']['couro_painel']:.1f} mm. "
        f"O copo de Montana ovaliza {phys['montana_cup']['closure_mm']:.0f} mm sob 3 N. "
        f"O copo de couro de {LEATHER_CUP:.1f} mm ovaliza {phys['leather_cup']['closure_mm']:.1f} mm."
    )
    pdf.p(
        "O couro fica escondido. Por fora é Montana, inclusive no debrum liso da mesma cor, "
        "porque o furadinho rasga se for dobrado na borda. A costura aparente a 3 mm da borda reproduz o acabamento da foto."
    )

    pdf.h2("O que cabe dentro")
    pdf.p(
        f"Corpo interno {phys['inner_w']:.0f} × {phys['inner_d']:.0f} mm, altura útil {phys['inner_h']:.0f} mm. "
        "Cabe garrafa bordalesa de 750 ml até cerca de 90 mm de diâmetro e 300 mm de altura. "
        f"Cada copo tem diâmetro interno {CUP_ID:.0f} mm e altura {CUP_H:.0f} mm: a taça entra com o bojo para baixo "
        "e a haste fica para fora. Bojo acima de 90 mm não entra. Meça a taça da cliente antes de cortar."
    )

    pdf.add_page()
    pdf.h1("Ensaio")
    pdf.image(str(images["modelo"]), w=120)
    pdf.ln(2)
    pdf.p(
        "O sólido acima é o arquivo porta-vinho.obj, em milímetros. O ensaio usa elementos de viga no anel do copo "
        "e a flecha de uma faixa engastada nas duas bordas do painel. Não é uma simulação de pano. "
        "A pergunta é se a parede segura a forma, e esse é o cálculo certo para ela."
    )
    pdf.p(
        f"O anel de couro fechou o diâmetro em {phys['leather_cup']['closure_mm']:.2f} mm no modelo "
        f"e em {phys['leather_cup']['formula_mm']:.2f} mm na fórmula clássica de Roark. "
        f"A razão entre os dois é {phys['leather_cup']['ratio']:.3f}. O mesmo código, com o Montana, "
        f"dá {phys['montana_cup']['closure_mm']:.0f} mm. A conta está conferida."
    )
    pdf.p(
        "Módulos adotados: couro firme 180 MPa; Montana furadinho 8 MPa em flexão, já com o desconto dos furos. "
        "Densidade 900 kg/m³ no couro e 750 kg/m³ no Montana. Carga do dedo: 2 N numa faixa de 30 mm. "
        "Carga do copo: 3 N apertando o diâmetro, o esforço de uma taça encostada. "
        "Limite para aprovar: flecha até 3 mm."
    )
    pdf.image(str(images["aneis"]), w=180)
    pdf.ln(2)
    pdf.set_font("DejaVu", "", 9)
    pdf.multi_cell(0, 4, "À esquerda o couro quase não sai do lugar. À direita o Montana atravessa o próprio diâmetro. Escala real.")

    pdf.add_page()
    pdf.h1("Resultado")
    pdf.image(str(images["barras"]), w=175)
    pdf.ln(2)
    headers = ["Peça", "Construção", "Flecha", "Situação"]
    rows = [
        ["Painel", "Só Montana 1,0 mm", f"{phys['finger']['montana_painel']:.0f} mm", "Molenga"],
        ["Painel", "Nervura a cada 50 mm", f"{phys['finger']['montana_vao_50']:.0f} mm", "Molenga"],
        ["Painel", "Nervura a cada 30 mm", f"{phys['finger']['montana_vao_30']:.0f} mm", "Molenga"],
        ["Painel", "Casca de couro 2,8 mm", f"{phys['finger']['couro_painel']:.1f} mm", "Aprovada"],
        ["Copo", "Só Montana", f"{phys['montana_cup']['closure_mm']:.0f} mm", "Amassa"],
        ["Copo", "Aro solto de 14 mm", f"{phys['leather_hoop']['closure_mm']:.0f} mm", "Ainda cede"],
        ["Copo", "Casca de couro 2,2 mm", f"{phys['leather_cup']['closure_mm']:.1f} mm", "Aprovada"],
    ]
    widths = [28, 62, 32, 40]
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_fill_color(42, 42, 42)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    for i, row in enumerate(rows):
        pdf.set_font("DejaVu", "", 8)
        pdf.set_fill_color(230, 245, 232) if row[-1] == "Aprovada" else pdf.set_fill_color(255, 236, 230)
        for c, w in zip(row, widths):
            pdf.cell(w, 6.5, c, border=1, fill=True)
        pdf.ln()
    pdf.ln(3)
    pdf.set_font("DejaVu", "B", 11)
    pdf.multi_cell(0, 6, "Se o Montana do rolo for mais duro do que o adotado")
    pdf.ln(1)
    pdf.set_font("DejaVu", "", 10)
    pdf.p("Mesmo um sintético furado bem mais rígido continua mole. O couro é que muda o resultado.")
    headers = ["Módulo do Montana", "Dedo no painel", "Oval do copo"]
    widths = [55, 50, 50]
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_fill_color(42, 42, 42)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 8)
    for item in phys["sensitivity"]:
        pdf.cell(55, 6.5, f"{item['E_MPa']:.0f} MPa", border=1)
        pdf.cell(50, 6.5, f"{item['dedo_mm']:.0f} mm", border=1)
        pdf.cell(50, 6.5, f"{item['copo_mm']:.0f} mm", border=1)
        pdf.ln()

    pdf.add_page()
    pdf.h1("Ficar em pé na mesa")
    te = phys["tip_empty"]
    tl = phys["tip_loaded"]
    pdf.p(
        f"A bolsa vazia pesa cerca de {phys['mass_bag_kg']:.2f} kg. "
        f"Com garrafa de 1,25 kg e duas taças de 0,28 kg, fica em {phys['mass_loaded_kg']:.2f} kg. "
        f"O centro de massa carregado está a {phys['com_loaded_mm']:.0f} mm do fundo."
    )
    pdf.p(
        f"Para a frente, o apoio tem {DEPTH:.0f} mm. Vazia, tomba a partir de {te[0]:.0f}°. "
        f"Carregada, a partir de {tl[0]:.0f}°. Um empurrão de {tl[2]:.1f} N no topo da alça, "
        "cerca de 300 gramas-força, já a derruba para a frente. Para os lados, os copos alargam a base: "
        f"o ângulo sobe para {tl[1]:.0f}° e o empurrão precisa chegar a {tl[3]:.1f} N."
    )
    pdf.p(
        "Em mesa plana ela fica em pé. O risco é um toque na alça, de frente para trás, não a falta de rigidez. "
        "Não aumente a altura da alça. Se a cliente quiser mais estabilidade de frente, aumente a profundidade do corpo em 10 mm, "
        "não afrouxe a parede."
    )
    pdf.h2("Erguer pela janela")
    pdf.p(
        f"O peso carregado puxa {phys['lift_n']:.0f} N na alça. Ao lado da janela sobram duas faixas de couro. "
        f"A tensão no couro fica em {phys['stress_leather_mpa']:.2f} MPa, folgada para vaqueta. "
        f"Se a janela fosse só Montana, a tensão média iria a {phys['stress_montana_mpa']:.2f} MPa e, no furo, "
        "umas três vezes isso. O furadinho rasga. A janela é cortada nas duas cascas de couro e debruada."
    )

    pdf.add_page()
    pdf.h1("Materiais")
    pdf.p("Compre um pouco a mais. O couro do copo é mais fino porque precisa enrolar.")
    rows = [
        ("Montana furadinho 1,0 mm", "capa de tudo", "50 cm × 1,40 m"),
        ("Montana liso, mesma cor", "debrum", "tira de 3 m × 22 mm"),
        ("Couro firme 2,8 mm", "frente, costas, laterais, alça", "50 × 70 cm"),
        ("Couro firme 3,2 mm", "fundo do corpo", "pode sair do mesmo couro"),
        ("Couro 2,2 a 2,6 mm", "os dois copos", "40 × 50 cm, ou rebaixar o 2,8"),
        ("Botão de pressão 12 mm", "topo da alça", "1, ouro velho"),
        ("Linha encerada 0,6 mm", "costura aparente", "cor próxima do Montana"),
        ("Cola de contato", "colar capa na casca", "própria para couro e sintético"),
    ]
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_fill_color(42, 42, 42)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(("Material", "Onde entra", "Quantidade"), (62, 62, 52)):
        pdf.cell(w, 7, h, border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 8)
    for a, b, c in rows:
        pdf.cell(62, 7, a, border=1)
        pdf.cell(62, 7, b, border=1)
        pdf.cell(52, 7, c, border=1)
        pdf.ln()
    pdf.ln(3)
    pdf.set_font("DejaVu", "", 10)
    pdf.p(
        "Agulha 100/16 ou 110/18. Pé de teflon ou de rolete. A alça, com frente e costas juntas, chega a cerca de 7,5 mm. "
        "Máquina doméstica comum pode não subir nesse ponto. Rebaixe o couro para 1,5 mm só na faixa da costura da alça, "
        "ou cosa a alça à mão com duas agulhas. O restante da caixa fica na faixa de 4 mm por costura, que a máquina costuma aceitar."
    )
    pdf.h2("Impressão dos moldes")
    pdf.bullet("Imprima em A4, escala 100%, sem ajustar à página.")
    pdf.bullet("Em cada folha de molde, no canto de cima, há uma linha de 50 mm. Meça com régua. Se não der 50, a folha está errada. A última folha traz também um quadrado de 50 mm.")
    pdf.bullet("Linha preta é corte. Linha azul é a peça acabada. A diferença é a margem de 8 mm.")
    pdf.bullet("Na alça a linha preta e a azul coincidem: a borda é acabada, sem virar.")
    pdf.bullet("Onde a folha diz faixa 2, sobreponha os triângulos da faixa 1 e cole com fita.")
    pdf.bullet("Corte duas frentes de couro e duas de Montana no mesmo molde. O mesmo vale para as costas: o molde da frente serve.")

    pdf.add_page()
    pdf.h1("Ordem de fazer")
    steps = [
        "Risque o couro pelo molde, com o lado mais firme na vertical. Corte a frente duas vezes: uma é a frente, a outra é as costas.",
        "Corte o Montana furadinho nas mesmas peças. O sentido menos elástico fica na vertical, senão o copo estica e ovaliza.",
        "Rebaixe a margem de costura do couro até uns 1,2 mm. Na alça, rebaixe também a faixa dos 12 mm da borda, até 1,5 mm, para a máquina passar.",
        "Cole o Montana no couro com cola de contato, capa com capa, casca com casca. Deixe os 8 mm da margem sem cola. Alinhe pelo topo, que não tem margem.",
        "Marque a janela nas duas placas, centrada, começando 66 mm abaixo do topo, com 58 por 34 mm. Corte as duas juntas, com cantos levemente arredondados.",
        "Empilhe frente e costas, Montana para fora. Costure o contorno da alça, de um lado ao outro, desde a linha onde o corpo abre, dando a volta no topo. Ponto a 3 mm da borda, comprimento 3,5 mm.",
        "Costure em volta da janela, a 3 mm do corte, unindo as duas placas. Aí a janela fica debruada pelo próprio couro.",
        "Pregue o botão de 12 mm no centro, a 18 mm do topo, atravessando as duas placas.",
        "Costure cada lateral na frente e nas costas, só no trecho do corpo, 318 mm a partir do fundo. A margem de 8 mm fica para dentro. O topo da lateral termina onde a alça já está fechada.",
        "Costure o fundo. Os cantos do fundo encontram os cantos das laterais. Abra a margem com o osso e bata o canto para ficar quadrado, como na foto.",
        "No copo, enrole a casca de couro de 2,2 mm num tubo de diâmetro interno 94 mm. A emenda, de 8 mm mais 8 mm, fica para o lado que encosta na bolsa. Cole e costure a emenda.",
        "Cole a capa de Montana por fora do tubo, com a emenda no mesmo lugar. A capa dá a volta por fora e pode pedir os 8 mm da margem na emenda: não estique o furadinho. Vire 12 mm de Montana liso para dentro do topo, cobrindo um aro de couro de 14 mm de largura. Costure a 3 mm.",
        "Embuta o fundo redondo e costure. O fundo do copo fica no mesmo plano do fundo da bolsa.",
        "Costure cada copo na lateral, centrado, com o fundo alinhado. A costura vertical da emenda fica escondida contra a bolsa. Reforce o topo e a base do encontro com um retrocesso.",
        "Passe tinta de borda na cor do Montana onde o couro aparecer. Não é para aparecer faixa clara.",
        "Prova: ponha a garrafa e as duas taças numa mesa plana. A bolsa fica em pé. Aperte o painel com o dedo: o couro cede cerca de 1 mm e volta. Se afundar, a capa foi colada numa nervura, não numa casca.",
    ]
    for i, step in enumerate(steps, 1):
        pdf.ensure(16)
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(8, 5, f"{i}.")
        pdf.set_font("DejaVu", "", 10)
        pdf.multi_cell(0, 5, step)
        pdf.ln(1)

    pdf.h2("Erros que desfazem o ensaio")
    pdf.bullet("Usar napa macia no lugar da vaqueta. O módulo cai e o painel volta a molengar.")
    pdf.bullet("Deixar o Montana sem cola no meio do painel. A capa bolsa entre as costuras.")
    pdf.bullet("Fazer o copo só com aro em cima e embaixo. O aro sozinho ovaliza mais de 1 cm.")
    pdf.bullet("Aumentar a alça para a garrafa ficar mais enterrada. O centro de massa sobe e ela tomba para a frente com menos força.")

    add_pattern_pages(pdf)
    path = OUT / "porta-vinho-tacas-molde.pdf"
    pdf.output(str(path))
    return path


def add_pattern_pages(pdf):
    finished, cut = frente_polylines()
    tiles = [(0, 210), (190, 400), (380, TOTAL_H + SA)]
    for idx, (y0, y1) in enumerate(tiles, 1):
        pattern_page(
            pdf,
            f"Frente e costas — faixa {idx} de 3",
            "Corte 2 de couro 2,8 mm e 2 de Montana. Uma peça é a frente, a outra é as costas.",
            [("acabada", finished, (31, 78, 140)), ("corte", cut, (0, 0, 0))],
            y0, y1, 16, 36, join=idx < 3,
        )
        mark_window(pdf, y0, y1, 16, 36)

    lat_fin, lat_cut = rect_poly(DEPTH, BOX_H, SA)
    for idx, (y0, y1) in enumerate(((0, 210), (190, BOX_H + 2 * SA)), 1):
        pattern_page(
            pdf,
            f"Lateral — faixa {idx} de 2",
            "Corte 2 de couro e 2 de Montana. A margem de 8 mm vai nos quatro lados.",
            [("acabada", lat_fin, (31, 78, 140)), ("corte", lat_cut, (0, 0, 0))],
            y0, y1, 16, 36, join=idx < 2,
        )

    fund_fin, fund_cut = rect_poly(FACE, DEPTH, SA)
    pattern_page(
        pdf,
        "Fundo do corpo",
        "Corte 1 de couro 3,2 mm e 1 de Montana. Quadrado acabado de 106 mm.",
        [("acabada", fund_fin, (31, 78, 140)), ("corte", fund_cut, (0, 0, 0))],
        0, 140, 16, 36, join=False,
    )

    circ = np.pi * (CUP_ID + LEATHER_CUP)
    cup_len = circ + 2 * SA
    cup_h = CUP_H + SA + 12
    cup_fin = [(0, 12), (circ, 12), (circ, 12 + CUP_H), (0, 12 + CUP_H)]
    cup_cut = [( -SA, 0), (circ + SA, 0), (circ + SA, cup_h), (-SA, cup_h)]
    tiles_x = [(0, 180), (160, cup_len)]
    for idx, (x0, x1) in enumerate(tiles_x, 1):
        pattern_page(
            pdf,
            f"Parede do copo — faixa {idx} de 2",
            "Corte 2 de couro 2,2 mm e 2 de Montana. A faixa longa é a volta do tubo. Emenda de 8 mm em cada ponta.",
            [("acabada", cup_fin, (31, 78, 140)), ("corte", cup_cut, (0, 0, 0))],
            0, cup_h + 5, 16, 36, x0=x0, x1=x1, join=idx < 2,
        )

    pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "B", 14)
    pdf.multi_cell(pdf.epw, 7, "Fundos redondos, aros e janela")
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "", 10)
    pdf.multi_cell(pdf.epw, 5, "Tudo nesta folha está em tamanho real. Confira o quadrado de 50 mm.")
    pdf.ln(2)
    square(pdf, 150, 22)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.4)
    # fundo redondo: diametro de corte = ID + 2*SA
    d_cut = CUP_ID + 2 * SA
    cx, cy, r = 55, 95, d_cut / 2
    pdf.ellipse(cx - r, cy - r, d_cut, d_cut)
    pdf.set_draw_color(31, 78, 140)
    pdf.ellipse(cx - CUP_ID / 2, cy - CUP_ID / 2, CUP_ID, CUP_ID)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", "", 9)
    pdf.text(20, 95 + r + 8, f"Fundo do copo. Corte 2 couro + 2 Montana. Corte Ø {d_cut:.0f}. Acabado Ø {CUP_ID:.0f}.")
    # aro
    pdf.set_draw_color(0, 0, 0)
    pdf.rect(20, 175, 170, 14)
    pdf.set_font("DejaVu", "", 8)
    pdf.text(22, 184, "Aro do copo — esta faixa é só uma amostra da largura: 14 mm.")
    hoop_len = np.pi * (CUP_ID - 4) + 25
    pdf.text(20, 198, f"Corte 2 aros de couro 2,8 mm, largura 14 mm, comprimento {hoop_len:.0f} mm (já com 25 mm de transpasse).")
    # janela
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    jx, jy = 20, 210
    pdf.rect(jx, jy, WIN_W, WIN_H)
    pdf.set_draw_color(31, 78, 140)
    pdf.rect(jx - 8, jy - 8, WIN_W + 16, WIN_H + 16)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.text(20, 258, f"Janela em tamanho real: corte {WIN_W:.0f} × {WIN_H:.0f} mm. A linha azul é a costura, 8 mm para fora só como referência de margem.")
    pdf.text(20, 264, "Na peça, a janela começa 66 mm abaixo do topo e fica centrada na largura de 106 mm.")


def rect_poly(w, h, sa):
    finished = [(sa, sa), (sa + w, sa), (sa + w, sa + h), (sa, sa + h)]
    cut = [(0, 0), (w + 2 * sa, 0), (w + 2 * sa, h + 2 * sa), (0, h + 2 * sa)]
    return finished, cut


def square(pdf, x, y):
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, 50, 50)
    pdf.set_font("DejaVu", "", 7)
    pdf.text(x + 8, y + 27, "50 mm")


def pattern_page(pdf, title, subtitle, layers, y0, y1, ox, oy, x0=None, x1=None, join=True):
    pdf.add_page()
    text_w = pdf.epw - 62
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "B", 13)
    pdf.multi_cell(text_w, 6, title)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "", 9)
    pdf.multi_cell(text_w, 4, subtitle)
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "", 8)
    if x0 is None:
        faixa = f"Faixa vertical {y0:.0f}–{y1:.0f} mm, a partir do topo."
    else:
        faixa = f"Faixa horizontal {x0:.0f}–{x1:.0f} mm. A altura inteira está nesta folha."
    extra = " Cole a seguinte sobre os triângulos." if join else " Esta é a última faixa desta peça."
    pdf.multi_cell(text_w, 4, faixa + extra)
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.45)
    pdf.line(148, 16, 198, 16)
    pdf.line(148, 14, 148, 18)
    pdf.line(198, 14, 198, 18)
    pdf.set_font("DejaVu", "", 7)
    pdf.text(163, 13, "50 mm")
    pdf.set_line_width(0.45)
    for name, poly, color in layers:
        pdf.set_draw_color(*color)
        segs = clip_poly(poly, y0, y1, x0, x1)
        shift_x = 0 if x0 is None else x0
        for (xa, ya), (xb, yb) in segs:
            pdf.line(ox + xa - shift_x, oy + ya - y0, ox + xb - shift_x, oy + yb - y0)
    # marcas de encontro
    pdf.set_fill_color(180, 40, 40)
    pdf.set_draw_color(180, 40, 40)
    for mark_y in (y0, y1):
        page_y = oy + mark_y - y0
        if 30 < page_y < 250:
            pdf.polygon([(ox - 3, page_y), (ox + 3, page_y - 2.5), (ox + 3, page_y + 2.5)], style="F")
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("DejaVu", "", 8)
    pdf.text(14, 270, "Preto = corte. Azul = acabado. Triângulo vermelho = linha de encontro da outra faixa.")
    pdf.set_text_color(0, 0, 0)


def mark_window(pdf, y0, y1, ox, oy):
    if WIN_TOP + WIN_H < y0 or WIN_TOP > y1:
        return
    x = ox + (FACE - WIN_W) / 2
    y = oy + WIN_TOP - y0
    pdf.set_draw_color(160, 60, 20)
    pdf.set_line_width(0.35)
    pdf.rect(x, y, WIN_W, WIN_H)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(160, 60, 20)
    pdf.text(x, max(8, y - 1), "janela")
    pdf.set_text_color(0, 0, 0)


def main():
    phys = run_physics()
    serial = {k: v for k, v in phys.items() if k != "rings"}
    # tuples of tip metrics
    serial["tip_empty"] = list(phys["tip_empty"])
    serial["tip_loaded"] = list(phys["tip_loaded"])
    (OUT / "ensaio.json").write_text(json.dumps(serial, indent=2), encoding="utf-8")
    images = {
        "vistas": save_views(phys),
        "modelo": save_3d(),
        "aneis": save_rings(phys),
        "barras": save_bars(phys),
    }
    write_obj()
    write_ring_obj("copo-couro-deformado.obj", phys["rings"]["leather"][1])
    write_ring_obj("copo-montana-deformado.obj", phys["rings"]["montana"][1])
    pdf_path = build_pdf(phys, images)
    print("PDF", pdf_path)
    print("validação couro", round(phys["leather_cup"]["ratio"], 4))
    print("dedo montana", round(phys["finger"]["montana_painel"], 1))
    print("dedo couro", round(phys["finger"]["couro_painel"], 2))
    print("copo montana", round(phys["montana_cup"]["closure_mm"], 1))
    print("copo couro", round(phys["leather_cup"]["closure_mm"], 2))


if __name__ == "__main__":
    main()

"""Molde plano das peças principais, em milímetros, com margem de costura."""
import math
from pathlib import Path

import dimensions as D

MM = 1000.0
SA = 8.0  # margem de costura
ST = 3.0  # pesponto


def r(v):
    return round(v, 2)


def panel_path(x, y, w, h, radius):
    """Contorno com topo arredondado. Origem no canto inferior esquerdo da peça cortada."""
    rad = min(radius, w / 2, h)
    pts = [
        (x, y),
        (x, y + h - rad),
    ]
    cx, cy = x + rad, y + h - rad
    for i in range(1, 7):
        a = math.pi - i * (math.pi / 2) / 6
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    cx = x + w - rad
    for i in range(0, 7):
        a = math.pi / 2 - i * (math.pi / 2) / 6
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    pts.append((x + w, y))
    pts.append((x, y))
    return " ".join(f"{r(px)},{r(py)}" for px, py in pts)


def main():
    panel_w = D.PANEL_W * MM
    panel_h = (D.HANDLE_H + D.CYL_H) * MM
    cyl_w = math.pi * D.CYL_OD * MM
    cyl_h = D.CYL_H * MM
    base_w = (2 * (D.PANEL_W / 2 + D.CYL_R + 0.003 + D.CYL_R) + 0.012) * MM
    base_d = (D.CYL_OD + 0.014) * MM
    bay_w = D.BAY_W * MM
    bay_d = D.BAY_D * MM
    bay_h = D.CYL_H * MM
    slot_w = D.SLOT_W * MM
    slot_h = D.SLOT_H * MM
    # fenda medida a partir do topo da peça (sem a margem)
    slot_from_top = D.SLOT_FROM_TOP * MM

    # layout em folhas
    pieces = []
    # painel
    pieces.append(("painel", 40, 40, panel_w, panel_h))
    x2 = 40 + panel_w + 2 * SA + 50
    pieces.append(("traseiro", x2, 40, bay_w, bay_h))
    pieces.append(("lateral", x2 + bay_w + 2 * SA + 40, 40, bay_d, bay_h))
    y2 = 40 + panel_h + 2 * SA + 70
    pieces.append(("cilindro", 40, y2, cyl_w, cyl_h))
    pieces.append(("base", 40 + cyl_w + 2 * SA + 40, y2, base_w, base_d))
    y3 = y2 + cyl_h + 2 * SA + 70
    pieces.append(("piso", 40, y3, D.CYL_OD * MM, D.CYL_OD * MM))
    pieces.append(("aro", 40 + D.CYL_OD * MM + 80, y3, cyl_w, 12))
    pieces.append(("nervura", 40 + D.CYL_OD * MM + cyl_w + 120, y3, 16, bay_h))
    pieces.append(("canal", 40, y3 + D.CYL_OD * MM + 60, 90, panel_h * D.HANDLE_H / (D.HANDLE_H + D.CYL_H)))

    width = 1100
    height = int(y3 + D.CYL_OD * MM + panel_h * 0.6 + 160)

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">')
    out.append('<rect width="100%" height="100%" fill="#f6f1e7"/>')
    out.append('<style>text{font-family:DejaVu Sans,sans-serif;fill:#3a2414}.cut{fill:none;stroke:#8a3b12;stroke-width:0.6}.sew{fill:none;stroke:#c4a574;stroke-width:0.35;stroke-dasharray:2 1.4}.lbl{font-size:5px}.sub{font-size:3.4px;fill:#6b4a2a}</style>')
    out.append('<text x="20" y="18" font-size="7">Molde porta-vinho/taças — montana perfurado + couro rígido</text>')
    out.append('<text x="20" y="28" class="sub">Linha cheia = corte. Tracejado = pesponto (3 mm). Margem de costura 8 mm. Medidas em mm. Estimativa de modelagem, não molde de produção certificado.</text>')

    def cut_rect(x, y, w, h, name, note, material):
        out.append(f'<rect class="cut" x="{r(x)}" y="{r(y)}" width="{r(w+2*SA)}" height="{r(h+2*SA)}"/>')
        out.append(f'<rect class="sew" x="{r(x+SA)}" y="{r(y+SA)}" width="{r(w)}" height="{r(h)}"/>')
        out.append(f'<text class="lbl" x="{r(x)}" y="{r(y-3)}">{name}</text>')
        out.append(f'<text class="sub" x="{r(x)}" y="{r(y+h+2*SA+6)}">{note} · {material}</text>')

    # painel frontal com topo arredondado e fenda
    x, y = 30, 40
    pw, ph = panel_w + 2 * SA, panel_h + 2 * SA
    out.append(f'<polyline class="cut" points="{panel_path(x, y, pw, ph, D.TOP_RADIUS*MM+SA)}"/>')
    out.append(f'<polyline class="sew" points="{panel_path(x+SA, y+SA, panel_w, panel_h, D.TOP_RADIUS*MM)}"/>')
    # fenda no miolo (coordenadas SVG y cresce para baixo; o topo da peça está em y)
    sx = x + SA + (panel_w - slot_w) / 2
    sy = y + SA + slot_from_top
    out.append(f'<rect class="cut" x="{r(sx)}" y="{r(sy)}" width="{r(slot_w)}" height="{r(slot_h)}"/>')
    out.append(f'<text class="lbl" x="{r(x)}" y="{r(y-4)}">1 · Painel frontal (alça + corpo) — 1×</text>')
    out.append(f'<text class="sub" x="{r(x)}" y="{r(y+ph+6)}">{r(panel_w)} × {r(panel_h)} mm no pesponto · fenda {r(slot_w)}×{r(slot_h)} · montana perfurado</text>')

    cut_rect(x + pw + 24, 40, bay_w, bay_h, "2 · Painel traseiro do berço — 1×", f"{r(bay_w)} × {r(bay_h)} mm", "montana perfurado")
    cut_rect(x + pw + bay_w + 2 * SA + 48, 40, bay_d, bay_h, "3 · Lateral do berço — 2×", f"{r(bay_d)} × {r(bay_h)} mm", "montana perfurado")

    cut_rect(30, y + ph + 28, cyl_w, cyl_h, "4 · Cilindro desenvolvido — 2×", f"{r(cyl_w)} × {r(cyl_h)} mm (π × Ø {r(D.CYL_OD*MM)})", "montana perfurado")
    cut_rect(30 + cyl_w + 2 * SA + 24, y + ph + 28, base_w, base_d, "5 · Base / plinto — 1×", f"{r(base_w)} × {r(base_d)} mm · esp. 2,2 mm", "couro rígido")

    yb = y + ph + cyl_h + 2 * SA + 56
    od = D.CYL_OD * MM
    # piso circular
    cx, cy, rad = 30 + od / 2 + SA, yb + od / 2 + SA, od / 2
    out.append(f'<circle class="cut" cx="{r(cx)}" cy="{r(cy)}" r="{r(rad+SA)}"/>')
    out.append(f'<circle class="sew" cx="{r(cx)}" cy="{r(cy)}" r="{r(rad)}"/>')
    out.append(f'<text class="lbl" x="30" y="{r(yb-4)}">6 · Piso do cilindro — 2×</text>')
    out.append(f'<text class="sub" x="30" y="{r(yb+od+2*SA+8)}">Ø {r(od)} mm · couro rígido</text>')

    cut_rect(30 + od + 2 * SA + 30, yb, cyl_w, 12, "7 · Aro superior — 2×", "faixa 12 mm de altura · couro rígido", "couro rígido")
    cut_rect(30 + od + cyl_w + 4 * SA + 50, yb, 16, bay_h, "8 · Nervura do berço — 4×", "16 × altura do berço · couro 2,2 mm", "couro rígido")
    canal_h = D.HANDLE_H * MM
    cut_rect(30, yb + od + 2 * SA + 24, 90, canal_h, "9 · Parede do canal da alça — 2×", "90 mm × altura da alça, afastadas 12 mm · couro 2,2 mm", "couro rígido")
    cut_rect(30 + 90 + 2 * SA + 20, yb + od + 2 * SA + 24, 10, cyl_h, "10 · Nervura do cilindro — 4×", "10 mm · couro 2,2 mm", "couro rígido")

    out.append("</svg>")
    path = Path("/workspace/porta-vinho/molde-plano.svg")
    path.write_text("\n".join(out))
    print("WROTE", path, "bytes", path.stat().st_size)


if __name__ == "__main__":
    main()

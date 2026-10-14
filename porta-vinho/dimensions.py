"""Proporções do porta-vinho.

A foto de referência não é ortográfica. A altura foi fixada em 400 mm
e as razões abaixo saíram da silhueta (topo, fenda, início dos cilindros,
base). São medidas de proporção, não um levantamento com paquímetro.
"""

# Altura total, coroa até o chão
H = 0.400
# Painel frontal: largura medida ~235 px numa altura de ~913 px → 103 mm
PANEL_W = 0.104
TOP_RADIUS = 0.026
# Fenda: começa ~51 mm abaixo da coroa, altura ~32 mm, largura ~67% do painel
SLOT_W = 0.070
SLOT_H = 0.032
SLOT_FROM_TOP = 0.050
SNAP_D = 0.009
SNAP_FROM_TOP = 0.018

# Cilindros mais baixos que o painel. Razão foto ~0,39 da altura.
CYL_H = 0.150
CYL_OD = 0.085
CYL_R = CYL_OD / 2.0
PLINTH_H = 0.016
HANDLE_H = H - PLINTH_H - CYL_H  # 0.234 m

# Berço da garrafa de 75 mm, com folga
BAY_W = 0.080
BAY_D = 0.084
BOTTLE_D = 0.075
BOTTLE_H = 0.300
GLASS_D = 0.060
GLASS_H = 0.120

# Quanto o painel cobre o cilindro, lido na foto (o painel é mais largo que o berço)
OVERLAP = 0.008

# Estimativas de material — não são dados de laboratório
MONTANA_T = 0.0011
MONTANA_E = 30e6  # Pa
MONTANA_RHO = 900.0  # kg/m3
MONTANA_HOLE = 0.0015
MONTANA_PITCH = 0.004
LEATHER_T = 0.0022
LEATHER_E = 250e6
LEATHER_RHO = 950.0
NU = 0.40

# Cargas
BOTTLE_MASS = 1.30
GLASS_MASS = 0.15

# Imperfeição geométrica inicial (fora de prumo), em radianos no script
IMPERFECTION_DEG = 1.5

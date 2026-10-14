# Ficha técnica — porta-vinho/taças

Modelagem em escala real no Blender 4.0.2. As proporções saíram da foto de referência (altura fixada em 400 mm). Os módulos e as massas são **estimativas de projeto, não ensaio de laboratório**.

## Silhueta

Peça em pé, vista de três quartos:

- Painel frontal alto, mostarda, topo arredondado, fenda retangular e botão de latão centrado acima da fenda. O centro do painel fica liso: não há wordmark.
- Dois cilindros abertos, mais baixos que o painel, no mesmo piso, um de cada lado.
- Base chata, com plinto, para a peça ficar de pé.
- Pesponto na borda do painel.

| Cota | Valor | Origem |
| --- | --- | --- |
| Altura total | 400 mm | pedido |
| Largura do painel | 104 mm | foto: ~235 px em ~913 px de altura |
| Raio do topo | 26 mm | foto: o arredondado ocupa ~25 mm |
| Fenda | 70 × 32 mm, a 50 mm do topo | foto |
| Botão | Ø 9 mm, a 18 mm do topo | foto |
| Cilindro | Ø 85 mm × 150 mm | Ø pedido; altura ~0,39 da peça na foto |
| Berço da garrafa | 80 × 84 mm internos | folga sobre garrafa de 75 mm |
| Garrafa (carga) | Ø 75 mm × 300 mm, 1,30 kg | pedido |
| Taça (carga) | Ø 60 mm × 120 mm, 0,15 kg cada | pedido |
| Plinto | 16 mm de altura | base estruturada da foto |
| Base | cerca de 292 × 99 mm | envolve os dois cilindros com folga |

## Materiais (estimativa)

| | Montana perfurado | Couro rígido |
| --- | --- | --- |
| Espessura | 1,1 mm | 2,2 mm |
| Furos | Ø 1,5 mm em grade de 4 mm | sem furo |
| Módulo E | 30 MPa | 250 MPa |
| Densidade | 900 kg/m³ | 950 kg/m³ |
| Poisson (adotado) | 0,40 | 0,40 |
| Rigidez de placa D = E t³ / 12(1−ν²) | 0,0040 N·m | 0,264 N·m |

O montana cobre as superfícies vistas: painel, berço e cilindros. O couro entra só como osso: base, pisos, aros, nervuras, canal da alça e debrum de borda.

D do couro é cerca de 67 vezes o do montana, porque a espessura dobra (o cubo dá fator 8) e o módulo é 8,3 vezes maior.

## Por que o montana sozinho dobra

Numa chapa, a inércia à flexão é I = b t³/12. Para o painel de 104 mm:

- I montana = 1,15×10⁻¹¹ m⁴
- E I = 3,5×10⁻⁴ N·m²

Isso não segura um painel de 234 mm acima dos copos, nem o berço com a garrafa de 1,3 kg, nem o cilindro se a boca ovalizar e a parede passar a trabalhar como tira aberta (I de uma faixa de 40 mm é ainda menor). O peso próprio já gera momento maior que o momento resistente da chapa assim que a peça sai 1,5° do prumo. A compressão pura da garrafa sobre a base seria pequena; o que derruba é a flexão.

## Como o E entrou no simulador

O pano do Blender não aceita MPa. A mola angular SPRING2 do rigid body, no caso calibrado, fecha com N·m/rad.

Calibração (não é o porta-vinho; é uma barra de controle):

- Barra de 0,20 m, massa 0,10 kg, imperfeição de 8°.
- Equilíbrio: k (θ − θ₀) = m g (L/2) sen θ.
- k = 0,2 N·m/rad assentou em 15,47° (teoria 15,52°).
- k = 2,0 N·m/rad assentou em 8,41° (teoria 8,41°).

Nas dobradiças da bolsa:

```
k = E I / L
```

aplicado em `spring_stiffness_ang_z`, com o eixo local Z do vazio alinhado ao X do mundo (tombo para a frente ou para trás).

Imperfeição inicial de 1,5°, sem tensão na mola. Gravidade 9,81 m/s². 180 quadros a 30 fps. Garrafa e taças são corpos rígidos com a massa pedida, presos ao berço e aos cilindros.

## Caso A — só montana

Sem nervura, sem aro, sem canal. I de chapa aberta.

| Mola | k (N·m/rad) |
| --- | --- |
| Berço | 0,0023 |
| Alça | 0,0015 |
| Cilindro | 0,0009 |

Resultado no último quadro, depois de assentar (por volta do quadro 40 a peça já estava no chão):

| | Valor | Limite | |
| --- | --- | --- | --- |
| Inclinação da alça | 90,0° | < 8° | reprova |
| Perda de altura da coroa | 99,5% (399,8 mm → 2,1 mm) | < 8% | reprova |
| Inclinação dos cilindros | 95,5° | < 8° | reprova |

**Reprovado.** A peça tomba e fica deitada na mesa, com a garrafa junto.

## Caso B — montana + couro

Primeira ossatura (4 nervuras de 16×2,2 mm no berço, sanduíche plano de 2×2,2 mm na alça, aro no cilindro):

- A alça foi a 39,3° e encostou na garrafa. Perda de altura 13,0%.
- Os cilindros travaram em 11,8° porque a boca batia no berço.

Isso não passou. O que foi acrescentado, e só isso:

1. **Canal de couro na alça**, duas paredes de 90 × 2,2 mm com 12 mm entre eixos (seção caixa). O sanduíche plano, k = 0,73 N·m/rad, não segurou. O canal dá I = 1,44×10⁻⁸ m⁴ e **k = 15,4 N·m/rad**.
2. **Duas nervuras de 10×2,2 mm em cada cilindro**, além do aro, e 3 mm de folga entre cilindro e painel para a boca não travar no berço. k do cilindro passou a 69 N·m/rad.
3. O plinto deixa de colidir com alça e cilindro; quem os segura é a mola. O contato com o plinto empurrava o copo até 11,8° e a mola não desfazia esse encosto.

Resultado no quadro 180 (6 s), já estável desde o quadro 120:

| | Valor | Limite | |
| --- | --- | --- | --- |
| Inclinação da alça | 0,77° | < 8° | passa |
| Altura da coroa | 399,8 mm → 400,3 mm | perda < 8% | passa (não perdeu altura; endireitou a imperfeição de 1,5°) |
| Inclinação dos cilindros | 1,26° | < 8° | passa |

**Aprovado.** A peça fica de pé.

A série da alça (quadros 20, 40, 60, 90, 120, 180) foi 0,13° → 0,15° → 0,20° → 0,31° → 0,46° → 0,77°. Não há queda livre. O valor final está folgado em relação a 8°.

## Peças

Molde em `molde-plano.svg` (corte cheio, pesponto tracejado, margem 8 mm).

| Peça | Material | Quantidade |
| --- | --- | --- |
| Painel frontal com fenda | montana perfurado | 1 |
| Painel traseiro e laterais do berço | montana perfurado | 1 + 2 |
| Cilindro desenvolvido | montana perfurado | 2 |
| Base / plinto | couro rígido 2,2 mm | 1 |
| Piso do cilindro | couro rígido | 2 |
| Aro superior (12 mm) | couro rígido | 2 |
| Nervura do berço 16 mm | couro rígido | 4 |
| Parede do canal da alça | couro rígido | 2 |
| Nervura do cilindro 10 mm | couro rígido | 4 |
| Debrum de borda | couro rígido | 2 faixas |

## Arquivos

- `simulate_porta_vinho.py` — geometria, molas e ensaio
- `dimensions.py` — cotas
- `caseA.blend`, `caseB.blend` — cenas com o cache de física
- `resultado_caseA.json`, `resultado_caseB.json` — números do ensaio
- `molde-plano.svg`

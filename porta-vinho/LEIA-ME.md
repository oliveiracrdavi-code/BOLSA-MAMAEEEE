# Porta-vinho com duas taças

Molde, tutorial e ensaio de rigidez para a bolsa da foto: corpo alto, dois copos abertos nas laterais, alça com janela e botão. A capa é Montana furadinho. A estrutura que deixa a peça em pé é uma casca contínua de couro firme por baixo.

## O que imprimir

`saida/porta-vinho-tacas-molde.pdf`

- Folha A4, escala 100%, sem ajustar à página.
- Em cada folha de molde, a linha de 50 mm no canto de cima tem de medir 50 mm na régua.
- A última folha tem também um quadrado de 50 mm.
- Linha preta é corte. Linha azul é a peça acabada. A diferença é a margem de 8 mm.
- Onde a folha diz faixa 2 ou 3, sobreponha os triângulos vermelhos e cole com fita.

## Modelo 3D

`saida/porta-vinho.obj` é a bolsa rígida, em milímetros, com o eixo Z para cima. Abre no Blender, no Meshmixer ou no visualizador 3D do sistema.

`saida/copo-couro-deformado.obj` e `saida/copo-montana-deformado.obj` são a seção do copo depois do ensaio de 3 N. Os números do ensaio estão em `saida/ensaio.json` e nas páginas do PDF.

## Gerar de novo

```bash
python3 gerar_projeto.py
```

Precisa de numpy, matplotlib, fpdf2 e, para conferir as páginas, pymupdf.

# -*- coding: utf-8 -*-
import io, sys, statistics as st
sys.path.insert(0, "src")
import pandas as pd, xlrd
from pathlib import Path
from validador import MapaZonas

mapa = MapaZonas.de_arquivo(Path("config/zonas.json"))
log = io.StringIO()
livro = xlrd.open_workbook("execucao.XLS", logfile=log)
aba = livro.sheet_by_index(0)
dados = [aba.row_values(i) for i in range(aba.nrows)]
df = pd.DataFrame(dados[1:], columns=[str(c).strip() for c in dados[0]])
for c in df.columns:
    df[c] = df[c].fillna("").astype(str).str.strip()

CHAVE = ["Data Operação","Serviço","Veículo","Partida Prevista","Chegada Prevista","Origem","Destino"]
df = df.drop_duplicates(subset=CHAVE)
tipo = df["Tipo Serviço"].str.upper()
df = df[tipo.isin(["NORMAL","EXTRA"])]
p = pd.to_numeric(df["Partida Prevista"], errors="coerce")
c = pd.to_numeric(df["Chegada Prevista"], errors="coerce")
dur = (c - p) * 24 * 60
ok = dur.notna() & (dur > 0) & (dur < 60*60)
df, dur = df[ok], dur[ok]

def rot(x):
    z = mapa.zona(x)
    return z.replace("ZONA_", "") if z else mapa.resolver(x)

pares = {}
for (o, d, du) in zip(df["Origem"], df["Destino"], dur):
    a, b = rot(o), rot(d)
    if a == b:
        continue
    k = tuple(sorted((a, b)))
    pares.setdefault(k, []).append(du)

linhas = []
for k, v in pares.items():
    linhas.append((k, len(v), min(v), st.median(v), max(v)))
linhas.sort(key=lambda x: x[3])

def hh(m):
    return f"{int(m)//60}h{int(m)%60:02d}"

curtas = [l for l in linhas if l[3] <= 300]
print(f"pares de ponta: {len(linhas)} | com mediana <= 5h: {len(curtas)} | viagens no arquivo: {int(sum(l[1] for l in linhas))}")
print(f"\n{'par':16} {'viagens':>7} {'min':>7} {'mediana':>8} {'max':>7}")
for k, n, mn, md, mx in curtas:
    marca = "  <-- max acima de 5h" if mx > 300 else ""
    print(f"{k[0]+' x '+k[1]:16} {n:7} {hh(mn):>7} {hh(md):>8} {hh(mx):>7}{marca}")
print("\n--- os 8 pares logo acima do corte, para calibrar ---")
for k, n, mn, md, mx in [l for l in linhas if l[3] > 300][:8]:
    print(f"{k[0]+' x '+k[1]:16} {n:7} {hh(mn):>7} {hh(md):>8} {hh(mx):>7}")

"""
Página online da validação da malha SIGLA.

O que ela faz a cada 10 minutos: baixa o execucao.XLS do link compartilhado,
roda o mesmo `main.py` que roda na mão, e mostra o relatório HTML embutido.

Por que chama o main.py por subprocesso em vez de importar o pipeline: o
main.py é o caminho testado, com todos os avisos que servem de trilha de
auditoria. Chamando ele, a página e o menu do .bat nunca divergem. O texto do
console aparece no expansor "Como este número foi apurado".

Rodar aqui:
    streamlit run streamlit_app.py
Rodar servindo a rede interna:
    streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501

A URL do link NUNCA fica no código nem no repositório. Ela vem, nesta ordem:
    1. Secrets do Streamlit  ->  SIGLA_EXECUCAO_URL = "https://..."
    2. variável de ambiente SIGLA_EXECUCAO_URL
    3. execucao_url no config/caminhos.json, só para uso local
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parent
SAIDA = RAIZ / "saida"
INTERVALO_SEG = 600
VARIAVEL_URL = "SIGLA_EXECUCAO_URL"


def _sem_runtime() -> bool:
    """True quando o arquivo foi chamado com `python`, e não com `streamlit run`.

    Sem servidor do Streamlit cada chamada de st.* imprime um aviso de
    ScriptRunContext, e a tela vira uma parede de warnings sem nenhuma página no
    fim. Melhor parar na primeira linha e dizer o comando certo.
    """
    try:
        from streamlit.runtime import exists

        return not exists()
    except Exception:
        return False


if _sem_runtime():
    print()
    print("Este arquivo é um app do Streamlit, não um script comum.")
    print("Rodando com `python` não sobe servidor nenhum e só sai aviso.")
    print()
    print("  streamlit run streamlit_app.py")
    print()
    print("Para servir a rede interna:")
    print("  streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501")
    print()
    print("Para só validar na linha de comando, sem página:")
    print("  python main.py --remoto --sem-abrir")
    print()
    raise SystemExit(2)

st.set_page_config(
    page_title="Malha SIGLA, validação",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------- segredo
def semear_url() -> bool:
    """Leva a URL dos Secrets para o ambiente, que é o que o subprocesso herda."""
    if os.environ.get(VARIAVEL_URL):
        return True
    try:
        valor = st.secrets[VARIAVEL_URL]
    except Exception:
        return False
    if valor:
        os.environ[VARIAVEL_URL] = str(valor)
        return True
    return False


TEM_URL = semear_url()


# ---------------------------------------------------------------- pipeline
@st.cache_data(ttl=INTERVALO_SEG * 2, show_spinner=False)
def rodar(dia: str, corte: str, remoto: bool, janela: int) -> dict:
    """Roda o main.py e devolve log, resumo e o HTML do relatório.

    `janela` é o número do bloco de 10 minutos. Ele não é usado dentro da
    função: existe só para o cache virar sozinho a cada bloco, sem depender de
    ttl adivinhado.
    """
    argumentos = [sys.executable, "main.py", "--sem-abrir", "--corte", corte]
    if remoto:
        argumentos.append("--remoto")
    else:
        argumentos += ["--arquivo", "execucao.XLS"]
    if dia:
        argumentos += ["--dia", dia]

    inicio = time.monotonic()
    try:
        processo = subprocess.run(argumentos, cwd=str(RAIZ), capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=420)
        log = (processo.stdout or "") + (processo.stderr or "")
        codigo = processo.returncode
    except subprocess.TimeoutExpired:
        return {"ok": False, "log": "O pipeline passou de 7 minutos e foi cortado.",
                "codigo": -1, "segundos": time.monotonic() - inicio}

    resposta = {"ok": codigo == 0, "log": log, "codigo": codigo,
                "segundos": time.monotonic() - inicio}
    if codigo != 0:
        return resposta

    resumo_json = SAIDA / "ultimo.json"
    if resumo_json.exists():
        resposta["ultimo"] = json.loads(resumo_json.read_text(encoding="utf-8"))
        alvo = Path(resposta["ultimo"]["relatorio_caminho"])
        if not alvo.is_absolute():
            alvo = RAIZ / alvo
        if alvo.exists():
            resposta["html"] = alvo.read_text(encoding="utf-8")
            resposta["arquivo"] = alvo.name
    return resposta


# ---------------------------------------------------------------- topo
try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(interval=INTERVALO_SEG * 1000, key="tique")
    AUTO = True
except ImportError:
    AUTO = False

with st.sidebar:
    st.header("Fonte")
    remoto = st.toggle("Baixar do link compartilhado", value=TEM_URL,
                       help="Desligado, usa o execucao.XLS que estiver na pasta "
                            "do projeto.")
    if remoto and not TEM_URL:
        st.warning(f"Nenhuma URL configurada. Ponha {VARIAVEL_URL} nos Secrets "
                   "do app ou na variável de ambiente.")

    st.header("Recorte")
    hoje = st.checkbox("Dia de hoje", value=True)
    dia = ""
    if not hoje:
        escolhido = st.date_input("Dia alvo", value=datetime.now())
        dia = escolhido.strftime("%d/%m/%Y")

    modo_corte = st.radio(
        "Hora de corte",
        ["Hora de agora", "Hora fixa", "Sem corte"],
        help="Malha que já rodou não muda mais, então serviço que terminou antes "
             "do corte sai da análise.",
    )
    if modo_corte == "Hora de agora":
        corte = "agora"
    elif modo_corte == "Sem corte":
        corte = "nao"
    else:
        hora = st.time_input("Cortar às", value=datetime.now().time())
        corte = hora.strftime("%H:%M")

    st.divider()
    if st.button("Atualizar agora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Atualização automática a cada {INTERVALO_SEG // 60} min: "
               + ("ligada" if AUTO else "DESLIGADA, falta o pacote "
                                        "streamlit-autorefresh"))

janela = int(time.time() // INTERVALO_SEG)
with st.spinner("Baixando, validando e desenhando…"):
    resultado = rodar(dia, corte, remoto, janela)

st.title("Validação da malha SIGLA")

if not resultado["ok"]:
    st.error("O pipeline não terminou. O log abaixo diz onde parou.")
    st.code(resultado["log"] or "sem saída", language="text")
    st.stop()

ultimo = resultado.get("ultimo", {})
meta = ultimo.get("meta", {})
resumo = ultimo.get("resumo", {})
severidade = resumo.get("severidade", {})
por_tipo = resumo.get("tipo", {})

linha = st.columns(5)
linha[0].metric("Anomalias", ultimo.get("anomalias", "-"))
linha[1].metric("Trilhos afetados", ultimo.get("trilhos_afetados", "-"))
linha[2].metric("Trilhos na malha", resumo.get("trilhos", "-"))
linha[3].metric("Serviços", resumo.get("servicos", "-"))
linha[4].metric("Viradas conferidas", resumo.get("elos", "-"))

linha = st.columns(4)
for coluna, chave, rotulo in zip(linha,
                                 ["CRITICA", "ALTA", "MEDIA", "BAIXA"],
                                 ["Críticas", "Altas", "Médias", "Baixas"]):
    coluna.metric(rotulo, severidade.get(chave, 0))

NOME_TIPO = {
    "SEQUENCIA": "Trilho quebrado",
    "VIRADA_CURTA": "Virada curta",
    "VIRADA_LINHA_CURTA": "Virada linha curta",
    "SOBREPOSICAO": "Sobreposição",
    "LOCAL_FORA_DO_MAPA": "Local sem zona",
}
if por_tipo:
    st.caption("Por tipo: " + " · ".join(
        f"{NOME_TIPO.get(k, k)} {v}" for k, v in sorted(por_tipo.items(),
                                                        key=lambda kv: -kv[1])))

st.caption(
    f"Malha de {meta.get('dia_operacao', '?')} · corte {meta.get('corte', '?')} · "
    f"gerado em {meta.get('gerado_em', '?')} · extração "
    f"{meta.get('arquivo_origem', '?')} · apurado em "
    f"{resultado['segundos']:.0f} s"
)

with st.expander("Como este número foi apurado"):
    st.code(resultado["log"], language="text")

html = resultado.get("html")
if not html:
    st.warning("O relatório foi gerado mas não pôde ser lido de saida/.")
    st.stop()

st.download_button("Baixar o relatório HTML", data=html,
                   file_name=resultado.get("arquivo", "malha.html"),
                   mime="text/html")

altura = st.slider("Altura do quadro", 800, 4000, 1800, step=100)

# st.iframe é o substituto do st.components.v1.html, que sai do Streamlit depois
# de 01/06/2026. O fallback existe porque o requirements aceita 1.37, que ainda
# não tem o novo.
if hasattr(st, "iframe"):
    st.iframe(html, height=altura)
else:
    st.components.v1.html(html, height=altura, scrolling=True)

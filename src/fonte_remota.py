"""
Baixa o execucao.XLS de um link compartilhado do OneDrive ou SharePoint.

O relatório é gerado por outro processo, que deixa o arquivo numa pasta
publicada por link. Aqui só se consome esse link.

Link de compartilhamento não entrega o arquivo direto: a URL devolve a página
do visualizador do Office. As estratégias abaixo são tentadas em ordem até vir
um arquivo de verdade, e a que funcionou aparece no relatório de saída.

A gravação é atômica: o corpo desce para um `.part` na mesma pasta do destino e
só então é renomeado por cima. Nunca pelo Temp do sistema, porque de lá a troca
vira cópia mais exclusão e o Windows recusa com "arquivo em uso" sempre que o
OneDrive ou o antivírus estiver com um handle aberto. Quem lê o cache nunca vê
arquivo pela metade.

  1. download=1     acrescenta o parâmetro na própria URL de compartilhamento
  2. download.aspx  troca o caminho por /personal/<conta>/_layouts/15/
                    download.aspx?share=<ID>
  3. url crua       último recurso, para link que já aponta para o arquivo

Como se sabe que veio arquivo e não tela de login: os primeiros bytes. XLS
antigo é OLE2 e começa com D0 CF 11 E0, xlsx é zip e começa com PK. Página HTML
não começa com nenhum dos dois, e é o sintoma de link que exige autenticação.
Nesse caso a função devolve o diagnóstico em vez de gravar lixo no cache.

ONDE PÕE A URL: nunca dentro do repositório. O link carrega o token de
compartilhamento, então quem tem o link tem o arquivo. Use a variável de
ambiente SIGLA_EXECUCAO_URL, ou os Secrets do Streamlit Cloud.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from arquivos import substituir as _substituir
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

VARIAVEL_AMBIENTE = "SIGLA_EXECUCAO_URL"

# Primeiros bytes de um arquivo de planilha de verdade.
ASSINATURAS = {
    b"\xd0\xcf\x11\xe0": "xls, formato OLE2 antigo",
    b"PK\x03\x04": "xlsx, formato zip",
}

CABECALHOS = {
    # Sem um agente conhecido o SharePoint às vezes devolve a página do
    # visualizador mesmo com download=1.
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"),
    "Accept": "*/*",
}


def resolver_url(explicito: str | None = None, config: dict | None = None) -> str | None:
    """Ordem: argumento explícito, variável de ambiente, config. Nunca inventa."""
    for candidato in (explicito,
                      os.environ.get(VARIAVEL_AMBIENTE),
                      (config or {}).get("execucao_url")):
        if candidato and str(candidato).strip():
            return str(candidato).strip()
    return None


def _com_parametro(url: str, chave: str, valor: str) -> str:
    partes = urlparse(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query[chave] = valor
    return urlunparse(partes._replace(query=urlencode(query)))


def _download_aspx(url: str) -> str | None:
    """Forma direta do SharePoint: /personal/<conta>/_layouts/15/download.aspx?share=<ID>."""
    partes = urlparse(url)
    achado = re.match(r"^/:[a-z]:/[a-z]/(personal/[^/]+)/([^/?]+)$", partes.path)
    if not achado:
        return None
    conta, identificador = achado.groups()
    caminho = f"/{conta}/_layouts/15/download.aspx"
    return urlunparse(partes._replace(path=caminho,
                                      query=urlencode({"share": identificador})))


def urls_candidatas(url: str) -> list[tuple[str, str]]:
    """(rótulo da estratégia, url) na ordem de tentativa, sem repetir."""
    candidatas = [("download=1", _com_parametro(url, "download", "1"))]
    direta = _download_aspx(url)
    if direta:
        candidatas.append(("download.aspx", direta))
    candidatas.append(("url crua", url))

    vistas, saida = set(), []
    for rotulo, alvo in candidatas:
        if alvo not in vistas:
            vistas.add(alvo)
            saida.append((rotulo, alvo))
    return saida


def _e_planilha(inicio: bytes) -> str | None:
    for assinatura, nome in ASSINATURAS.items():
        if inicio.startswith(assinatura):
            return nome
    return None


def baixar(url: str, destino: str | Path, timeout: int = 90) -> dict:
    """Tenta as estratégias em ordem e grava o arquivo só se for planilha.

    Devolve sempre um dicionário, nunca levanta por falha de rede:
    {ok, estrategia, formato, bytes, destino, tentativas, erro}
    """
    try:
        import requests
    except ImportError:
        return {"ok": False, "erro": "pacote requests não instalado",
                "tentativas": []}

    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tentativas = []

    for rotulo, alvo in urls_candidatas(url):
        try:
            resposta = requests.get(alvo, headers=CABECALHOS, timeout=timeout,
                                    allow_redirects=True, stream=True)
        except Exception as erro:
            tentativas.append({"estrategia": rotulo, "erro":
                               f"{type(erro).__name__}: {erro}"[:200]})
            continue

        if resposta.status_code != 200:
            tentativas.append({"estrategia": rotulo,
                               "erro": f"HTTP {resposta.status_code}"})
            resposta.close()
            continue

        # O parcial fica na pasta do destino, e não no Temp do sistema: assim a
        # troca é renomeação no mesmo volume. Pelo Temp, o shutil.move copia e
        # apaga, e é aí que o Windows reclama de arquivo em uso.
        parcial = destino.with_name(destino.name + ".part")
        primeiro = b""
        try:
            with open(parcial, "wb") as saida:
                for pedaco in resposta.iter_content(chunk_size=65536):
                    if not pedaco:
                        continue
                    if not primeiro:
                        primeiro = pedaco[:8]
                    saida.write(pedaco)
        finally:
            resposta.close()

        formato = _e_planilha(primeiro)
        tamanho = parcial.stat().st_size
        if not formato:
            # Se não der para apagar o parcial, não importa: ele é sobrescrito na
            # próxima tentativa. O que não pode é a limpeza engolir o
            # diagnóstico, que é a informação útil aqui.
            try:
                parcial.unlink(missing_ok=True)
            except OSError:
                pass
            tipo = resposta.headers.get("Content-Type", "?")
            tentativas.append({
                "estrategia": rotulo,
                "erro": (f"não veio planilha, e sim {tipo} com {tamanho} bytes. "
                         "Sintoma de link que pede login."),
            })
            continue

        falha = _substituir(parcial, destino)
        if falha:
            tentativas.append({
                "estrategia": rotulo,
                "erro": (f"baixou {tamanho} bytes mas não deu para publicar em "
                         f"{destino.name}: {falha}. O arquivo está aberto em outro "
                         f"programa, ou o OneDrive está sincronizando. A cópia "
                         f"íntegra ficou em {parcial.name}."),
            })
            return {"ok": False, "estrategia": rotulo, "formato": formato,
                    "bytes": tamanho, "destino": str(destino),
                    "parcial": str(parcial), "tentativas": tentativas,
                    "erro": "download completo, publicação bloqueada"}

        tentativas.append({"estrategia": rotulo, "erro": None})
        return {"ok": True, "estrategia": rotulo, "formato": formato,
                "bytes": tamanho, "destino": str(destino),
                "tentativas": tentativas, "erro": None}

    return {"ok": False, "estrategia": None, "formato": None, "bytes": 0,
            "destino": str(destino), "tentativas": tentativas,
            "erro": "nenhuma estratégia trouxe o arquivo"}


def _milhar(numero: int) -> str:
    return f"{numero:,}".replace(",", ".")


def resumir(relatorio: dict) -> list[str]:
    """Linhas de texto para o main.py e para o app mostrarem o que aconteceu."""
    if relatorio.get("ok"):
        return [f"Baixado pelo link ({relatorio['estrategia']}): "
                f"{_milhar(relatorio['bytes'])} bytes, {relatorio['formato']}"]
    linhas = [f"Download pelo link falhou: {relatorio.get('erro')}"]
    for tentativa in relatorio.get("tentativas", []):
        if tentativa.get("erro"):
            linhas.append(f"  {tentativa['estrategia']}: {tentativa['erro']}")
    if not relatorio.get("parcial"):
        linhas.append("Se todas dizem que pede login, o link precisa estar como "
                      "'qualquer pessoa com o link' no OneDrive.")
    return linhas


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"uso: python src/fonte_remota.py <url> [destino]")
        print(f"     ou defina {VARIAVEL_AMBIENTE} e rode sem argumento")
        url_teste = resolver_url()
        if not url_teste:
            raise SystemExit(1)
    else:
        url_teste = sys.argv[1]
    alvo = sys.argv[2] if len(sys.argv) > 2 else "dados_trabalho/remoto/execucao.XLS"
    print("Estratégias na ordem:")
    for rotulo, candidata in urls_candidatas(url_teste):
        print(f"  {rotulo:14} {candidata}")
    print()
    for linha in resumir(baixar(url_teste, alvo)):
        print(linha)

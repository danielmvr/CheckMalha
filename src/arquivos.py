"""
Escrita de arquivo que sobrevive ao Windows com OneDrive.

Todo destino deste projeto mora numa pasta sincronizada. O OneDrive, o antivírus
e o Excel seguram handle no arquivo por frações de segundo, e nesse instante
qualquer rename ou exclusão falha com
`PermissionError: [WinError 32] arquivo já está sendo usado por outro processo`.

Duas regras que valem para todo o projeto:

  1. Escreva num `.part` **na mesma pasta do destino** e publique com
     `os.replace`. Mesmo volume, renomeação atômica. Escrever no Temp do sistema
     e usar `shutil.move` faz cópia mais exclusão, que é o par de operações que
     o Windows recusa.
  2. Insista no `os.replace` algumas vezes com espera crescente, porque o handle
     é transitório. Insistir para sempre, não: depois de N tentativas, erro
     claro dizendo que o parcial íntegro ficou no disco.

Isso importa mais desde que o pipeline passou a rodar a cada 10 minutos por cima
sempre dos mesmos nomes fixos.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

TENTATIVAS = 6
ESPERA = 0.4


def substituir(origem: Path, destino: Path, tentativas: int = TENTATIVAS,
               espera: float = ESPERA) -> str | None:
    """os.replace com paciência. None em sucesso, ou o motivo da última falha."""
    ultimo = None
    for numero in range(tentativas):
        try:
            os.replace(origem, destino)
            return None
        except OSError as erro:
            ultimo = f"{type(erro).__name__}: {erro}"
            time.sleep(espera * (numero + 1))
    return ultimo


def _publicar(parcial: Path, destino: Path) -> None:
    falha = substituir(parcial, destino)
    if falha is None:
        return
    raise OSError(
        f"não deu para publicar {destino.name}: {falha}. O arquivo está aberto "
        f"em outro programa, ou o OneDrive está sincronizando. O conteúdo "
        f"íntegro ficou em {parcial.name}."
    )


def escrever_texto(destino: str | Path, texto: str, encoding: str = "utf-8") -> Path:
    """Grava texto de forma atômica. Quem lê nunca vê arquivo pela metade."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    parcial.write_text(texto, encoding=encoding)
    _publicar(parcial, destino)
    return destino


def copiar(origem: str | Path, destino: str | Path) -> Path:
    """Copia preservando data, de forma atômica. Origem igual ao destino não faz nada."""
    origem, destino = Path(origem), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        if origem.resolve() == destino.resolve():
            return destino
    except OSError:
        pass
    parcial = destino.with_name(destino.name + ".part")
    shutil.copy2(origem, parcial)
    _publicar(parcial, destino)
    return destino

"""
Versão única do projeto.

Quem mostra: o cabeçalho do relatório HTML, a página do Streamlit e o
`main.py --versao`. Mudou o comportamento, muda aqui e registra no CHANGELOG.md.

Formato MAIOR.MENOR.CORRECAO:
  MAIOR     muda o que conta como anomalia, ou quebra a leitura de um relatório
            antigo. Exige recontar a linha de base.
  MENOR     regra, filtro ou fonte nova, sem mudar o que já era anomalia.
  CORRECAO  conserto de defeito ou de texto, sem efeito nos números.
"""

VERSAO = "2.0.0"

# Histórico de versões

Formato MAIOR.MENOR.CORRECAO, explicado em `src/versao.py`. A versão aparece no
canto superior esquerdo do relatório e da página.

## 1.0.0, 03/09/2026

Primeira versão numerada. Estado do validador da malha SIGLA nesta data.

### Fontes
- `execucao.XLS` do SIGLA, com dedução da escala de motorista e recorte da
  janela pelo dia alvo.
- Raspagem por OCR da malha, mantida em paralelo.
- Consumo por **link compartilhado** do OneDrive, com três estratégias de
  download, checagem por assinatura de arquivo e queda para o cache anterior.

### Regras
- Virada mínima de 240 min, tolerância 5, com exceções em `regras_virada.json`:
  curta distância, continuidade de serviço, atividade interna e o transbordo
  BSB/DIV pela condição nova `par_rota`.
- Classificação de serviço em três níveis de precedência: `prefixos_internos`
  pelo nome (`FUNCIONARIO`), `por_tipo` pelo tipo estruturado, e o padrão do
  número como reserva.
- `VIRADA_LINHA_CURTA`, tipo próprio para as 11 linhas de viagem até 5h, com
  filtro dedicado e uma severidade abaixo.
- Descarte de veículo que não é veículo: `SIMULTANEO`, `TURISMO`, vazio,
  `CANCELAD.*` e `N ABRIR*`. Veículo de terceiro fica.
- 12 zonas e 40 códigos, com normalização de garagem pelo catálogo de 295
  siglas.
- **Hora de corte**, padrão a hora de geração: o que já terminou sai da análise.
  Ancorada no fuso da operação, não no relógio da máquina.

### Relatório
- Recorte de 1 hora em volta da virada no desenho, com o horário cheio no texto.
- Escala de cor de 5 degraus no tempo de virada, pela fração do mínimo que
  sobrou.
- Filtros por tipo de anomalia, por severidade, por **empresa** e busca livre.
- Exportação CSV do que está filtrado.

### Operação
- Nome fixo em `dados_trabalho` e `saida`, um por dia de operação.
- Escrita atômica em toda gravação, `src/arquivos.py`, para sobreviver ao
  OneDrive no Windows.
- Página online em Streamlit, atualização automática a cada 10 minutos,
  chamando o `main.py` por subprocesso.

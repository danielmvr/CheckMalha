# Processo: Relatório de Carros em Manutenção

## Visão Geral

Este processo é responsável pela preparação dos dados e envio de relatório por e-mail dos veículos que ficaram indisponíveis devido à manutenção. Ele atua como uma etapa (perna) de um fluxo operacional maior.

---

## Ordem de Execução

### 1. Extração de Dados

**Objetivo:** Obter os registros de veículos que entraram em manutenção no período de referência.

- Consultar a fonte de dados (banco de dados, planilha ou sistema operacional)
- Filtrar pelo período desejado (ex: dia anterior, semana, mês)
- Garantir que os campos mínimos estejam presentes: identificador do veículo, data de início da manutenção, data de retorno (se houver), motivo e status

---

### 2. Preparação e Tratamento dos Dados

**Objetivo:** Limpar e estruturar os dados para uso no relatório.

- Remover registros duplicados ou inválidos
- Normalizar campos de data e hora
- Classificar os veículos por status: em manutenção, retornados no período, pendentes
- Calcular tempo de indisponibilidade por veículo
- Agregar totais e indicadores resumidos (quantidade, tempo médio de parada, etc.)

---

### 3. Geração do Relatório

**Objetivo:** Montar o arquivo de relatório a ser enviado.

- Estruturar os dados tratados em formato de relatório (Excel, PDF ou HTML)
- Incluir cabeçalho com período de referência e data de geração
- Inserir tabela detalhada por veículo
- Inserir seção de resumo com totais e indicadores

---

### 4. Envio por E-mail

**Objetivo:** Distribuir o relatório aos destinatários definidos.

- Compor o e-mail com assunto padronizado (ex: `Relatório de Manutenção – [DATA]`)
- Anexar o arquivo do relatório
- Incluir no corpo do e-mail um resumo executivo com os principais números
- Enviar para a lista de destinatários configurada
- Registrar log de envio (status, horário, destinatários)

---

### 5. Verificação de Conclusão

**Objetivo:** Confirmar que o processo foi concluído com sucesso antes de sinalizar ao processo pai.

- Verificar retorno do servidor de e-mail (confirmação de entrega ou erro)
- Em caso de falha: registrar erro, acionar alerta e não sinalizar conclusão
- Em caso de sucesso: sinalizar ao processo pai que esta etapa foi concluída

---

## Interface com o Processo Pai

| Ponto | Descrição |
|---|---|
| **Entrada** | Período de referência (data inicial e final) passado pelo processo pai |
| **Saída** | Status de conclusão: `SUCESSO` ou `FALHA` com mensagem de erro |
| **Dependências** | Acesso à fonte de dados e credenciais de e-mail configuradas |
| **Pré-condição** | Dados do período disponíveis na fonte antes da execução |
| **Pós-condição** | Relatório enviado e log registrado |

---

## Configurações Necessárias

- Fonte de dados (conexão com banco ou caminho do arquivo)
- Período de referência (definido pelo processo pai ou configuração fixa)
- Lista de destinatários do e-mail
- Credenciais do servidor de e-mail (SMTP ou serviço de envio)
- Caminho para armazenamento temporário do relatório gerado

---

## Observações

- Este processo não deve alterar dados na fonte — apenas leitura.
- Em caso de reexecução para o mesmo período, o relatório anterior deve ser sobrescrito e o e-mail reenviado com indicação de reenvio no assunto.
- O log de execução deve ser mantido para auditoria.

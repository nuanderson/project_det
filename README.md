# Controle de Notificações do DET · ISAC

Sistema para a matriz acompanhar as notificações do Domicílio Eletrônico Trabalhista (DET) recebidas por cada filial.
As filiais registram as notificações (com anexo); a matriz vê tudo, identifica quem não informou no mês, registra justificativas e acompanha dashboards.

Stack: Python 3.12+ e Django 5.2, SQLite por padrão (PostgreSQL opcional), Bootstrap e Chart.js.

## 1. Rodar localmente para teste
```
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py popular_demo
.venv\Scripts\python manage.py runserver
```
Abra http://localhost:8000. O comando `popular_demo` cria dados de exemplo e só roda com `DET_DEBUG=True` (o padrão local).
Usuários de teste: `matriz` e `filial1`, `filial2`, `filial3` (senhas `matriz-demo-123`, `filial1-demo-123`, etc.). Nunca use esses usuários em produção.

Sem dados demo, crie o administrador da matriz: `.venv\Scripts\python manage.py createsuperuser` (nasce com perfil Matriz). Depois cadastre filiais e usuários pelo menu **Filiais** e **Usuários**.

Testes automatizados: `.venv\Scripts\python -m pytest`

## 2. Regras principais
- **Fechamento mensal por filial**: `Com notificações` (há registro no mês), `Sem notificações` (a filial declarou), `Justificado` ou `Pendente`. Competência = mês de recebimento da notificação.
- **Vencida** é derivada do prazo e do status (não é armazenada).
- **Justificativas**: a filial justifica a própria filial e a matriz pode justificar qualquer uma. O histórico é só-inserção (não edita nem apaga). Criação, edição e exclusão relevantes vão para o log de auditoria.
- **Papel da matriz nas notificações**: a matriz não edita nem exclui o que a filial enviou. Ela abre a notificação, baixa o anexo, informa o prazo de resposta e o código de acesso do e-Processo (cartão "Complementar dados", cada mudança entra no histórico), altera o status e envia um aviso à filial ("Resolvida" ou "Problema no envio", este com mensagem, por exemplo anexo não veio). O aviso fica registrado, aparece no painel da filial como novo até ser aberto e também sai por e-mail quando há destinatário.
- **Histórico de atualizações**: cada notificação tem um histórico só-inserção (data, autor e texto). O campo "Histórico: registrar atualização" do formulário acrescenta uma linha a cada salvamento; mudanças de status e a importação de PDF também entram sozinhas. Aparece no formulário de edição e no detalhe, para a filial e para a matriz.
- **PDF importado**: ao importar, o PDF já aparece como "anexado automaticamente" e é gravado como anexo ao salvar, sem novo upload.
- **Escopo**: a filial só enxerga e altera dados da própria filial (`Notificacao.objects.visiveis_para`).
- **Anexos**: PDF/PNG/JPG até 10 MB, guardados fora de pasta pública e entregues só por download autenticado.

## 3. Alertas por e-mail
`manage.py enviar_alertas`, agendado uma vez por dia. Envia o lembrete mensal no dia `DET_ALERTA_DIA_MES`, avisos de prazo (`DET_ALERTA_DIAS_PRAZO`) e o resumo de vencidas à matriz.
Sem `DET_EMAIL_HOST` os e-mails só aparecem no console (útil para teste). Para ver o lembrete mensal agora: `manage.py enviar_alertas --forcar-lembrete`.

## 4. Para a equipe de TI do ISAC: subir no servidor
Configuração é toda por variáveis de ambiente `DET_*` (lista comentada em `.env.example`); não há segredos no repositório.

Antes de publicar:
1. `DET_DEBUG=False` e `DET_SECRET_KEY` longa e aleatória (o sistema recusa subir sem ela).
2. `DET_ALLOWED_HOSTS` e `DET_CSRF_TRUSTED_ORIGINS` com o endereço real; HTTPS na frente (proxy com certificado).
3. `DET_MEDIA_ROOT` apontando para uma pasta fora do projeto, com backup.
4. SMTP (`DET_EMAIL_*`) para os alertas.
5. Não rodar `popular_demo`; criar o primeiro administrador com `createsuperuser`.
6. `python manage.py check --deploy` deve passar sem avisos relevantes.

**Windows**: `.\deploy\servir.ps1 -Porta 8000` (migra, coleta estáticos e sobe com waitress; estáticos via WhiteNoise) e, em PowerShell como administrador, `.\deploy\agendar.ps1 -DestinoBackup D:\backups\det` para as tarefas diárias de alertas (08:00) e backup (22:00).

**Linux**: mesmo fluxo com `migrate`, `collectstatic` e um servidor WSGI (por exemplo `gunicorn config.wsgi`); agendar `enviar_alertas` no cron e fazer backup do banco e de `DET_MEDIA_ROOT`. Os scripts de `deploy\` são só para Windows.

**PostgreSQL**: `pip install "psycopg[binary]"` e `DET_DB_ENGINE=postgresql` com as demais `DET_DB_*`. O `backup.ps1` cobre apenas SQLite; com PostgreSQL use `pg_dump`.

Dados pessoais (LGPD): os anexos podem conter dados de trabalhadores. Restrinja o acesso ao servidor e às pastas de backup, e defina quem na matriz recebe usuário.

## 4.1 Link de teste online (Render, só dados fictícios)
O repositório traz um `render.yaml` (Blueprint) para publicar uma demonstração no plano gratuito do Render, a partir do GitHub:
1. No Render: **New +** → **Blueprint** → escolher este repositório → **Apply**.
2. Aguardar o build; o endereço fica em `https://controle-det-isac.onrender.com` (ou parecido).
3. A senha da demonstração é gerada pelo Render: serviço → **Environment** → `DET_DEMO_SENHA`. Usuários: `matriz`, `filial1`, `filial2`, `filial3`.

Como funciona: `build.sh` instala e coleta os estáticos; `start.sh` migra o banco, repopula os dados demo (`DET_PERMITIR_DEMO=True`) e sobe o waitress atrás do HTTPS do Render.
Limitações: o disco do plano gratuito é temporário (banco e anexos somem a cada deploy ou reinício), o serviço "dorme" quando fica parado e o link é público. **Não cadastre dados reais.** Para uso de verdade, siga a seção 4.

## 5. Identidade visual
Logo e paleta do ISAC em `static/img/logo_isac.png` e `static/css/tema.css` (azul `#005aa9`, azul claro `#0092d5`, cinza `#606062`). A logo também aparece nos PDFs exportados.

## 6. Estrutura
- `config/`: configurações e URLs.
- `core/`: modelos, views, formulários e `services/` (fechamento, dashboard, exportação).
- `core/management/commands/`: `enviar_alertas`, `popular_demo`.
- `templates/`, `static/`, `deploy/`, `tests/`.

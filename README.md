# Robô do WhatsApp · Novrix Tech

Atendimento automático do WhatsApp da Novrix Tech pela **API oficial da Meta** (Cloud API).

## O que ele faz

1. Quem manda a primeira mensagem recebe uma saudação com o nome e um **menu em lista**:
   Sites, Automações, Planilhas, Sistemas sob medida, OS-Church e *Falar com uma pessoa*.
2. Ao escolher um serviço, recebe a explicação e dois botões: **Quero orçamento** e **Ver outros serviços**.
3. Em **Quero orçamento** ou **Falar com uma pessoa** (ou digitando "atendente" / "orçamento"),
   o robô avisa que a equipe vai continuar a conversa e **fica quieto naquela conversa por 24 h**.
   Fora do horário (seg a sex 9h–18h, sáb 9h–13h), ele avisa quando a equipe volta.
4. Texto livre, áudio ou foto: ele mostra as opções de novo.
5. Se você responder pelo app WhatsApp Business (modo coexistência), o robô também pausa naquela conversa.
6. Tudo fica registrado no **painel** (`/painel/`): contatos, quem pediu orçamento, histórico de mensagens
   e botões para reativar ou pausar o robô em cada conversa.

Os textos ficam todos em `bot/fluxo.py`.

## Variáveis de ambiente (Render → novrix-bot → Environment)

| Variável | Onde pegar |
|---|---|
| `WHATSAPP_TOKEN` | Meta for Developers → seu app → WhatsApp → Configuração da API → token de acesso |
| `WHATSAPP_PHONE_NUMBER_ID` | Mesma tela: "ID do número de telefone" |
| `WHATSAPP_VERIFY_TOKEN` | Uma palavra que você inventa (ex.: `novrix-webhook-2026`) e repete no cadastro do webhook |
| `WHATSAPP_APP_SECRET` | Configurações do app → Básico → Chave secreta do app |
| `ADMIN_USER` / `ADMIN_PASSWORD` | Usuário e senha que você quer para entrar no `/painel/` |

`SECRET_KEY` e `DATABASE_URL` o Render preenche sozinho.

## Publicar no Render

1. Render → **New + → Blueprint** → escolha o repositório `novrix-bot` → **Apply**.
2. Preencha as variáveis que ele pedir (tabela acima).
3. Espere o deploy ficar **Live**. Teste `https://SEU-SERVICO.onrender.com/saude/` (deve mostrar `{"ok": true}`).

## Ligar na Meta

1. Meta for Developers → seu app → **WhatsApp → Configuração** → **Webhook → Editar**.
2. URL de retorno: `https://SEU-SERVICO.onrender.com/webhook/`
3. Token de verificação: o mesmo valor de `WHATSAPP_VERIFY_TOKEN` → **Verificar e salvar**.
4. Em **Campos do webhook**, assine **messages**.
5. Mande "oi" do seu celular para o número de teste: o menu deve chegar.

## Rodar no computador

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py test bot
python manage.py runserver
```

## Antes de usar com clientes de verdade

- Troque o plano do Render para pago (web `starter`, banco `basic-256mb`): o gratuito "dorme" e o banco gratuito expira.
- Troque o token temporário (24 h) por um **token de usuário do sistema** permanente (Gerenciador de Negócios → Usuários do sistema).

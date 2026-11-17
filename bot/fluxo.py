"""O roteiro da conversa: o que o robô responde em cada situação.

Para mudar um texto, mexa só neste arquivo.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings

from . import whatsapp
from .models import Contato, Mensagem

FUSO = ZoneInfo("America/Sao_Paulo")
SITE = "www.novrixtech.com.br"

# Horário de atendimento (o mesmo do perfil do WhatsApp Business).
# Segunda=0 ... Domingo=6. None = fechado.
HORARIO = {
    0: (time(9), time(18)), 1: (time(9), time(18)), 2: (time(9), time(18)),
    3: (time(9), time(18)), 4: (time(9), time(18)), 5: (time(9), time(13)), 6: None,
}
HORARIO_TEXTO = "segunda a sexta, das 9h às 18h, e sábado, das 9h às 13h"

PALAVRAS_MENU = {"menu", "inicio", "início", "voltar", "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"}
PALAVRAS_HUMANO = {"atendente", "humano", "pessoa", "falar com alguem", "falar com alguém", "orcamento", "orçamento"}

SERVICOS = {
    "sites": (
        "Sites",
        "Seu negócio aberto 24 horas por dia na internet",
        "🌐 *Sites*\n\nCriamos site institucional e página de vendas, perfeitos no celular e "
        "prontos para aparecer no Google.\n\nVocê conta como é o seu negócio e a gente cuida do resto: "
        "textos, visual, domínio e publicação.",
    ),
    "automacoes": (
        "Automações",
        "O trabalho repetitivo fica com a máquina",
        "⚡ *Automações*\n\nMensagens e respostas automáticas, aplicativos conversando entre si e "
        "tarefas que hoje são feitas à mão rodando sozinhas.\n\nMenos trabalho manual, menos erro.",
    ),
    "planilhas": (
        "Planilhas",
        "Seus números organizados e fáceis de entender",
        "📊 *Planilhas*\n\nControle financeiro e de estoque, com fórmulas e painéis que se atualizam "
        "sozinhos e relatórios prontos sem esforço.",
    ),
    "sistemas": (
        "Sistemas sob medida",
        "Um programa do jeito que sua empresa trabalha",
        "💻 *Sistemas sob medida*\n\nCadastros, controles e relatórios num sistema feito para a sua "
        "rotina, com acesso pelo computador e pelo celular.",
    ),
    "oschurch": (
        "OS-Church",
        "Gestão para igrejas em células",
        "⛪ *OS-Church*\n\nO sistema da Novrix para igrejas em células: membros, células, relatórios, "
        "cultos e mapa num só lugar.\n\n• O líder lança o relatório da célula pelo celular em 1 minuto\n"
        "• A equipe Rapha conta o culto com total na hora\n• O pastor acompanha tudo num painel\n\n"
        "Cada pessoa entra com o próprio login e vê só o que é dela.",
    ),
}


def dentro_do_horario(agora=None):
    agora = (agora or datetime.now(FUSO)).astimezone(FUSO)
    faixa = HORARIO[agora.weekday()]
    return bool(faixa and faixa[0] <= agora.time() < faixa[1])


def _normalizar(texto):
    return " ".join((texto or "").strip().lower().split())


def _registrar_saida(contato, texto, wa_id_msg):
    # Sem ID de volta = o WhatsApp não aceitou o envio; fica marcado no painel.
    Mensagem.objects.create(contato=contato, direcao=Mensagem.SAIDA, wa_message_id=wa_id_msg,
                            tipo="robo" if wa_id_msg else "falha", texto=texto)


def enviar_menu(contato, saudacao=False):
    nome = (contato.nome or "").split(" ")[0]
    if saudacao:
        texto = (f"Olá{', ' + nome if nome else ''}! 👋 Aqui é a *Novrix Tech*, obrigado pela mensagem.\n\n"
                 "Criamos tecnologia sob medida para o seu negócio. Toque em *Ver opções* e escolha "
                 "o que você precisa:")
    else:
        texto = "Toque em *Ver opções* e escolha o que você precisa:"
    linhas = [(chave, titulo, desc) for chave, (titulo, desc, _) in SERVICOS.items()]
    linhas.append(("humano", "Falar com uma pessoa", "Atendimento com a nossa equipe"))
    mid = whatsapp.enviar_lista(contato.wa_id, texto, "Ver opções", linhas, rodape=SITE)
    _registrar_saida(contato, texto, mid)


def enviar_servico(contato, chave):
    _, _, texto = SERVICOS[chave]
    contato.interesse = chave
    contato.save(update_fields=["interesse", "atualizado_em"])
    mid = whatsapp.enviar_botoes(contato.wa_id, texto, [("orcamento", "Quero orçamento"), ("menu", "Ver outros serviços")])
    _registrar_saida(contato, texto, mid)


def passar_para_humano(contato):
    contato.quer_orcamento = True
    contato.save(update_fields=["quer_orcamento", "atualizado_em"])
    if dentro_do_horario():
        texto = ("Perfeito! 🙌 Já avisei a nossa equipe e alguém vai continuar a conversa com você por aqui "
                 "em instantes.\n\nEnquanto isso, pode ir contando o que você precisa.")
    else:
        texto = ("Perfeito! 🙌 Sua mensagem já está com a nossa equipe.\n\nAgora estamos fora do horário de "
                 f"atendimento ({HORARIO_TEXTO}), mas respondemos assim que voltarmos. "
                 "Pode ir contando o que você precisa.")
    mid = whatsapp.enviar_texto(contato.wa_id, texto)
    _registrar_saida(contato, texto, mid)
    contato.pausar_robo(settings.PAUSA_HUMANO_HORAS)


def responder(contato, tipo, texto, escolha_id, primeira_vez):
    """Decide a resposta para uma mensagem recebida."""
    if contato.robo_pausado:
        return  # uma pessoa está cuidando dessa conversa

    if escolha_id:
        if escolha_id in SERVICOS:
            return enviar_servico(contato, escolha_id)
        if escolha_id in ("humano", "orcamento"):
            return passar_para_humano(contato)
        return enviar_menu(contato)

    if primeira_vez:
        return enviar_menu(contato, saudacao=True)

    t = _normalizar(texto)
    if t in PALAVRAS_HUMANO:
        return passar_para_humano(contato)
    if t in PALAVRAS_MENU:
        return enviar_menu(contato, saudacao=True)

    # Áudio, foto ou texto livre: mostra de novo as opções, sem insistir demais.
    aviso = "Para eu te ajudar mais rápido, escolha uma opção abaixo. Se preferir, escolha *Falar com uma pessoa*."
    mid = whatsapp.enviar_texto(contato.wa_id, aviso)
    _registrar_saida(contato, aviso, mid)
    enviar_menu(contato)

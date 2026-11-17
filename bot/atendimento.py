"""Caixa de entrada: a tela onde a equipe lê e responde as conversas do WhatsApp."""
from datetime import timedelta

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import whatsapp
from .models import Contato, Mensagem

JANELA = timedelta(hours=24)  # a Meta só deixa mandar texto livre até 24 h depois da última mensagem do cliente

ROTULOS = {
    "audio": "🎤 Áudio", "voice": "🎤 Áudio", "image": "📷 Foto", "video": "🎬 Vídeo",
    "document": "📄 Documento", "sticker": "Figurinha", "location": "📍 Localização",
    "contacts": "👤 Contato", "reaction": "Reação",
}

painel = staff_member_required(login_url="/painel/login/")


def _texto(m):
    if m.texto:
        return m.texto
    return ROTULOS.get(m.tipo, f"[{m.tipo or 'mensagem'}]") + " (ainda não abre no painel)"


def _msg_json(m):
    return {
        "id": m.id,
        "de": "cliente" if m.direcao == Mensagem.ENTRADA else ("robo" if m.tipo in ("robo", "falha") else "equipe"),
        "texto": _texto(m),
        "via_app": m.tipo == "app",
        "falhou": m.tipo == "falha",
        "hora": timezone.localtime(m.criado_em).strftime("%d/%m %H:%M"),
    }


def _janela_aberta(contato):
    ultima = contato.mensagens.filter(direcao=Mensagem.ENTRADA).aggregate(u=Max("criado_em"))["u"]
    return bool(ultima and timezone.now() - ultima < JANELA)


def _status(contato):
    return {
        "robo_pausado": contato.robo_pausado,
        "pausado_ate": timezone.localtime(contato.robo_pausado_ate).strftime("%d/%m %H:%M") if contato.robo_pausado else "",
        "janela_aberta": _janela_aberta(contato),
    }


@painel
@require_GET
def caixa(request):
    return render(request, "bot/caixa.html", {"pausa_horas": settings.PAUSA_HUMANO_HORAS})


@painel
@require_GET
def api_conversas(request):
    busca = (request.GET.get("q") or "").strip()
    qs = Contato.objects.annotate(
        nao_lidas=Count("mensagens", filter=Q(mensagens__direcao=Mensagem.ENTRADA)
                        & (Q(lido_ate__isnull=True) | Q(mensagens__criado_em__gt=F("lido_ate")))),
        ultima_em=Max("mensagens__criado_em"),
    ).order_by("-ultima_em")
    if busca:
        qs = qs.filter(Q(nome__icontains=busca) | Q(wa_id__icontains=busca))
    conversas = []
    for c in qs[:100]:
        ultima = c.mensagens.order_by("-criado_em").first()
        conversas.append({
            "id": c.id,
            "nome": c.nome or "Sem nome",
            "numero": c.wa_id,
            "interesse": c.interesse,
            "quer_orcamento": c.quer_orcamento,
            "robo_pausado": c.robo_pausado,
            "nao_lidas": c.nao_lidas,
            "ultima": (("Você: " if ultima.direcao == Mensagem.SAIDA and ultima.tipo not in ("robo", "falha") else "")
                       + _texto(ultima))[:90] if ultima else "",
            "hora": timezone.localtime(c.ultima_em).strftime("%d/%m %H:%M") if c.ultima_em else "",
        })
    return JsonResponse({"conversas": conversas})


@painel
@require_GET
def api_mensagens(request, pk):
    contato = get_object_or_404(Contato, pk=pk)
    depois = int(request.GET.get("depois") or 0)
    msgs = contato.mensagens.filter(id__gt=depois).order_by("criado_em", "id")
    if not depois:
        msgs = list(msgs)[-300:]
    contato.lido_ate = timezone.now()
    contato.save(update_fields=["lido_ate"])
    return JsonResponse({
        "contato": {"id": contato.id, "nome": contato.nome or "Sem nome", "numero": contato.wa_id,
                    "interesse": contato.interesse, "quer_orcamento": contato.quer_orcamento},
        "status": _status(contato),
        "mensagens": [_msg_json(m) for m in msgs],
    })


@painel
@require_POST
def api_enviar(request, pk):
    contato = get_object_or_404(Contato, pk=pk)
    texto = (request.POST.get("texto") or "").strip()
    if not texto:
        return JsonResponse({"erro": "Escreva uma mensagem antes de enviar."}, status=400)
    if len(texto) > 4096:
        return JsonResponse({"erro": "A mensagem passou de 4.096 caracteres, o limite do WhatsApp."}, status=400)
    if not _janela_aberta(contato):
        return JsonResponse({"erro": "Já passaram 24 h desde a última mensagem do cliente. Pela regra do "
                                     "WhatsApp, só dá para responder depois que ele mandar uma nova mensagem."},
                            status=400)
    mid = whatsapp.enviar_texto(contato.wa_id, texto)
    if not mid:
        return JsonResponse({"erro": "O WhatsApp recusou o envio. Tente de novo; se continuar, veja os logs do Render."},
                            status=502)
    m = Mensagem.objects.create(contato=contato, direcao=Mensagem.SAIDA, wa_message_id=mid, tipo="humano", texto=texto)
    contato.pausar_robo(settings.PAUSA_HUMANO_HORAS)  # quem responde agora é uma pessoa
    contato.lido_ate = timezone.now()
    contato.save(update_fields=["lido_ate"])
    return JsonResponse({"mensagem": _msg_json(m), "status": _status(contato)})


@painel
@require_POST
def api_robo(request, pk):
    contato = get_object_or_404(Contato, pk=pk)
    if request.POST.get("acao") == "pausar":
        contato.pausar_robo(settings.PAUSA_HUMANO_HORAS)
    else:
        contato.robo_pausado_ate = None
        contato.save(update_fields=["robo_pausado_ate", "atualizado_em"])
    return JsonResponse({"status": _status(contato)})

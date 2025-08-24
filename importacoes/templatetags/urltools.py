# importacoes/templatetags/urltools.py
from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def urlparams(context, **kwargs):
    """
    Monta a querystring preservando request.GET e alterando/removendo chaves passadas.
    Uso no template:
      href="{% urlparams page=3 %}"           -> "?q=foo&vehicle=1&page=3"
      href="{% urlparams page=None %}"        -> "?q=foo&vehicle=1"  (remove 'page')
      href="{% urlparams page=1 q='economia' %}"
    """
    request = context.get("request")
    if request is None:
        return ""
    params = request.GET.copy()

    for k, v in kwargs.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = v

    encoded = params.urlencode()
    return f"?{encoded}" if encoded else ""

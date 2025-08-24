from django import template

register = template.Library()

def _merge_classes(existing: str | None, new: str | None) -> str:
    ex = (existing or "").strip()
    nw = (new or "").strip()
    if not ex:
        return nw
    if not nw:
        return ex
    have = set(ex.split())
    add = [c for c in nw.split() if c and c not in have]
    return (ex + (" " + " ".join(add) if add else "")).strip()

@register.filter
def addattrs(field, arg: str):
    """
    Adiciona múltiplos atributos ao widget do campo.
    Sintaxe: "chave=valor|chave2=valor2|attrbool"
    Exemplos:
      {{ form.url|addattrs:"class=form-control|placeholder=https://..." }}
      {{ form.enabled|addattrs:"class=form-check-input" }}
    Observação: se 'class' existir, as classes são mescladas (não sobrescreve).
    """
    # Se já estiver renderizado (SafeString), devolve como está
    if not hasattr(field, "as_widget") or not hasattr(field, "field"):
        return field

    attrs = dict(field.field.widget.attrs or {})
    for pair in str(arg).split("|"):
        pair = pair.strip()
        if not pair:
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "class":
                attrs["class"] = _merge_classes(attrs.get("class"), v)
            else:
                attrs[k] = v
        else:
            # atributo booleano (ex.: required, autofocus)
            attrs[pair] = pair
    return field.as_widget(attrs=attrs)

import streamlit as st
from i18n.en import STRINGS as EN
from i18n.mr import STRINGS as MR

_LANGS = {"en": EN, "mr": MR}


def t(key: str, **kwargs) -> str:
    lang = st.session_state.get("lang", "en")
    strings = _LANGS.get(lang, EN)
    text = strings.get(key) or EN.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

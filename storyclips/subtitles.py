"""Subtítulos ASS palabra por palabra (la palabra que se dice, resaltada) y tarjetas de texto."""

from __future__ import annotations

from collections.abc import Sequence

from storyclips.models import Word

_WHITE, _YELLOW = "&HFFFFFF&", "&H00E5FF&"  # ASS usa BGR


def ass_time(seconds: float) -> str:
    cs = round(seconds * 100)
    h, rest = divmod(cs, 360000)
    m, rest = divmod(rest, 6000)
    s, c = divmod(rest, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _escape(text: str) -> str:
    """Las llaves y la barra invertida son sintaxis de ASS: se neutralizan."""
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _groups(words: Sequence[Word], size: int) -> list[list[Word]]:
    return [list(words[i : i + size]) for i in range(0, len(words), size)]


def build_ass(
    words: Sequence[Word],
    *,
    width: int = 1080,
    height: int = 1920,
    group: int = 3,
    font: str = "Arial",
    cards: Sequence[tuple[float, float, str]] = (),
) -> str:
    """Un evento por palabra mostrando su grupo de `group` palabras con la actual resaltada.

    `cards` son textos grandes arriba (inicio, fin, texto): «PARTE 1» y «Parte 2 en el siguiente video».
    """
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Word,{font},96,{_WHITE},{_WHITE},&H000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,7,2,5,60,60,0,1\n"
        f"Style: Card,{font},78,{_YELLOW},{_YELLOW},&H000000&,&H80000000&,-1,0,0,0,100,100,0,0,1,6,2,8,60,60,260,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events: list[str] = []
    for chunk in _groups(words, group):
        for i, current in enumerate(chunk):
            end = chunk[i + 1].start if i + 1 < len(chunk) else current.end
            text = " ".join(
                f"{{\\c{_YELLOW}}}{_escape(w.text)}{{\\c{_WHITE}}}" if j == i else _escape(w.text)
                for j, w in enumerate(chunk)
            )
            events.append(
                f"Dialogue: 0,{ass_time(current.start)},{ass_time(end)},Word,,0,0,0,,{text}"
            )
    for start, end, text in cards:
        events.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Card,,0,0,0,,{_escape(text)}")
    return header + "\n".join(events) + "\n"

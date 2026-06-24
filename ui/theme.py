"""Light professional theme (spec §7.1): qt-material light + the spec's palette tokens."""
from __future__ import annotations

PALETTE = {
    "accent": "#3455FA",
    "bg": "#FFFFFF",
    "text": "#000000",
    "secondary": "#555555",
    "border": "#E0E0E0",
    "success": "#34A853",   # progress bar
    "error": "#EA4335",
}

_EXTRA_QSS = f"""
QWidget {{ background: {PALETTE['bg']}; color: {PALETTE['text']}; }}
QLabel#secondary {{ color: {PALETTE['secondary']}; }}
QFrame[divider="true"] {{ border: 1px solid {PALETTE['border']}; }}
QProgressBar {{ border: 1px solid {PALETTE['border']}; border-radius: 4px; text-align: center; }}
QProgressBar::chunk {{ background: {PALETTE['success']}; }}
QPushButton#primary {{ background: {PALETTE['accent']}; color: white;
                       padding: 6px 14px; border-radius: 4px; }}
QLabel#error {{ color: {PALETTE['error']}; }}
"""


def apply_theme(app) -> None:
    try:
        from qt_material import apply_stylesheet
        apply_stylesheet(app, theme="light_blue.xml", invert_secondary=True)
    except Exception:
        pass  # fallback: palette QSS below still applies the required tokens
    app.setStyleSheet(app.styleSheet() + _EXTRA_QSS)

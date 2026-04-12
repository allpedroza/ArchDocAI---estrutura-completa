"""
Layer 2 - Analysis: Generate architecture diagrams from AnalysisResult.

Primary renderer: matplotlib — full layout control, professional horizontal-band design.
Secondary renderer: diagrams (mingrammer) — opt-in via generate_png(use_diagrams=True).

Also exports Mermaid markup for embedding in docs.
"""

import math
import textwrap
from pathlib import Path
from dataclasses import dataclass
from .analyzer import AnalysisResult

# ---------------------------------------------------------------------------
# Color palette – one accent per layer (cycles if more layers than colors)
# ---------------------------------------------------------------------------
DEFAULT_COLORS = [
    "#2563eb",  # blue
    "#16a34a",  # green
    "#9333ea",  # purple
    "#ea580c",  # orange
    "#dc2626",  # red
    "#0891b2",  # cyan
    "#854d0e",  # amber-brown
    "#475569",  # slate
]

# Light pastel fills derived from accent colors (hex 18% opacity approximation)
_PASTEL = [
    "#dbeafe",  # blue-100
    "#dcfce7",  # green-100
    "#f3e8ff",  # purple-100
    "#ffedd5",  # orange-100
    "#fee2e2",  # red-100
    "#cffafe",  # cyan-100
    "#fef3c7",  # amber-100
    "#f1f5f9",  # slate-100
]

# Tech badge colors (text on white)
_TECH_COLORS = [
    "#1d4ed8", "#15803d", "#7e22ce", "#c2410c",
    "#b91c1c", "#0e7490", "#92400e", "#334155",
]

# Short tech abbreviations shown as colored badge inside component card
_TECH_ABBR: dict[str, str] = {
    "python": "PY", "javascript": "JS", "typescript": "TS",
    "go": "GO", "java": "JV", "rust": "RS", "c++": "C+",
    "ruby": "RB", "scala": "SC", "kotlin": "KT", "swift": "SW",
    "fastapi": "FA", "django": "DJ", "flask": "FL", "spring": "SP",
    "react": "RE", "vue": "VU", "angular": "NG", "svelte": "SV",
    "postgresql": "PG", "postgres": "PG", "mysql": "MY", "sqlite": "SQ",
    "mongodb": "MG", "cassandra": "CA", "redis": "RD", "dynamodb": "DY",
    "elasticsearch": "ES", "kafka": "KF", "rabbitmq": "MQ", "celery": "CL",
    "kubernetes": "K8", "k8s": "K8", "docker": "DK", "terraform": "TF",
    "aws": "AW", "gcp": "GC", "azure": "AZ", "s3": "S3",
    "lambda": "λ", "airflow": "AF", "spark": "SP", "flink": "FL",
    "nginx": "NX", "apache": "AP", "graphql": "GQ", "rest": "RS",
    "grpc": "gR", "protobuf": "PB", "jwt": "JW", "oauth": "OA",
    "mlflow": "ML", "pytorch": "PT", "tensorflow": "TF", "sklearn": "SK",
    "pandas": "PD", "numpy": "NP", "dbt": "DB", "bigquery": "BQ",
    "redshift": "RS", "snowflake": "SF", "databricks": "DB",
}

# Layout constants
_FIG_W = 16.0          # figure width in inches
_DPI = 180
_LAYER_ACCENT_W = 0.18  # width of left color accent bar (data units)
_LAYER_HPAD = 0.35      # horizontal padding inside layer band
_LAYER_VPAD = 0.22      # vertical padding top/bottom inside layer band
_TITLE_H = 0.55         # height of layer title row
_COMP_W = 2.6           # component card width
_COMP_H = 1.05          # component card height
_COMP_GAP_X = 0.22      # horizontal gap between cards
_COMP_GAP_Y = 0.2       # vertical gap between card rows
_MAX_PER_ROW = 5        # max cards per row
_LAYER_GAP = 0.32       # gap between consecutive layer bands
_ARROW_H = _LAYER_GAP   # arrow height fits in the gap
_MARGIN = 0.5           # top/bottom figure margin


@dataclass
class DiagramGenerator:
    output_dir: str = "./output"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate_png(self, result: AnalysisResult, filename: str = "architecture.png") -> str:
        """Render a professional horizontal-band architecture PNG."""
        if not result.layers:
            raise ValueError("No layers found in analysis result.")
        return self._render(result, filename)

    # ------------------------------------------------------------------
    # Main renderer
    # ------------------------------------------------------------------

    def _render(self, result: AnalysisResult, filename: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.patches import FancyBboxPatch

        layers = result.layers
        n_layers = len(layers)

        # ── compute layer heights ──────────────────────────────────────
        layer_heights: list[float] = []
        for layer in layers:
            n_comps = len(layer.get("components", []))
            n_rows = max(1, math.ceil(n_comps / _MAX_PER_ROW)) if n_comps > 0 else 0
            cards_h = n_rows * (_COMP_H + _COMP_GAP_Y) - _COMP_GAP_Y if n_rows > 0 else 0
            h = _LAYER_VPAD + _TITLE_H + (cards_h + _LAYER_VPAD if cards_h else _LAYER_VPAD)
            layer_heights.append(h)

        total_h = (
            sum(layer_heights)
            + _LAYER_GAP * (n_layers - 1)
            + 2 * _MARGIN
            + 0.6  # project title
        )

        fig, ax = plt.subplots(figsize=(_FIG_W, total_h))
        fig.patch.set_facecolor("#f8fafc")
        ax.set_facecolor("#f8fafc")
        ax.set_xlim(0, _FIG_W)
        ax.set_ylim(0, total_h)
        ax.axis("off")

        # ── project title ──────────────────────────────────────────────
        ax.text(
            _FIG_W / 2, total_h - _MARGIN * 0.6,
            result.project_name,
            ha="center", va="top",
            fontsize=17, fontweight="bold", color="#0f172a",
            zorder=10,
        )
        ax.text(
            _FIG_W / 2, total_h - _MARGIN * 0.6 - 0.32,
            "Architecture Overview",
            ha="center", va="top",
            fontsize=9, color="#64748b", style="italic",
            zorder=10,
        )

        y_top = total_h - _MARGIN - 0.6  # top of first layer band

        for i, layer in enumerate(layers):
            lh = layer_heights[i]
            accent = layer.get("color") or DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
            pastel = _PASTEL[i % len(_PASTEL)]
            y_bottom = y_top - lh
            band_x = _LAYER_ACCENT_W
            band_w = _FIG_W - _LAYER_ACCENT_W

            # ── layer band background ──────────────────────────────────
            band = FancyBboxPatch(
                (0, y_bottom), _FIG_W, lh,
                boxstyle="round,pad=0.05",
                facecolor=pastel,
                edgecolor=accent + "55",
                linewidth=1.2,
                zorder=1,
            )
            ax.add_patch(band)

            # left accent bar
            accent_bar = mpatches.Rectangle(
                (0, y_bottom), _LAYER_ACCENT_W, lh,
                facecolor=accent, edgecolor="none", zorder=2,
            )
            ax.add_patch(accent_bar)

            # ── layer title ────────────────────────────────────────────
            title_y = y_top - _LAYER_VPAD - _TITLE_H / 2
            ax.text(
                band_x + _LAYER_HPAD, title_y,
                layer["name"],
                ha="left", va="center",
                fontsize=11, fontweight="bold", color="#0f172a",
                zorder=4,
            )

            # layer description (right, italic, dimmed)
            desc = layer.get("description", "")
            if desc:
                short = desc[:80] + ("…" if len(desc) > 80 else "")
                ax.text(
                    _FIG_W - 0.3, title_y,
                    short,
                    ha="right", va="center",
                    fontsize=7.5, style="italic", color="#64748b",
                    zorder=4,
                )

            # divider line under title
            div_y = y_top - _LAYER_VPAD - _TITLE_H
            ax.plot(
                [band_x + _LAYER_HPAD, _FIG_W - _LAYER_HPAD],
                [div_y, div_y],
                color=accent + "55", linewidth=0.8, zorder=3,
            )

            # ── component cards ────────────────────────────────────────
            components = layer.get("components", [])
            if components:
                n_cols = min(len(components), _MAX_PER_ROW)
                # center cards horizontally within the band
                total_cards_w = n_cols * _COMP_W + (n_cols - 1) * _COMP_GAP_X
                x_start = band_x + (band_w - total_cards_w) / 2
                cards_y_top = div_y - _COMP_GAP_Y

                for j, comp in enumerate(components):
                    row = j // n_cols
                    col = j % n_cols
                    cx = x_start + col * (_COMP_W + _COMP_GAP_X)
                    cy_top = cards_y_top - row * (_COMP_H + _COMP_GAP_Y)
                    cy_bottom = cy_top - _COMP_H

                    # card background
                    card = FancyBboxPatch(
                        (cx, cy_bottom), _COMP_W, _COMP_H,
                        boxstyle="round,pad=0.04",
                        facecolor="white",
                        edgecolor=accent + "88",
                        linewidth=1.0,
                        zorder=3,
                    )
                    ax.add_patch(card)

                    # tech badge (top-right corner of card)
                    tech_raw = comp.get("tech", "")
                    abbr = self._tech_abbr(tech_raw)
                    badge_color = accent
                    badge_x = cx + _COMP_W - 0.08
                    badge_y = cy_top - 0.1
                    if abbr:
                        badge_rect = FancyBboxPatch(
                            (badge_x - 0.32, badge_y - 0.22), 0.32, 0.22,
                            boxstyle="round,pad=0.02",
                            facecolor=badge_color,
                            edgecolor="none",
                            zorder=5,
                        )
                        ax.add_patch(badge_rect)
                        ax.text(
                            badge_x - 0.16, badge_y - 0.11,
                            abbr,
                            ha="center", va="center",
                            fontsize=6, fontweight="bold", color="white",
                            zorder=6,
                        )

                    # component name (centered, bold)
                    name = comp.get("name", "")
                    wrap_w = max(14, int(_COMP_W * 8))
                    name_lines = textwrap.wrap(name, width=wrap_w)[:2]
                    name_y = (cy_top + cy_bottom) / 2 + 0.1
                    ax.text(
                        cx + _COMP_W / 2, name_y,
                        "\n".join(name_lines),
                        ha="center", va="center",
                        fontsize=8.5, fontweight="bold", color="#1e293b",
                        linespacing=1.3, zorder=4,
                    )

                    # tech label below name
                    if tech_raw:
                        ax.text(
                            cx + _COMP_W / 2, cy_bottom + 0.14,
                            tech_raw[:26],
                            ha="center", va="bottom",
                            fontsize=7, color="#64748b", style="italic",
                            zorder=4,
                        )

            # ── arrow to next layer ────────────────────────────────────
            if i < n_layers - 1:
                arrow_x = _FIG_W / 2
                arrow_y_start = y_bottom
                arrow_y_end = y_bottom - _LAYER_GAP
                ax.annotate(
                    "",
                    xy=(arrow_x, arrow_y_end + 0.06),
                    xytext=(arrow_x, arrow_y_start),
                    arrowprops=dict(
                        arrowstyle="->, head_width=0.22, head_length=0.1",
                        color="#94a3b8",
                        lw=1.6,
                        connectionstyle="arc3,rad=0",
                    ),
                    zorder=5,
                )

            y_top = y_bottom - _LAYER_GAP

        output_path = Path(self.output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(
            str(output_path), dpi=_DPI, bbox_inches="tight",
            facecolor=fig.get_facecolor(), pad_inches=0.25,
        )
        plt.close()
        return str(output_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _tech_abbr(self, tech: str) -> str:
        """Return a 2-char abbreviation for the tech label, or empty string."""
        if not tech:
            return ""
        key = tech.lower().strip()
        for k, v in _TECH_ABBR.items():
            if k in key:
                return v
        # fallback: first 2 uppercase chars
        letters = [c for c in tech if c.isalpha()]
        return "".join(letters[:2]).upper() if letters else ""

    # ------------------------------------------------------------------
    # Mermaid generation
    # ------------------------------------------------------------------

    def generate_mermaid(self, result: AnalysisResult) -> str:
        """Return a Mermaid flowchart markup string with per-layer colors."""
        lines = ["flowchart TD"]
        prev_id = None
        style_lines: list[str] = []

        for i, layer in enumerate(result.layers):
            lid = layer["id"]
            label = layer["name"].replace('"', "'")
            lines.append(f'    {lid}["{label}"]')

            color = layer.get("color") or DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
            style_lines.append(
                f"    style {lid} fill:{color},stroke:#ffffff22,color:#ffffff,font-weight:bold"
            )

            for comp in layer.get("components", []):
                cid = lid + "_" + comp["name"].replace(" ", "_").lower()[:15]
                clabel = comp["name"].replace('"', "'")
                lines.append(f'    {cid}["{clabel}"]')
                lines.append(f"    {lid} --> {cid}")
                style_lines.append(
                    f"    style {cid} fill:{color}99,stroke:#ffffff33,color:#ffffff"
                )

            if prev_id:
                lines.append(f"    {prev_id} --> {lid}")
            prev_id = lid

        return "\n".join(lines + style_lines)

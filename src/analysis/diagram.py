"""
Layer 2 - Analysis: Generate architecture diagrams from AnalysisResult.

Primary renderer: diagrams (diagrams.mingrammer.com) — icon-based professional output.
Fallback renderer: matplotlib — when diagrams/graphviz is unavailable.

Also exports Mermaid markup for embedding in docs.
"""

import math
import os
import tempfile
import textwrap
from pathlib import Path
from dataclasses import dataclass
from .analyzer import AnalysisResult

# ---------------------------------------------------------------------------
# Icon map: tech keyword -> (module_path, class_name)
# Longest match wins (e.g. "postgresql" beats "post")
# ---------------------------------------------------------------------------
_ICON_MAP: dict[str, tuple[str, str]] = {
    # AWS Storage
    "s3": ("diagrams.aws.storage", "S3"),
    "glacier": ("diagrams.aws.storage", "S3Glacier"),
    # AWS Compute
    "lambda": ("diagrams.aws.compute", "Lambda"),
    "ec2": ("diagrams.aws.compute", "EC2"),
    "ecs": ("diagrams.aws.compute", "ECS"),
    "eks": ("diagrams.aws.compute", "EKS"),
    "fargate": ("diagrams.aws.compute", "Fargate"),
    "sagemaker": ("diagrams.aws.ml", "Sagemaker"),
    "glue": ("diagrams.aws.analytics", "Glue"),
    "athena": ("diagrams.aws.analytics", "Athena"),
    "kinesis": ("diagrams.aws.analytics", "KinesisDataStreams"),
    "redshift": ("diagrams.aws.analytics", "Redshift"),
    "dynamodb": ("diagrams.aws.database", "Dynamodb"),
    "rds": ("diagrams.aws.database", "RDS"),
    "aurora": ("diagrams.aws.database", "Aurora"),
    "elasticache": ("diagrams.aws.database", "ElastiCache"),
    "sqs": ("diagrams.aws.integration", "SQS"),
    "sns": ("diagrams.aws.integration", "SNS"),
    "api gateway": ("diagrams.aws.network", "APIGateway"),
    "cloudfront": ("diagrams.aws.network", "CloudFront"),
    "route53": ("diagrams.aws.network", "Route53"),
    "vpc": ("diagrams.aws.network", "VPC"),
    "load balancer": ("diagrams.aws.network", "ELB"),
    "elb": ("diagrams.aws.network", "ELB"),
    "alb": ("diagrams.aws.network", "ALB"),
    "cloudwatch": ("diagrams.aws.management", "Cloudwatch"),
    "step functions": ("diagrams.aws.integration", "StepFunctions"),
    "eventbridge": ("diagrams.aws.integration", "Eventbridge"),
    # GCP
    "bigquery": ("diagrams.gcp.analytics", "BigQuery"),
    "pubsub": ("diagrams.gcp.analytics", "PubSub"),
    "pub/sub": ("diagrams.gcp.analytics", "PubSub"),
    "dataflow": ("diagrams.gcp.analytics", "Dataflow"),
    "cloud run": ("diagrams.gcp.compute", "Run"),
    "gke": ("diagrams.gcp.compute", "GKE"),
    "cloud storage": ("diagrams.gcp.storage", "GCS"),
    "gcs": ("diagrams.gcp.storage", "GCS"),
    "firestore": ("diagrams.gcp.database", "Firestore"),
    "cloud sql": ("diagrams.gcp.database", "SQL"),
    "spanner": ("diagrams.gcp.database", "Spanner"),
    # Azure
    "blob": ("diagrams.azure.storage", "BlobStorage"),
    "cosmos": ("diagrams.azure.database", "CosmosDb"),
    "azure sql": ("diagrams.azure.database", "SQLDatabases"),
    "service bus": ("diagrams.azure.integration", "ServiceBus"),
    "event hub": ("diagrams.azure.analytics", "EventHubs"),
    "azure function": ("diagrams.azure.compute", "FunctionApps"),
    "aks": ("diagrams.azure.compute", "KubernetesServices"),
    # On-prem databases
    "postgresql": ("diagrams.onprem.database", "Postgresql"),
    "postgres": ("diagrams.onprem.database", "Postgresql"),
    "mysql": ("diagrams.onprem.database", "Mysql"),
    "mongodb": ("diagrams.onprem.database", "MongoDB"),
    "mongo": ("diagrams.onprem.database", "MongoDB"),
    "cassandra": ("diagrams.onprem.database", "Cassandra"),
    "elasticsearch": ("diagrams.onprem.search", "Elasticsearch"),
    "elastic": ("diagrams.onprem.search", "Elasticsearch"),
    "redis": ("diagrams.onprem.inmemory", "Redis"),
    "memcached": ("diagrams.onprem.inmemory", "Memcached"),
    # Queues / streaming
    "kafka": ("diagrams.onprem.queue", "Kafka"),
    "rabbitmq": ("diagrams.onprem.queue", "Rabbitmq"),
    "celery": ("diagrams.onprem.queue", "Celery"),
    "activemq": ("diagrams.onprem.queue", "ActiveMQ"),
    # Orchestration / infra
    "kubernetes": ("diagrams.onprem.container", "K8S"),
    "k8s": ("diagrams.onprem.container", "K8S"),
    "docker": ("diagrams.onprem.container", "Docker"),
    "nginx": ("diagrams.onprem.network", "Nginx"),
    "apache": ("diagrams.onprem.network", "Apache"),
    "haproxy": ("diagrams.onprem.network", "HAProxy"),
    "terraform": ("diagrams.onprem.iac", "Terraform"),
    "ansible": ("diagrams.onprem.iac", "Ansible"),
    "jenkins": ("diagrams.onprem.ci", "Jenkins"),
    "gitlab": ("diagrams.onprem.vcs", "Gitlab"),
    "github": ("diagrams.onprem.vcs", "Github"),
    "grafana": ("diagrams.onprem.monitoring", "Grafana"),
    "prometheus": ("diagrams.onprem.monitoring", "Prometheus"),
    # Programming languages
    "python": ("diagrams.programming.language", "Python"),
    "javascript": ("diagrams.programming.language", "Javascript"),
    "typescript": ("diagrams.programming.language", "Typescript"),
    "go": ("diagrams.programming.language", "Go"),
    "java": ("diagrams.programming.language", "Java"),
    "rust": ("diagrams.programming.language", "Rust"),
    # Frameworks / runtime
    "fastapi": ("diagrams.programming.framework", "FastAPI"),
    "flask": ("diagrams.programming.framework", "Flask"),
    "django": ("diagrams.programming.framework", "Django"),
    "react": ("diagrams.programming.framework", "React"),
    "vue": ("diagrams.programming.framework", "Vue"),
    "angular": ("diagrams.programming.framework", "Angular"),
    "spring": ("diagrams.programming.framework", "Spring"),
    # Networking
    "internet": ("diagrams.onprem.network", "Internet"),
    "firewall": ("diagrams.onprem.network", "Pfsense"),
    # SaaS / generic
    "git": ("diagrams.onprem.vcs", "Git"),
    "airflow": ("diagrams.onprem.workflow", "Airflow"),
    "spark": ("diagrams.onprem.analytics", "Spark"),
    "flink": ("diagrams.onprem.analytics", "Flink"),
    "dbt": ("diagrams.onprem.analytics", "DBT"),
    "mlflow": ("diagrams.onprem.mlops", "Mlflow"),
}

# Fallback by component type field
_TYPE_FALLBACK: dict[str, tuple[str, str]] = {
    "source": ("diagrams.onprem.queue", "Kafka"),
    "store": ("diagrams.onprem.database", "Postgresql"),
    "process": ("diagrams.programming.language", "Python"),
    "api": ("diagrams.onprem.network", "Nginx"),
    "ui": ("diagrams.programming.framework", "React"),
    "infra": ("diagrams.onprem.container", "Docker"),
    "ml": ("diagrams.aws.ml", "Sagemaker"),
    "analytics": ("diagrams.onprem.analytics", "Spark"),
}

# Pastel layer colors for diagrams cluster borders
_CLUSTER_COLORS = [
    "#1a6b4a", "#1a3a5c", "#5a2d82", "#8b3a00",
    "#c0392b", "#2c7a7b", "#6d4c41", "#155799",
]
# Public alias kept for backwards compatibility with existing tests/code
DEFAULT_COLORS = _CLUSTER_COLORS

# ---------------------------------------------------------------------------
# Matplotlib fallback constants
# ---------------------------------------------------------------------------
_MAX_PER_ROW = 4
_COMP_H = 1.6
_COMP_ROW_GAP = 0.2
_TITLE_H = 0.75
_LAYER_PAD = 0.4
_MARGIN_TOP = 0.7
_FIG_W = 18.0
_DPI = 160
_BG = "#111827"
_TEXT = "#f0f4f8"
_SUBTEXT = "#94a3b8"
_MPL_COLORS = [
    "#1a6b4a", "#1a3a5c", "#5a2d82", "#8b3a00",
    "#c0392b", "#2c7a7b", "#6d4c41",
]


def _resolve_icon(comp: dict):
    """Return (module_path, class_name) for a component, or None if no match."""
    haystack = (comp.get("tech", "") + " " + comp.get("name", "")).lower()
    # longest match wins
    best_key = ""
    best_val = None
    for kw, val in _ICON_MAP.items():
        if kw in haystack and len(kw) > len(best_key):
            best_key = kw
            best_val = val
    if best_val:
        return best_val
    # fallback by component type
    ctype = comp.get("type", "").lower()
    return _TYPE_FALLBACK.get(ctype)


def _import_node(module_path: str, class_name: str):
    """Dynamically import a diagrams node class."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


@dataclass
class DiagramGenerator:
    output_dir: str = "./output"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate_png(self, result: AnalysisResult, filename: str = "architecture.png") -> str:
        """Render architecture PNG. Tries diagrams library first, falls back to matplotlib."""
        if not result.layers:
            raise ValueError("No layers found in analysis result.")
        try:
            return self._generate_with_diagrams(result, filename)
        except Exception:
            return self._generate_with_matplotlib(result, filename)

    # ------------------------------------------------------------------
    # diagrams (mingrammer) renderer
    # ------------------------------------------------------------------

    def _generate_with_diagrams(self, result: AnalysisResult, filename: str) -> str:
        from diagrams import Diagram, Cluster, Edge  # type: ignore

        output_path = Path(self.output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # diagrams saves as <outfilename>.png — strip extension from stem
        out_stem = str(output_path.with_suffix(""))

        graph_attr = {
            "bgcolor": "white",
            "splines": "ortho",
            "nodesep": "0.6",
            "ranksep": "0.9",
            "fontsize": "13",
            "fontname": "Helvetica",
            "pad": "0.5",
        }
        node_attr = {
            "fontsize": "11",
            "fontname": "Helvetica",
            "labelloc": "b",
        }

        with Diagram(
            result.project_name,
            filename=out_stem,
            outformat="png",
            show=False,
            direction="TB",
            graph_attr=graph_attr,
            node_attr=node_attr,
        ):
            prev_cluster_nodes: list = []

            for i, layer in enumerate(result.layers):
                color = layer.get("color") or _CLUSTER_COLORS[i % len(_CLUSTER_COLORS)]
                components = layer.get("components", [])

                cluster_attr = {
                    "bgcolor": color + "22",  # very translucent
                    "style": "rounded",
                    "color": color,
                    "penwidth": "2",
                    "fontcolor": color,
                    "fontsize": "12",
                    "fontname": "Helvetica-Bold",
                }

                layer_nodes: list = []
                with Cluster(layer["name"], graph_attr=cluster_attr):
                    if not components:
                        # placeholder node for empty layers
                        try:
                            NodeCls = _import_node("diagrams.onprem.container", "Docker")
                        except Exception:
                            NodeCls = None
                        if NodeCls:
                            node = NodeCls(layer["name"])
                            layer_nodes.append(node)
                    else:
                        for comp in components:
                            icon = _resolve_icon(comp)
                            if icon:
                                try:
                                    NodeCls = _import_node(*icon)
                                    node = NodeCls(comp["name"])
                                    layer_nodes.append(node)
                                except Exception:
                                    pass

                # Connect previous layer to this one
                if prev_cluster_nodes and layer_nodes:
                    prev_cluster_nodes[-1] >> Edge(color="#64748b", style="dashed") >> layer_nodes[0]

                prev_cluster_nodes = layer_nodes

        return str(output_path)

    # ------------------------------------------------------------------
    # matplotlib fallback renderer
    # ------------------------------------------------------------------

    def _generate_with_matplotlib(self, result: AnalysisResult, filename: str) -> str:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyBboxPatch

        layers = result.layers
        n_layers = len(layers)
        if n_layers == 0:
            raise ValueError("No layers found in analysis result.")

        # Pre-compute each layer's height based on component count
        layer_heights = []
        for layer in layers:
            n_comps = len(layer.get("components", []))
            n_rows = max(1, math.ceil(n_comps / _MAX_PER_ROW)) if n_comps > 0 else 0
            if n_rows == 0:
                h = _TITLE_H + 0.4
            else:
                h = _TITLE_H + n_rows * (_COMP_H + _COMP_ROW_GAP) + 0.3
            layer_heights.append(h)

        total_content_h = sum(layer_heights) + (_LAYER_PAD * (n_layers - 1))
        fig_h = total_content_h + _MARGIN_TOP + 0.5

        fig, ax = plt.subplots(figsize=(_FIG_W, fig_h))
        ax.set_xlim(0, _FIG_W)
        ax.set_ylim(0, fig_h)
        ax.axis("off")
        fig.patch.set_facecolor(_BG)

        ax.text(
            _FIG_W / 2, fig_h - 0.15,
            result.project_name,
            ha="center", va="top",
            fontsize=18, fontweight="bold",
            color=_TEXT, zorder=10,
        )

        y_cursor = fig_h - _MARGIN_TOP

        for i, layer in enumerate(layers):
            lh = layer_heights[i]
            color = layer.get("color") or _MPL_COLORS[i % len(_MPL_COLORS)]
            y_bottom = y_cursor - lh

            lpad = 0.25
            rect = FancyBboxPatch(
                (lpad, y_bottom), _FIG_W - 2 * lpad, lh,
                boxstyle="round,pad=0.08",
                facecolor=color, edgecolor="none", alpha=0.92,
                zorder=1,
            )
            ax.add_patch(rect)

            ax.text(
                0.7, y_cursor - 0.12,
                layer["name"].upper(),
                ha="left", va="top",
                fontsize=11, fontweight="bold",
                color=_TEXT, zorder=3, alpha=0.95,
            )

            desc = layer.get("description", "")
            if desc:
                short_desc = desc[:90] + ("..." if len(desc) > 90 else "")
                ax.text(
                    _FIG_W - 0.5, y_cursor - 0.15,
                    short_desc,
                    ha="right", va="top",
                    fontsize=8, style="italic",
                    color=_SUBTEXT, zorder=3, alpha=0.85,
                )

            components = layer.get("components", [])
            if components:
                usable_w = _FIG_W - 2 * lpad - 0.4
                n_per_row = min(len(components), _MAX_PER_ROW)
                slot_w = usable_w / n_per_row
                comp_x0 = lpad + 0.2
                row_y_top = y_cursor - _TITLE_H

                for j, comp in enumerate(components):
                    row = j // n_per_row
                    col = j % n_per_row
                    cx = comp_x0 + col * slot_w + slot_w / 2
                    comp_top = row_y_top - row * (_COMP_H + _COMP_ROW_GAP)
                    comp_bottom = comp_top - _COMP_H

                    box_margin = slot_w * 0.06
                    comp_rect = FancyBboxPatch(
                        (cx - slot_w / 2 + box_margin, comp_bottom + 0.08),
                        slot_w - 2 * box_margin, _COMP_H - 0.16,
                        boxstyle="round,pad=0.06",
                        facecolor="#ffffff15",
                        edgecolor="#ffffff40",
                        linewidth=0.8,
                        zorder=2,
                    )
                    ax.add_patch(comp_rect)

                    wrap_w = max(12, int(slot_w * 5.5))
                    name_lines = textwrap.wrap(comp.get("name", ""), width=wrap_w)[:2]
                    name_y = (comp_top + comp_bottom) / 2 + 0.28
                    ax.text(
                        cx, name_y,
                        "\n".join(name_lines),
                        ha="center", va="center",
                        fontsize=9.5, fontweight="bold",
                        color=_TEXT, zorder=4, linespacing=1.25,
                    )

                    tech = comp.get("tech", "")
                    if tech:
                        ax.text(
                            cx, comp_bottom + 0.22,
                            tech[:28],
                            ha="center", va="bottom",
                            fontsize=7.5, style="italic",
                            color=_SUBTEXT, zorder=4,
                        )

            if i < n_layers - 1:
                arrow_y = y_bottom
                ax.annotate(
                    "", xy=(_FIG_W / 2, arrow_y - _LAYER_PAD + 0.1),
                    xytext=(_FIG_W / 2, arrow_y),
                    arrowprops=dict(
                        arrowstyle="->, head_width=0.25, head_length=0.12",
                        color="#64748b", lw=1.8,
                    ),
                    zorder=5,
                )

            y_cursor = y_bottom - _LAYER_PAD

        output_path = Path(self.output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(
            str(output_path), dpi=_DPI, bbox_inches="tight",
            facecolor=fig.get_facecolor(), pad_inches=0.2,
        )
        plt.close()
        return str(output_path)

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

            color = layer.get("color") or _CLUSTER_COLORS[i % len(_CLUSTER_COLORS)]
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

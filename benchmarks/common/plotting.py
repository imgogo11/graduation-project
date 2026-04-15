from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence


_PALETTE = ["#155E75", "#B45309", "#4D7C0F", "#9A3412", "#1D4ED8", "#BE123C"]


def _load_pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def save_table_image(
    output_path: Path,
    *,
    title: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
) -> None:
    plt = _load_pyplot()
    figure_height = max(3.2, 0.5 * (len(rows) + 2))
    fig, ax = plt.subplots(figsize=(max(8, len(columns) * 1.8), figure_height))
    ax.axis("off")
    table = ax.table(cellText=[list(row) for row in rows], colLabels=list(columns), loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.25)
    ax.set_title(title, fontsize=14, pad=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_grouped_bar_chart(
    output_path: Path,
    *,
    title: str,
    categories: Sequence[str],
    series: Mapping[str, Sequence[float]],
    ylabel: str,
) -> None:
    plt = _load_pyplot()
    fig, ax = plt.subplots(figsize=(12, 6))
    width = 0.8 / max(1, len(series))
    x_positions = list(range(len(categories)))
    for index, (name, values) in enumerate(series.items()):
        offset = (index - (len(series) - 1) / 2.0) * width
        ax.bar([position + offset for position in x_positions], values, width=width, label=name, color=_PALETTE[index % len(_PALETTE)])
    ax.set_xticks(x_positions)
    ax.set_xticklabels(categories, rotation=18, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_line_chart(
    output_path: Path,
    *,
    title: str,
    x_values: Sequence[float],
    series: Mapping[str, Sequence[float]],
    xlabel: str,
    ylabel: str,
) -> None:
    plt = _load_pyplot()
    fig, ax = plt.subplots(figsize=(12, 6))
    for index, (name, values) in enumerate(series.items()):
        ax.plot(x_values, values, marker="o", linewidth=2.0, label=name, color=_PALETTE[index % len(_PALETTE)])
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def save_pie_chart(
    output_path: Path,
    *,
    title: str,
    labels: Sequence[str],
    values: Sequence[float],
    legend_outside: bool = False,
    min_pct_label: float = 0.5,
) -> None:
    plt = _load_pyplot()
    fig, ax = plt.subplots(figsize=((10, 8) if legend_outside else (8, 8)))
    non_zero_pairs = [(label, value) for label, value in zip(labels, values, strict=True) if value > 0]
    if not non_zero_pairs:
        non_zero_pairs = [("No Data", 1.0)]
    labels_to_plot = [label for label, _ in non_zero_pairs]
    values_to_plot = [value for _, value in non_zero_pairs]
    autopct = (lambda pct: (f"{pct:.1f}%" if pct >= min_pct_label else ""))
    wedges, _, _ = ax.pie(
        values_to_plot,
        labels=(None if legend_outside else labels_to_plot),
        autopct=autopct,
        startangle=90,
        colors=_PALETTE[: len(values_to_plot)],
        pctdistance=0.6,
    )
    if legend_outside:
        ax.legend(wedges, labels_to_plot, loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)

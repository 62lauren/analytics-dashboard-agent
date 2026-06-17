import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Default Plotly color sequence — varied and colorful
COLORS = px.colors.qualitative.Plotly

FONT = "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

BASE_LAYOUT = dict(
    font=dict(family=FONT, size=13, color="#1a1a2e"),
    title_font=dict(family=FONT, size=16, color="#1a1a2e", weight="bold" if False else None),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(t=56, b=48, l=56, r=24),
    legend=dict(
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="#e1e4e8",
        borderwidth=1,
        font=dict(size=12),
    ),
    colorway=COLORS,
    xaxis=dict(
        showgrid=False,
        showline=True,
        linecolor="#e1e4e8",
        tickfont=dict(size=12, color="#6b7280"),
        title_font=dict(size=12, color="#6b7280"),
        zeroline=False,
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="#f0f1f3",
        showline=False,
        tickfont=dict(size=12, color="#6b7280"),
        title_font=dict(size=12, color="#6b7280"),
        zeroline=False,
    ),
)


def _apply_base(fig: go.Figure, title: str) -> go.Figure:
    layout = dict(BASE_LAYOUT)
    layout["title"] = dict(
        text=title,
        x=0.02,
        xanchor="left",
        font=dict(family=FONT, size=16, color="#1a1a2e"),
    )
    fig.update_layout(**layout)
    return fig


def build_chart(
    chart_type: str,
    data: list[dict],
    x_field: str,
    y_field: str,
    title: str,
    color_field: str | None = None,
) -> dict:
    if not data:
        return {"data": [], "layout": {"title": {"text": title}}}

    df = pd.DataFrame(data)

    if y_field in df.columns:
        df[y_field] = pd.to_numeric(df[y_field], errors="coerce").fillna(0)

    df = df.dropna(subset=[c for c in [x_field, y_field] if c in df.columns])

    try:
        if chart_type == "bar":
            fig = px.bar(
                df, x=x_field, y=y_field, color=color_field,
                title=title, barmode="group",
                color_discrete_sequence=COLORS,
            )
            fig.update_traces(marker_line_width=0, opacity=0.9)

        elif chart_type == "line":
            fig = px.line(
                df, x=x_field, y=y_field, color=color_field,
                title=title, markers=True,
                color_discrete_sequence=COLORS,
            )
            fig.update_traces(line_width=2.5, marker_size=7)

        elif chart_type == "pie":
            fig = px.pie(
                df, names=x_field, values=y_field, title=title,
                color_discrete_sequence=COLORS,
                hole=0.4,  # donut style looks more modern
            )
            fig.update_traces(
                textposition="outside",
                textinfo="percent+label",
                marker_line_color="white",
                marker_line_width=2,
            )

        elif chart_type == "scatter":
            fig = px.scatter(
                df, x=x_field, y=y_field, color=color_field,
                title=title,
                color_discrete_sequence=COLORS,
            )
            fig.update_traces(marker_size=9, marker_line_width=1, marker_line_color="white")

        elif chart_type == "funnel":
            fig = px.funnel(
                df, x=y_field, y=x_field, title=title,
                color_discrete_sequence=COLORS,
            )

        elif chart_type == "heatmap":
            if color_field and color_field in df.columns:
                pivot = df.pivot_table(
                    values=y_field, index=x_field, columns=color_field, aggfunc="sum"
                ).fillna(0)
                fig = px.imshow(
                    pivot, title=title, text_auto=True,
                    color_continuous_scale="Blues",
                )
            else:
                fig = px.bar(df, x=x_field, y=y_field, title=title, color_discrete_sequence=COLORS)

        else:
            fig = px.bar(df, x=x_field, y=y_field, title=title, color_discrete_sequence=COLORS)

    except Exception:
        fig = px.bar(df, x=x_field, y=y_field, title=title, color_discrete_sequence=COLORS)

    _apply_base(fig, title)
    fig_dict = json.loads(fig.to_json())
    return {"data": fig_dict["data"], "layout": fig_dict["layout"]}

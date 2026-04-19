"""
Software Supply Chain Risk Detector — Streamlit App

Analyzes a PyPI package by building its dependency graph, extracting features,
and scoring it against four clustering models:
  1. Baseline          — K-Means on raw PyPI metadata (20-dim)
  2. Baseline + PCA    — K-Means on PCA-reduced metadata
  3. Raw Graph         — K-Means on full graph features (27-dim)
  4. GNN               — K-Means on GraphSAGE embeddings (32-dim, via GCL)
"""

from __future__ import annotations

import os
import sys
import warnings

# ── path setup ────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import joblib
import numpy as np
import pandas as pd
import streamlit as st
import torch

warnings.filterwarnings("ignore")

from models.gnn_encoder import GraphSAGEEncoder
from models.graph_utils import build_pyg_data
from scripts.FeatureGenerator import PACKAGE_FEATURE_NAMES, FeatureGenerator
from scripts.GraphGenerator import GraphGenerator, configure_dependency_cache

# ── paths ─────────────────────────────────────────────────────────────────────
MODELS_DIR = os.path.join(ROOT_DIR, "models", "lib")
DATA_DIR = os.path.join(ROOT_DIR, "data")

_DEPS_CACHE = os.path.join(DATA_DIR, "depsdev_deps_cache.json")
_PYPI_CACHE = os.path.join(DATA_DIR, "package_metadata_cache.csv")

# ── model registry ────────────────────────────────────────────────────────────
_STRUCTURAL_NAMES = [
    "in_degree", "out_degree", "depth_from_root",
    "is_leaf", "is_shared", "graph_node_count", "graph_edge_count",
]
ALL_FEATURE_NAMES = PACKAGE_FEATURE_NAMES + _STRUCTURAL_NAMES

MODEL_REGISTRY: dict[str, dict] = {
    "Baseline": {
        "label": "Baseline",
        "description": "K-Means on raw PyPI metadata (20 features, no graph)",
        "uses_gnn": False,
        "feature_slice": slice(0, 20),
        "artifacts": {
            "imputer": "baseline_imputer.pkl",
            "scaler": "baseline_scaler.pkl",
            "kmeans": "baseline_kmeans.pkl",
            "risk_csv": "cluster_risk_scores.csv",
        },
    },
    "Baseline + PCA": {
        "label": "Baseline + PCA",
        "description": "K-Means on PCA-reduced graph features (27-dim → lower-dim projection)",
        "uses_gnn": False,
        "feature_slice": slice(0, 27),
        "artifacts": {
            "scaler": "pca_scaler.pkl",
            "pca": "pca_transformer.pkl",
            "kmeans": "pca_kmeans.pkl",
            "risk_csv": "pca_cluster_risk_scores.csv",
        },
    },
    "Raw Graph": {
        "label": "Raw Graph Features",
        "description": "K-Means on full graph features (27-dim: 20 metadata + 7 structural)",
        "uses_gnn": False,
        "feature_slice": slice(0, 27),
        "artifacts": {
            "scaler": "raw_graph_scaler.pkl",
            "kmeans": "raw_graph_kmeans.pkl",
            "risk_csv": "raw_graph_cluster_risk_scores.csv",
        },
    },
    "GNN": {
        "label": "GNN (GraphSAGE + GCL)",
        "description": "K-Means on 32-dim embeddings from GraphSAGE trained with Graph Contrastive Learning",
        "uses_gnn": True,
        "feature_slice": slice(0, 27),
        "gnn_kwargs": dict(
            in_channels=27,
            hidden_channels=64,
            out_channels=32,
            num_layers=2,
        ),
        "artifacts": {
            "encoder": "gnn_encoder.pt",
            "scaler": "gnn_scaler.pkl",
            "kmeans": "gnn_kmeans.pkl",
            "risk_csv": "gnn_cluster_risk_scores.csv",
        },
    },
}


# ── resource loading (cached once per session) ────────────────────────────────

@st.cache_resource(show_spinner="Loading models…")
def load_models() -> dict:
    loaded: dict[str, dict] = {}
    for key, cfg in MODEL_REGISTRY.items():
        arts = cfg["artifacts"]
        m: dict = {}

        if "imputer" in arts:
            m["imputer"] = joblib.load(os.path.join(MODELS_DIR, arts["imputer"]))
        if "pca" in arts:
            m["pca"] = joblib.load(os.path.join(MODELS_DIR, arts["pca"]))
        if "encoder" in arts:
            encoder = GraphSAGEEncoder(**cfg["gnn_kwargs"])
            state = torch.load(
                os.path.join(MODELS_DIR, arts["encoder"]),
                map_location="cpu",
                weights_only=False,
            )
            encoder.load_state_dict(state)
            encoder.eval()
            m["encoder"] = encoder

        m["scaler"] = joblib.load(os.path.join(MODELS_DIR, arts["scaler"]))
        m["kmeans"] = joblib.load(os.path.join(MODELS_DIR, arts["kmeans"]))
        m["risk_df"] = pd.read_csv(os.path.join(MODELS_DIR, arts["risk_csv"]))
        loaded[key] = m
    return loaded


# ── pipeline ──────────────────────────────────────────────────────────────────

def _parse_input(raw: str) -> tuple[str, str] | None:
    raw = raw.strip()
    if "@" not in raw:
        return None
    pkg, _, ver = raw.rpartition("@")
    if not pkg or not ver:
        return None
    return pkg, ver


def _build_graph_and_features(
    package_name: str,
    version: str,
    status_fn,
) -> tuple[dict, str | None]:
    """Return (graph_data dict, error_message)."""
    configure_dependency_cache(_DEPS_CACHE)

    status_fn("Fetching dependency graph from deps.dev…")
    try:
        gg = GraphGenerator(package_name, version)
    except Exception as exc:
        return {}, f"Could not build dependency graph: {exc}"

    root_id: str = gg.levels[0][0] if gg.levels and gg.levels[0] else f"{package_name}@{version}"

    status_fn(f"Extracting features for {len(gg.nodes_map)} nodes…")
    fg = FeatureGenerator(system="pypi", cache_path=_PYPI_CACHE)
    features_dict: dict[str, list[float]] = {}
    for pkg_id in gg.nodes_map:
        try:
            res = fg.get_full_features(pkg_id, gg.nodes_map)
            features_dict[pkg_id] = res["full_metadata"]
        except Exception:
            features_dict[pkg_id] = [0.0] * 27

    root_features = features_dict.get(root_id, [0.0] * 27)

    return {
        "root_id": root_id,
        "nodes_map": gg.nodes_map,
        "features_dict": features_dict,
        "root_features": root_features,
        "graph_node_count": len(gg.nodes_map),
        "levels": gg.levels,
    }, None


def _score_one_model(
    key: str,
    cfg: dict,
    m: dict,
    graph_data: dict,
) -> dict:
    """Run a single model and return a result dict."""
    root_feats = graph_data["root_features"]
    feat_slice = cfg["feature_slice"]
    X_raw = np.array(root_feats[feat_slice], dtype=np.float64).reshape(1, -1)

    # Replace NaN/Inf with zero before any transformations
    X_raw = np.nan_to_num(X_raw, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float64)

    if key == "Baseline":
        X = m["imputer"].transform(X_raw)
        X = m["scaler"].transform(X)

    elif key == "Baseline + PCA":
        X = m["scaler"].transform(X_raw)
        X = m["pca"].transform(X)

    elif key == "Raw Graph":
        X = m["scaler"].transform(X_raw)

    elif key == "GNN":
        data, root_idx = build_pyg_data(
            graph_data["nodes_map"],
            graph_data["features_dict"],
            graph_data["root_id"],
        )
        with torch.no_grad():
            h = m["encoder"](data.x, data.edge_index)
            root_emb = h[root_idx].numpy().reshape(1, -1)
        X = m["scaler"].transform(root_emb)

    else:
        raise ValueError(f"Unknown model key: {key}")

    # Cast to match the dtype KMeans was trained with to avoid Cython buffer mismatch
    X = X.astype(m["kmeans"].cluster_centers_.dtype)
    cluster = int(m["kmeans"].predict(X)[0])
    row = m["risk_df"][m["risk_df"]["cluster"] == cluster]
    if row.empty:
        return {"cluster": cluster, "risk_score": 0.0, "cluster_size": 0, "n_vulnerable": 0}

    return {
        "cluster": cluster,
        "risk_score": float(row["risk_score"].values[0]),
        "cluster_size": int(row["cluster_size"].values[0]),
        "n_vulnerable": int(row["n_vulnerable"].values[0]),
    }


def _score_all_models(graph_data: dict, models: dict) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for key, cfg in MODEL_REGISTRY.items():
        try:
            results[key] = _score_one_model(key, cfg, models[key], graph_data)
        except Exception as exc:
            results[key] = {"error": str(exc)}
    return results


# ── UI helpers ────────────────────────────────────────────────────────────────

def _risk_color(score: float) -> str:
    if score >= 0.7:
        return "#e53935"   # red
    if score >= 0.35:
        return "#fb8c00"   # orange
    return "#43a047"        # green


def _risk_label(score: float) -> str:
    if score >= 0.7:
        return "HIGH"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _render_score_card(col, model_key: str, result: dict) -> None:
    cfg = MODEL_REGISTRY[model_key]
    with col:
        st.markdown(f"**{cfg['label']}**")
        st.caption(cfg["description"])

        if "error" in result:
            st.error(result["error"])
            return

        score = result["risk_score"]
        color = _risk_color(score)
        label = _risk_label(score)

        st.markdown(
            f"""
            <div style="
                background:{color}22;
                border-left:4px solid {color};
                border-radius:6px;
                padding:12px 16px;
                margin-bottom:8px;
            ">
                <span style="font-size:2rem;font-weight:700;color:{color}">
                    {score:.1%}
                </span>
                <span style="font-size:0.9rem;color:{color};margin-left:8px;font-weight:600">
                    {label}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(score)
        st.caption(
            f"Cluster {result['cluster']} · "
            f"{result['n_vulnerable']:,} / {result['cluster_size']:,} known vulnerable"
        )


# ── page ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Supply Chain Risk Detector",
        page_icon="🔍",
        layout="wide",
    )

    st.title("Software Supply Chain Risk Detector")
    st.caption(
        "Enter a PyPI package to analyze its dependency graph and score its "
        "risk level using four clustering-based models."
    )

    # ── input row ─────────────────────────────────────────────────────────────
    col_input, col_btn = st.columns([4, 1])
    with col_input:
        raw_input = st.text_input(
            "Package",
            placeholder="package@version  (e.g. requests@2.28.0)",
            label_visibility="collapsed",
        )
    with col_btn:
        run = st.button("Analyze", type="primary", use_container_width=True)

    st.divider()

    if not run or not raw_input:
        st.info(
            "Enter a `package@version` above and click **Analyze**. "
            "The tool will build the dependency graph (up to depth 3), "
            "extract 27 features per node, and score the root package "
            "with all four models."
        )
        return

    # ── validate input ────────────────────────────────────────────────────────
    parsed = _parse_input(raw_input)
    if parsed is None:
        st.error("Invalid input. Use the format `package@version`, e.g. `numpy@1.26.0`.")
        return

    package_name, version = parsed
    models = load_models()

    # ── pipeline ──────────────────────────────────────────────────────────────
    status_placeholder = st.empty()

    def update_status(msg: str) -> None:
        status_placeholder.info(f"⏳ {msg}")

    with st.spinner("Running pipeline…"):
        graph_data, err = _build_graph_and_features(package_name, version, update_status)

    if err:
        status_placeholder.empty()
        st.error(err)
        return

    update_status("Scoring with all four models…")
    risk_results = _score_all_models(graph_data, models)
    status_placeholder.empty()

    # ── summary header ────────────────────────────────────────────────────────
    st.subheader(f"Results for `{graph_data['root_id']}`")
    st.caption(
        f"Dependency graph: **{graph_data['graph_node_count']} nodes** across "
        f"{len(graph_data['levels'])} BFS levels"
    )

    # ── score cards ───────────────────────────────────────────────────────────
    cols = st.columns(len(MODEL_REGISTRY))
    for col, key in zip(cols, MODEL_REGISTRY):
        _render_score_card(col, key, risk_results[key])

    st.divider()

    # ── aggregate risk ────────────────────────────────────────────────────────
    valid_scores = [
        r["risk_score"]
        for r in risk_results.values()
        if "error" not in r
    ]
    if valid_scores:
        avg_score = float(np.mean(valid_scores))
        agg_color = _risk_color(avg_score)
        agg_label = _risk_label(avg_score)
        st.markdown(
            f"**Aggregate risk (mean across models):** "
            f"<span style='color:{agg_color};font-weight:700'>"
            f"{avg_score:.1%} — {agg_label}</span>",
            unsafe_allow_html=True,
        )

    # ── detail table ──────────────────────────────────────────────────────────
    with st.expander("Model Detail Table", expanded=False):
        rows = []
        for key, result in risk_results.items():
            cfg = MODEL_REGISTRY[key]
            if "error" in result:
                rows.append({
                    "Model": cfg["label"],
                    "Risk Score": "—",
                    "Risk Level": "ERROR",
                    "Cluster": "—",
                    "Cluster Size": "—",
                    "Known Vulnerable": "—",
                    "Uses GNN": cfg["uses_gnn"],
                })
            else:
                rows.append({
                    "Model": cfg["label"],
                    "Risk Score": f"{result['risk_score']:.4f}",
                    "Risk Level": _risk_label(result["risk_score"]),
                    "Cluster": result["cluster"],
                    "Cluster Size": result["cluster_size"],
                    "Known Vulnerable": result["n_vulnerable"],
                    "Uses GNN": cfg["uses_gnn"],
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── feature summary ───────────────────────────────────────────────────────
    with st.expander("Feature Summary (root package)", expanded=False):
        root_feats = graph_data["root_features"]
        feat_df = pd.DataFrame(
            {
                "Feature": ALL_FEATURE_NAMES[: len(root_feats)],
                "Type": (
                    ["metadata"] * len(PACKAGE_FEATURE_NAMES)
                    + ["structural"] * len(_STRUCTURAL_NAMES)
                )[: len(root_feats)],
                "Value": root_feats,
            }
        )
        st.dataframe(feat_df, use_container_width=True, hide_index=True)

    # ── graph overview ────────────────────────────────────────────────────────
    with st.expander("Dependency Graph Overview", expanded=False):
        nodes_map = graph_data["nodes_map"]
        levels = graph_data["levels"]

        level_data = [
            {"BFS Level": i, "Packages": len(lvl), "Example": lvl[0] if lvl else ""}
            for i, lvl in enumerate(levels)
        ]
        st.dataframe(pd.DataFrame(level_data), use_container_width=True, hide_index=True)

        # List direct dependencies of root
        root_node = nodes_map.get(graph_data["root_id"])
        if root_node and root_node.depends_on:
            direct_deps = sorted(root_node.depends_on)
            st.markdown(f"**Direct dependencies ({len(direct_deps)}):**")
            dep_cols = st.columns(min(3, len(direct_deps)))
            for i, dep in enumerate(direct_deps[:12]):
                dep_cols[i % 3].code(dep)
            if len(direct_deps) > 12:
                st.caption(f"… and {len(direct_deps) - 12} more")


if __name__ == "__main__":
    main()

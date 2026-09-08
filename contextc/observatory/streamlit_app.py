"""M16 read-only local Observatory. Presentation only; compiler semantics live in services."""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from contextc.canonical import to_canonical_primitive
from contextc.release_demos.models import DemoRunResult
from contextc.release_demos.service import DemoService


def _service() -> DemoService:
    return DemoService()


def _json(value: object) -> None:
    st.json(to_canonical_primitive(value), expanded=False)


def _demo_picker(service: DemoService, *, key: str) -> str:
    demos = service.list_demos()
    labels = {item.demo_id: f"{item.title} ({item.demo_id})" for item in demos}
    return str(
        st.selectbox(
            "Demo",
            options=tuple(labels),
            format_func=lambda demo_id: labels[str(demo_id)],
            key=key,
        )
    )


def _run(
    service: DemoService,
    demo_id: str,
    *,
    strategy: str | None = None,
    budget: int | None = None,
    target: str | None = None,
) -> DemoRunResult:
    with st.spinner("Running bounded offline demo..."):
        return service.run_demo(demo_id, strategy=strategy, budget=budget, target=target)


def _landing(service: DemoService) -> None:
    st.title("Context Compiler Observatory")
    st.write(
        "A local, read-only view of dependency-aware, provenance-preserving context compilation "
        "and static analysis evidence."
    )
    st.info(
        "Release demos are offline and bounded. The Observatory does not execute MCP tools, "
        "does not mutate repositories, and does not require telemetry or paid APIs."
    )
    for demo in service.list_demos():
        with st.container(border=True):
            st.subheader(demo.title)
            st.caption(f"{demo.demo_id} · {demo.kind.value} · profile {demo.profile_version}")
            st.write(demo.description)
    st.subheader("Current limitations")
    st.write(
        "The four release demos are intentionally small. Full development benchmarks, the complete "
        "M11 Git-bundle study, and live MCP validation are separate validation assets."
    )


def _compile(service: DemoService) -> None:
    st.title("Compile")
    demo_id = _demo_picker(service, key="compile-demo")
    demo = service.descriptor(demo_id)
    if demo.kind.value == "capability_composition":
        st.text_input("Target", value=demo.default_target, disabled=True)
        st.text_input("Strategy", value=demo.default_strategy, disabled=True)
        st.number_input("Budget", value=demo.default_budget, disabled=True)
        result = _run(service, demo_id)
    else:
        target = str(
            st.selectbox(
                "Target",
                options=("generic", "structured-json"),
                index=0 if demo.default_target == "generic" else 1,
            )
        )
        strategies = (
            "auto",
            "naive",
            "recency",
            "relevance_greedy",
            "density_greedy",
            "graph_closure_greedy",
            "brute_force",
            "dynamic_programming",
        )
        strategy = str(
            st.selectbox(
                "Strategy",
                options=strategies,
                index=strategies.index(demo.default_strategy),
            )
        )
        budget = int(
            st.number_input(
                "Budget",
                min_value=64,
                max_value=20000,
                value=max(64, demo.default_budget),
                step=32,
            )
        )
        result = _run(
            service,
            demo_id,
            strategy=strategy,
            budget=budget,
            target=target,
        )
    st.metric("Final tokens", str(result.compile.get("final_token_count", "n/a")))
    st.metric("Optimizer status", str(result.compile.get("optimizer_status", "static")))
    st.subheader("Compile evidence")
    _json(result.compile)


def _graph(service: DemoService) -> None:
    st.title("Graph")
    demo_id = _demo_picker(service, key="graph-demo")
    result = _run(service, demo_id)
    graph = result.graph
    nodes = graph.get("nodes", ())
    edges = graph.get("edges", ())
    selected_only = st.checkbox("Selected-only nodes", value=False)
    if selected_only and isinstance(nodes, tuple):
        nodes = tuple(
            item for item in nodes if isinstance(item, Mapping) and item.get("selected") is True
        )
    st.subheader("Nodes")
    st.dataframe(to_canonical_primitive(nodes), use_container_width=True)
    st.subheader("Typed edges")
    st.dataframe(to_canonical_primitive(edges), use_container_width=True)
    st.caption(f"Graph identity: {graph.get('graph_identity', 'n/a')}")


def _comparison(service: DemoService) -> None:
    st.title("Comparison")
    st.write(
        "The packaged repository demo compares strategies on one equal-footing fingerprint and "
        "reports raw M6 metrics without claiming a universal winner."
    )
    result = _run(service, "repository-bug")
    comparison = result.comparison
    st.caption(f"Fingerprint: {comparison.get('equal_footing_fingerprint', 'n/a')}")
    st.dataframe(
        to_canonical_primitive(comparison.get("rows", ())),
        use_container_width=True,
    )
    st.info(str(comparison.get("claim", "")))


def _reproduction(service: DemoService) -> None:
    st.title("Reproduction")
    demo_id = _demo_picker(service, key="reproduction-demo")
    result = _run(service, demo_id)
    _json(result.reproduction)


def _security(service: DemoService) -> None:
    st.title("Security")
    demo_id = _demo_picker(service, key="security-demo")
    result = _run(service, demo_id)
    st.warning(
        "Security evidence is structural/static. It does not claim complete prompt-injection or "
        "exfiltration prevention."
    )
    _json(result.security)


def _incremental_capabilities(service: DemoService) -> None:
    st.title("Incremental + capabilities")
    demo_id = str(
        st.radio(
            "View",
            options=("incremental-rebuild", "capability-composition"),
            horizontal=True,
        )
    )
    result = _run(service, demo_id)
    _json(result.incremental_capabilities)


def main() -> None:
    st.set_page_config(page_title="Context Compiler Observatory", layout="wide")
    service = _service()
    page = str(
        st.sidebar.radio(
            "Observatory",
            options=(
                "Landing / demos",
                "Compile",
                "Graph",
                "Comparison",
                "Reproduction",
                "Security",
                "Incremental + capabilities",
            ),
        )
    )
    if page == "Landing / demos":
        _landing(service)
    elif page == "Compile":
        _compile(service)
    elif page == "Graph":
        _graph(service)
    elif page == "Comparison":
        _comparison(service)
    elif page == "Reproduction":
        _reproduction(service)
    elif page == "Security":
        _security(service)
    else:
        _incremental_capabilities(service)


if __name__ == "__main__":
    main()

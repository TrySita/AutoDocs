# pyright: ignore[reportMissingTypeArgument=true]
"""NetworkX DAG builder for code analysis."""

import logging
from networkx import DiGraph

from collections import defaultdict

import networkx as nx

from database.manager import DatabaseManager, session_scope

from database.models import (
    DefinitionDependencyModel,
    DefinitionModel,
    FileDependencyModel,
    FileModel,
    ReferenceModel,
)
from database.types import ParseDelta

type IdGraph = DiGraph[int]


logger = logging.getLogger(__name__)


class DAGBuilder:
    """Builder class for creating NetworkX graphs from database data."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager: DatabaseManager = db_manager

    def build_function_dependency_graph(self, remove_isolated: bool = False) -> IdGraph:
        """Build a directed graph of function dependencies.

        Returns:
            NetworkX DiGraph where nodes are definition IDs
        """
        graph: IdGraph = DiGraph()

        # boolean whether the definition_dependencies table exists

        with session_scope(self.db_manager) as session:
            # Add all definitions as nodes with minimal metadata
            definitions = session.query(DefinitionModel).all()
            for definition in definitions:
                graph.add_node(
                    definition.id,
                    file_id=definition.file_id,
                    definition_type=definition.definition_type,
                    label=definition.name,
                    title=definition.file.file_path,
                )

            print(f"Added {len(definitions)} definition nodes")

            # Add edges for references
            refs = session.query(ReferenceModel).all()
            print(f"Adding reference edges... {len(refs)}")
            edges = 0
            for idx, ref in enumerate(refs):
                logger.info(f"Processing reference: {idx}/{len(refs)}")
                if ref.target_definition_id and ref.target_definition:
                    graph.add_edge(
                        ref.source_definition_id,
                        ref.target_definition_id,
                        relationship_type="reference",
                    )
                    session.add(
                        DefinitionDependencyModel(
                            from_definition=ref.source_definition,
                            to_definition=ref.target_definition,
                            dependency_type="reference",
                        )
                    )

                    edges += 1

            print(f"Added {edges} reference edges")

        print(
            f"Function graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
        )

        # Remove isolated nodes (no edges)
        isolated_nodes = list(nx.isolates(graph))
        if isolated_nodes and remove_isolated:
            graph.remove_nodes_from(isolated_nodes)
            print(f"Removed {len(isolated_nodes)} isolated nodes")

        return graph

    def build_file_dependency_graph(
        self, function_graph: IdGraph | None = None
    ) -> IdGraph:
        """Build a file-level dependency graph from function dependencies.

        Args:
            function_graph: Optional pre-built function graph

        Returns:
            NetworkX DiGraph where nodes are file paths
        """
        if function_graph is None:
            function_graph = self.build_function_dependency_graph()

        file_graph: IdGraph = DiGraph()

        with session_scope(self.db_manager) as session:
            # Create mapping from definition ID to file path
            def_id_to_file: dict[int, FileModel] = {}
            files: dict[int, FileModel] = {
                file.id: file for file in session.query(FileModel).all()
            }

            # Add all files as nodes
            for file_model in files.values():
                file_graph.add_node(
                    file_model.id,
                    file_path=file_model.file_path,
                    language=file_model.language,
                    label=file_model.file_path.split("/")[-1],
                    title=file_model.file_path,
                )

                # Build mapping for definitions in this file
                for definition in file_model.definitions:
                    def_id_to_file[definition.id] = file_model

            print(f"Added {len(files)} file nodes")

            # Build file dependencies from function/type dependencies
            file_dependencies: defaultdict[int, set[int]] = defaultdict(set)

            for source_def_id, target_def_id in function_graph.edges():
                source_file: FileModel | None = def_id_to_file.get(source_def_id)
                target_file: FileModel | None = def_id_to_file.get(target_def_id)

                # Only create file dependency if different files and both exist
                if source_file and target_file and source_file != target_file:
                    file_dependencies[source_file.id].add(target_file.id)

            # Add edges to file graph
            edge_count = 0
            file_dep_rows: list[dict[str, int]] = []
            for idx, (source_file_id, target_file_ids) in enumerate(
                file_dependencies.items()
            ):
                for target_file_id in target_file_ids:
                    if not file_graph.has_edge(source_file_id, target_file_id):
                        logger.info(
                            f"Processing file dependency: {idx}/{len(file_dependencies)}"
                        )

                        file_graph.add_edge(source_file_id, target_file_id)
                        session.add(
                            FileDependencyModel(
                                from_file=files[source_file_id],
                                to_file=files[target_file_id],
                            )
                        )

                        edge_count += 1

            print(f"Added {edge_count} file dependency edges")

        print(
            f"File graph: {file_graph.number_of_nodes()} nodes, {file_graph.number_of_edges()} edges"
        )

        return file_graph

    def seeds_from_delta(self, delta: ParseDelta) -> tuple[set[int], set[int]]:
        """Derive seed definition and file IDs from a ParseDelta.

        Returns:
            Tuple of (seed_definition_ids, seed_file_ids)
        """
        seed_def_ids: set[int] = set()
        seed_file_ids: set[int] = set()

        # Collect file paths to consider (relative paths)
        paths: set[str] = set()
        paths.update(delta.files_added)
        paths.update(delta.files_modified)
        paths.update([r.new for r in delta.files_renamed])

        with session_scope(self.db_manager) as session:
            if paths:
                files = (
                    session.query(FileModel)
                    .filter(FileModel.file_path.in_(list(paths)))
                    .all()
                )
                for f in files:
                    seed_file_ids.add(f.id)
                    for d in f.definitions:
                        seed_def_ids.add(d.id)

            # Add directly known added definition IDs (if any)
            seed_def_ids.update(delta.definitions_added)

        return seed_def_ids, seed_file_ids

    def build_function_subgraph(self, seed_definition_ids: set[int]) -> IdGraph:
        """Build a function-level subgraph containing seeds and all their ancestors (dependents).

        Traverses DefinitionDependencyModel in reverse (to -> from) to collect parents.
        """
        subgraph: IdGraph = DiGraph()
        if not seed_definition_ids:
            return subgraph

        # Compute reverse-closure of dependents
        with session_scope(self.db_manager) as session:
            visited: set[int] = set()
            frontier: set[int] = set(seed_definition_ids)

            while frontier:
                visited.update(frontier)
                # Find parents: from_definition_id where to_definition_id in frontier
                parents: set[int] = set()
                ids_list = list(frontier)
                frontier = set()
                if ids_list:
                    rows = (
                        session.query(ReferenceModel.source_definition_id)
                        .filter(ReferenceModel.target_definition_id.in_(ids_list))
                        .all()
                    )
                    for (from_id,) in rows:
                        if from_id not in visited:
                            parents.add(from_id)

                # Next frontier is parents not yet visited
                frontier = parents - visited

            nodes: set[int] = visited

            if not nodes:
                return subgraph

            # Add nodes with metadata
            defs = (
                session.query(DefinitionModel)
                .filter(DefinitionModel.id.in_(list(nodes)))
                .all()
            )
            for d in defs:
                subgraph.add_node(
                    d.id,
                    file_id=d.file_id,
                    definition_type=d.definition_type,
                    label=d.name,
                    title=d.file.file_path if d.file else None,
                )

            # Add edges among collected nodes using ReferenceModel
            edges = (
                session.query(
                    ReferenceModel.source_definition_id,
                    ReferenceModel.target_definition_id,
                )
                .filter(ReferenceModel.source_definition_id.in_(list(nodes)))
                .filter(ReferenceModel.target_definition_id.in_(list(nodes)))
                .all()
            )
            for from_id, to_id in edges:
                subgraph.add_edge(from_id, to_id, relationship_type="reference")

        return subgraph

    def build_file_subgraph(self, seed_file_ids: set[int]) -> IdGraph:
        """Build a file-level subgraph containing seeds and all their ancestors (dependents).

        Traverses FileDependencyModel in reverse (to -> from) to collect parents.
        """
        subgraph: IdGraph = DiGraph()
        if not seed_file_ids:
            return subgraph

        with session_scope(self.db_manager) as session:
            visited: set[int] = set()
            frontier: set[int] = set(seed_file_ids)

            while frontier:
                visited.update(frontier)
                parents: set[int] = set()
                ids_list = list(frontier)
                frontier = set()
                if ids_list:
                    # 1) Find definitions contained in the frontier files (targets)
                    target_def_ids = (
                        session.query(DefinitionModel.id)
                        .filter(DefinitionModel.file_id.in_(ids_list))
                        .all()
                    )
                    target_def_ids_set: set[int] = {i for (i,) in target_def_ids}

                    if target_def_ids_set:
                        # 2) Find source definitions that reference these target definitions
                        source_def_ids = (
                            session.query(ReferenceModel.source_definition_id)
                            .filter(
                                ReferenceModel.target_definition_id.in_(
                                    list(target_def_ids_set)
                                )
                            )
                            .all()
                        )
                        source_def_ids_set: set[int] = {i for (i,) in source_def_ids}

                        if source_def_ids_set:
                            # 3) Map source definitions to their files (parents)
                            parent_file_ids = (
                                session.query(DefinitionModel.file_id)
                                .filter(
                                    DefinitionModel.id.in_(list(source_def_ids_set))
                                )
                                .all()
                            )
                            for (from_file_id,) in parent_file_ids:
                                if from_file_id not in visited:
                                    parents.add(from_file_id)
                frontier = parents - visited

            nodes: set[int] = visited
            if not nodes:
                return subgraph

            # Add file nodes
            files = session.query(FileModel).filter(FileModel.id.in_(list(nodes))).all()
            for f in files:
                subgraph.add_node(
                    f.id,
                    file_path=f.file_path,
                    language=f.language,
                    label=f.file_path.split("/")[-1],
                    title=f.file_path,
                )

            # Add edges among collected nodes using ReferenceModel -> DefinitionModel mapping
            # Compute all file-level edges where both endpoints are in the subgraph
            # 1) Map definition id -> file id for nodes
            defs = (
                session.query(DefinitionModel.id, DefinitionModel.file_id)
                .filter(DefinitionModel.file_id.in_(list(nodes)))
                .all()
            )
            def_to_file: dict[int, int] = {d_id: f_id for (d_id, f_id) in defs}

            # 2) Find references where both files are in the set and different
            ref_edges = (
                session.query(
                    ReferenceModel.source_definition_id,
                    ReferenceModel.target_definition_id,
                )
                .filter(
                    ReferenceModel.source_definition_id.in_(list(def_to_file.keys()))
                )
                .filter(
                    ReferenceModel.target_definition_id.in_(list(def_to_file.keys()))
                )
                .all()
            )
            for src_def, tgt_def in ref_edges:
                src_file = def_to_file.get(src_def)
                tgt_file = def_to_file.get(tgt_def)
                if src_file and tgt_file and src_file != tgt_file:
                    if not subgraph.has_edge(src_file, tgt_file):
                        subgraph.add_edge(src_file, tgt_file)

        return subgraph

    def detect_strongly_connected_components(self, graph: IdGraph) -> list[set[int]]:
        """Detect strongly connected components (cycles) in the graph."""
        sccs = list(nx.strongly_connected_components(graph))

        # Filter out trivial SCCs (single nodes with no self-loops)
        non_trivial_sccs = []
        for scc in sccs:
            if len(scc) > 1 or (
                len(scc) == 1 and graph.has_edge(list(scc)[0], list(scc)[0])
            ):
                non_trivial_sccs.append(scc)

        if non_trivial_sccs:
            print(f"Found {len(non_trivial_sccs)} cycles in graph")
            for i, scc in enumerate(non_trivial_sccs):
                print(f"  Cycle {i + 1}: {len(scc)} nodes")
        else:
            print("No cycles detected - graph is acyclic")

        return sccs

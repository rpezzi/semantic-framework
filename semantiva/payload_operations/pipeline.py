from typing import Any, Dict, List, Optional, Tuple
from .stop_watch import StopWatch
from .payload_operations import PayloadOperation
from .nodes import (
    DataNode,
    AlgorithmNode,
    ContextNode,
    ProbeResultCollectorNode,
    ProbeContextInjectorNode,
)
from ..logger import Logger
from ..data_types.data_types import BaseDataType, DataCollectionType
from ..context_operations.context_types import ContextType
from .nodes import node_factory


class Pipeline(PayloadOperation):
    """
    Represents a pipeline for orchestrating multiple payload operations.

    A pipeline is a structured collection of nodes or operations designed to process
    `BaseDataType` data and context in a systematic manner. It enables the execution
    of complex workflows by chaining multiple `Node` instances together.

    Node Configuration:
    Each node in the pipeline is defined using a dictionary with the following keys:

    - `operation` (required): The operation to perform, either a `DataOperation (DataAlgorithm` or `DataProbe`) or a `ContextOperation`.
    - `parameters` (optional, default=`{}`): A dictionary of parameters for the operation.
      If an operation parameter is **not explicitly defined** in the pipeline configuration,
      it is extracted from the **context**, using the parameter name as the context keyword.
      Parameters explicitly defined in the pipeline configuration take precedence over those
      obtained from the context.

    ### Node Types:

    1. **AlgorithmNode**:
       - Configured when a `DataAlgorithm` is given as the `operation`.
       - Example:
         ```python
         {
             "operation": SomeDataAlgorithm,
             "parameters": {"param1": value1, "param2": value2}
         }
         ```
       - Defaults:
         - `parameters` defaults to an empty dictionary `{}`.

    2. **ProbeContextInjectorNode**:
       - Configured when a `DataProbe` is used as the `operation`, and `context_keyword` is **not** provided.
       - This node collects probe results. No changes in data or context information.
       - Example:
         ```python
         {
             "operation": SomeDataProbe
         }
         ```
       - Defaults:
         - `parameters` defaults to `{}`.

    3. **ProbeResultCollectorNode**:
       - Configured when a `DataProbe` is used as the `operation`, and `context_keyword` **is** provided.
       - Stores collected probe results in the context container under the specified keyword.
       - Example:
         ```python
         {
             "operation": SomeDataProbe,
             "context_keyword": "some_probe_keyword"
         }
         ```
       - Defaults:
         - `parameters` defaults to `{}`.

    ### Data Processing and Slicing:

    The pipeline processes data and context sequentially through its nodes. Processing follows these rules:
        1. If the node's expected input type matches the current data type exactly,
           the node processes the entire data object in a single call. This is the nominal operation.
        2. If the current data is a `DataCollectionType` and the node process its base type,
           data is processed **element-wise** using a slicing stratgy.
        3. If neither condition applies, an error is raised (invalid pipeline topology).

    The pipeline supports both `ContextType` and `ContextCollectionType`:
        - When slicing data, if the context is a `ContextCollectionType`, it is sliced in parallel.
        - If the context is a single `ContextType`, it is **reused** for each data item and the result
          of the context operation is not passed to the next node.

    Attributes:
        pipeline_configuration (List[Dict]): A list of dictionaries defining the configuration
                                             for each node in the pipeline.
        nodes (List[Node]): The list of nodes that make up the pipeline.
        stop_watch (StopWatch): Tracks the execution time of nodes in the pipeline.
    """

    pipeline_configuration: List[Dict]
    nodes: List[DataNode]
    stop_watch: StopWatch

    def __init__(
        self, pipeline_configuration: List[Dict], logger: Optional[Logger] = None
    ):
        """
        Initialize a pipeline based on the provided configuration.

        Args:
            pipeline_configuration (List[Dict]): A list of dictionaries where each dictionary
                                                 specifies the configuration for a node in the
                                                 pipeline.
            logger (Optional[Logger]): An optional logger instance for logging pipeline activities.

        Example:
            pipeline_configuration = [
                {"operation": SomeDataAlgorithm, "parameters": {"param1": value1}},
                {"operation": SomeDataProbe, "context_keyword": "collected_data"}
            ]
        """
        super().__init__(logger)
        self.nodes: List[DataNode] = []
        self.pipeline_configuration: List[Dict] = pipeline_configuration
        self.stop_watch = StopWatch()
        self._initialize_nodes()
        if self.logger:
            self.logger.info(f"Initialized {self.__class__.__name__}")
            self.logger.debug("%s", self.inspect())

    def _add_node(self, node: DataNode):
        """
        Adds a node to the pipeline while ensuring compatibility between consecutive operations.

        This method enforces that the output type of the last `AlgorithmNode` is compatible
        with the input type of the new node. Probe nodes do not modify data, so their output
        type is ignored for validation purposes.

        If the first node in the pipeline is a probe node, it is added without validation.

        Args:
            node (Node): The node to be added to the pipeline.

        Raises:
            AssertionError: If the input type of the new node is not compatible with the
                            output type of the last `AlgorithmNode`.
        """
        # Find the last node that constrains the data type (i.e., last AlgorithmNode)
        last_type_constraining_node = None
        for previous_node in reversed(self.nodes):
            if isinstance(previous_node, AlgorithmNode):
                last_type_constraining_node = previous_node
                break

        # If no AlgorithmNode exists yet, allow the first node to be added unconditionally
        if last_type_constraining_node is None or issubclass(type(node), ContextNode):
            self.nodes.append(node)
            return

        # Get the output type of the last type-constraining node and the input type of the new node
        output_type = last_type_constraining_node.operation.output_data_type()
        input_type = node.operation.input_data_type()

        # If the output is a DataCollectionType, check its base type
        if isinstance(output_type, type) and issubclass(
            output_type, DataCollectionType
        ):
            base_type = output_type.collection_base_type()

            # Allow the node if the base type matches the input type
            if base_type == input_type:
                self.nodes.append(node)
                return

        # Enforce strict type matching otherwise
        assert issubclass(output_type, input_type) or issubclass(
            input_type, output_type
        ), (
            f"Invalid pipeline topology: Output of "
            f"{last_type_constraining_node.operation.__class__.__name__} "
            f"({output_type}) not compatible with "
            f"{node.operation.__class__.__name__} ({input_type})."
        )

        # Add the node if it passes validation
        self.nodes.append(node)

    def _process(
        self, data: BaseDataType, context: ContextType
    ) -> Tuple[BaseDataType, ContextType]:
        """
        Executes the pipeline by processing data and context sequentially through each node.

        Processing follows these rules:
            1. If the node's expected input type matches the current data type exactly,
            the node processes the entire dataset in a single call.
            2. If the current data is a `DataCollectionType` and the node expects its base type,
            data is processed **element-wise** using `_slicing_strategy`.
            3. If neither condition applies, an error is raised (invalid pipeline topology).

        The pipeline supports both `ContextType` and `ContextCollectionType`:
            - When slicing data, if the context is a `ContextCollectionType`, it is sliced in parallel.
            - If the context is a single `ContextType`, it is **reused** for each data item.

        Args:
            data (BaseDataType): The initial input data for the pipeline.
            context (ContextType): The initial context, which may be updated during processing.

        Returns:
            Tuple[BaseDataType, ContextType]: The final processed data and context.

        Raises:
            TypeError: If the node's expected input type does not match the current data type.
        """
        self.stop_watch.start()
        result_data, result_context = data, context
        self.logger.debug("Start processing pipeline")
        for node in self.nodes:
            self.logger.debug(
                f"Processing {type(node.operation).__name__} ({type(node).__name__})"
            )
            self.logger.debug(f"    Data: {result_data}, Context: {result_context}")
            # Get the expected input type for the node's operation
            input_type = node.operation.input_data_type()

            if (
                (type(result_data) == input_type)
                or (
                    isinstance(result_data, DataCollectionType)
                    and input_type == result_data.collection_base_type()
                )
                or (issubclass(type(result_data), input_type))
            ):
                result_data, result_context = node.process(result_data, result_context)

            # Case 2: Incompatible data type
            else:
                raise TypeError(
                    f"Incompatible data type for Node {node.operation.__class__.__name__} "
                    f"expected {input_type}, but received {type(result_data)}."
                )
        self.stop_watch.stop()
        self.logger.debug("Finished pipeline")
        self.logger.debug(
            "Pipeline timers \n\tPipeline %s\n%s",
            str(self.stop_watch),
            self.get_timers(),
        )
        return result_data, result_context

    def inspect(self) -> str:
        """
        Inspect the current pipeline structure and return its summary, including execution time.

        Returns:
            str: A summary of the pipeline including nodes and their configuration, as well as
                the total pipeline execution time. The summary includes:
                - Node details: The class names of the nodes and their operations.
                - Parameters: The parameters used by each node, categorized by their source
                (pipeline configuration or context).
                - Context updates: The keywords that each node will create or modify in the context dictionary.
                - Context parameters needed: The final set of context parameters required by the pipeline.
        """

        # Format sets as comma-separated values instead of Python set syntax
        def format_set(s):
            return ", ".join(sorted(s)) if s else "None"

        summary = "Pipeline Structure:\n"

        all_context_params = set()
        probe_injector_params = set()
        node_summary = ""
        for i, node in enumerate(self.nodes):

            operation_params = set(node.operation.get_operation_parameter_names())
            node_config_params = set(node.operation_config.keys())
            context_params = operation_params - node_config_params

            if isinstance(node, ProbeContextInjectorNode):
                probe_injector_params.add(node.context_keyword)

            all_context_params.update(context_params)

            # Extract configuration parameters with their values
            config_with_values = (
                ", ".join(
                    f"{key}={value}" for key, value in node.operation_config.items()
                )
                if node.operation_config
                else "None"
            )
            node_summary += f"{i + 1}. Node: {node.operation.__class__.__name__}({node.__class__.__name__})\n"
            node_summary += f"\tParameters: {format_set(operation_params)}\n"
            node_summary += (
                f"\t\tFrom pipeline configuration: {config_with_values or None}\n"
            )
            node_summary += f"\t\tFrom context: {format_set(context_params - probe_injector_params) or None}\n"
            node_summary += (
                f"\tContext additions: {format_set(node.get_created_keys())}\n"
            )

        # Determine the final values needed in the context
        needed_context_parameters = all_context_params - probe_injector_params
        summary += f"Context parameters needed: {format_set(needed_context_parameters) or None}\n"
        summary += node_summary
        # summary += f"Pipeline {self.stop_watch}"
        return summary

    def get_timers(self) -> str:
        """
        Retrieve timing information for each node's execution.

        Returns:
            str: A formatted string displaying node number, operation name,
                elapsed CPU time, and elapsed wall time for each node.
        """
        timer_info = [
            f"\tNode {i + 1}: {type(node.operation).__name__}; "
            f"\tElapsed CPU Time: {node.stop_watch.elapsed_cpu_time():.6f}s; "
            f"\tElapsed Wall Time: {node.stop_watch.elapsed_wall_time():.6f}s"
            for i, node in enumerate(self.nodes)
        ]
        return "\n".join(timer_info)

    def get_probe_results(self) -> Dict[str, List[Any]]:
        """
        Retrieve the collected data from all probe collector nodes in the pipeline.

        This method iterates through the pipeline's nodes and checks for instances of
        `ProbeResultCollectorNode`. For each such node, it retrieves the collected data and
        associates it with the corresponding node's index in the pipeline.

        Returns:
            Dict[str, List[Any]]: A dictionary where keys are node identifiers (e.g., "Node 1/ProbeName"),
            and values are the collected data from the probe nodes.

        Example:
            If Node 1 and Node 3 are probe nodes, the result might look like:
            {
                "Node 1/ProbeName": [<collected_data_1>],
                "Node 3/ProbeName": [<collected_data_3>]
            }
        """
        # Dictionary to store probe results keyed by node identifiers
        probe_results = {}

        # Iterate over all nodes in the pipeline
        for i, node in enumerate(self.nodes):
            # Check if the node is a ProbeResultCollectorNode
            if isinstance(node, ProbeResultCollectorNode):
                # Add the collected data from the node to the results dictionary
                probe_results[f"Node {i + 1}/{type(node.operation).__name__}"] = (
                    node.get_collected_data()
                )

        # Return the dictionary of probe results
        return probe_results

    def _initialize_nodes(self):
        """
        Initialize all nodes in the pipeline.

        This method uses the `node_factory` function to create nodes from the provided
        pipeline configuration. Each node is then added to the pipeline.
        """

        for node_config in self.pipeline_configuration:
            node = node_factory(node_config, self.logger)
            self._add_node(node)

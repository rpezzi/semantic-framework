from abc import ABC, abstractmethod
from typing import Type, Dict
from ..data_io import DataSource, DataSink
from ..payload_operations import PayloadOperation


class ComputingTask(ABC):
    """
    Abstract base class for a computing task.

    Subclasses must implement the `_run` method to define the specific computation logic.
    """

    @abstractmethod
    def _run(self, *args, **kwargs):
        """
        Abstract method to be implemented by subclasses for performing the task.

        Args:
            *args: Positional arguments for the task.
            **kwargs: Keyword arguments for the task.
        """
        ...

    def run(self, *args, **kwargs):
        """
        Run the computing task by invoking the `_run` method.

        Args:
            *args: Positional arguments for the task.
            **kwargs: Keyword arguments for the task.

        Returns:
            The result of the `_run` method.
        """
        return self._run(*args, **kwargs)


class PayloadOperationTask(ComputingTask):
    """
    Task for processing payloads using a data source, a payload operation, and a data sink.

    This class encapsulates the logic for:
    - Retrieving data and context from a data source.
    - Applying a payload operation to the data and context.
    - Sending the processed data and context to a data sink.

    Attributes:
        data_source_class (Type[DataSource]): Class responsible for providing the data.
        data_source_parameters (Dict): Parameters for initializing the data source.
        payload_operation_class (Type[PayloadOperation]): Class responsible for the payload operation.
        payload_operation_config (Dict): Configuration for the payload operation.
        data_sink_class (Type[DataSink]): Class responsible for consuming the processed data.
        data_sink_parameters (Dict): Parameters for initializing the data sink.
    """

    data_source_class: Type[DataSource]
    data_source_parameters: Dict
    payload_operation_class: Type[PayloadOperation]
    payload_operation_config: Dict
    data_sink_class: Type[DataSink]
    data_sink_parameters: Dict

    def __init__(
        self,
        data_source_class: Type[DataSource],
        data_source_parameters: Dict,
        payload_operation_class: Type[PayloadOperation],
        payload_operation_config: Dict,
        data_sink_class: Type[DataSink],
        data_sink_parameters: Dict,
    ):
        """
        Initialize the PayloadOperationTask with the required components and configurations.

        Args:
            data_source_class (Type[DataSource]): The class for the data source.
            data_source_parameters (Dict): Parameters for initializing the data source.
            payload_operation_class (Type[PayloadOperation]): The class for the payload operation.
            payload_operation_config (Dict): Configuration for the payload operation.
            data_sink_class (Type[DataSink]): The class for the data sink.
            data_sink_parameters (Dict): Parameters for initializing the data sink.
        """
        self.data_source_class = data_source_class
        self.data_source_parameters = data_source_parameters
        self.payload_operation_class = payload_operation_class
        self.payload_operation_config = payload_operation_config
        self.data_sink_class = data_sink_class
        self.data_sink_parameters = data_sink_parameters

    def _run(self):
        """
        Execute the payload operation task.

        Steps:
        1. Retrieve data and context from the data source.
        2. Apply the payload operation to the data and context.
        3. Send the processed data and context to the data sink.

        Returns:
            tuple: A tuple containing the processed data and context.
        """
        # Retrieve data and context from the data source
        data, context = self.data_source_class.get_data(**self.data_source_parameters)

        # Initialize and apply the payload operation
        operation = PayloadOperation(
            self.payload_operation_class(self.payload_operation_config)
        )
        processed_data, processed_context = operation(data, context)

        # Send the processed data and context to the data sink
        self.data_sink_class.send_payload(
            *processed_data, processed_context, *self.data_sink_parameters
        )

        return processed_data, processed_context

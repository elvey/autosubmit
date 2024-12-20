from dataclasses import dataclass
from enum import Enum
import json
import copy
from typing import Any, Dict, List, Optional
from autosubmit.job.job import Job
from autosubmitconfigparser.config.configcommon import AutosubmitConfig
from log.log import Log


class MetricSpecSelectorType(Enum):
    TEXT = "TEXT"
    JSON = "JSON"


@dataclass
class MetricSpecSelector:
    type: MetricSpecSelectorType
    key: Optional[List[str]]

    @staticmethod
    def load(data: Optional[Dict[str, Any]]) -> "MetricSpecSelector":
        if data is None:
            _type = MetricSpecSelectorType.TEXT
            return MetricSpecSelector(type=_type, key=None)

        if not isinstance(data, dict):
            raise ValueError("Invalid metric spec selector")

        # Read the selector type
        _type = str(data.get("TYPE", MetricSpecSelectorType.TEXT.value)).upper()
        try:
            selector_type = MetricSpecSelectorType(_type)
        except Exception:
            raise ValueError(f"Invalid metric spec selector type: {_type}")

        # If selector type is TEXT, key is not required and is set to None
        if selector_type == MetricSpecSelectorType.TEXT:
            return MetricSpecSelector(type=selector_type, key=None)

        # If selector type is JSON, key must be a list or string
        elif selector_type == MetricSpecSelectorType.JSON:
            key = data.get("KEY", None)
            if isinstance(key, str):
                key = key.split(".")
            elif isinstance(key, list):
                key = key
            else:
                raise ValueError("Invalid key for JSON selector")
            return MetricSpecSelector(type=selector_type, key=key)

        return MetricSpecSelector(type=selector_type, key=None)


@dataclass
class MetricSpec:
    name: str
    path: str
    selector: MetricSpecSelector

    @staticmethod
    def load(data: Dict[str, Any]) -> "MetricSpec":
        if not isinstance(data, dict):
            raise ValueError("Invalid metric spec")

        if not data.get("NAME") or not data.get("PATH"):
            raise ValueError("Name and path are required in metric spec")

        _name = data["NAME"]
        _path = data["PATH"]

        _selector = data.get("SELECTOR", None)
        selector = MetricSpecSelector.load(_selector)

        return MetricSpec(name=_name, path=_path, selector=selector)


class UserMetricProcessor:
    def __init__(self, as_conf: AutosubmitConfig, job: Job):
        self.as_conf = as_conf
        self.job = job

    def read_metrics_specs(self) -> List[MetricSpec]:
        raw_metrics: List[Dict[str, Any]] = self.as_conf.normalize_parameters_keys(
            self.as_conf.get_section([self.job.section, "METRICS"])
        )

        metrics_specs: List[MetricSpec] = []
        for raw_metric in raw_metrics:
            """
            Read the metrics specs of the job
            """
            try:
                spec = MetricSpec.load(raw_metric)
                metrics_specs.append(spec)
            except Exception:
                Log.warning("Invalid metric spec: {}", str(raw_metric))

        return metrics_specs

    def _group_metrics_by_path_selector_type(
        self,
        metrics_specs: List[MetricSpec],
    ) -> Dict[str, Dict[str, List[MetricSpec]]]:
        """
        Group all metrics by file path and selector type.
        First level key is the file path, second level key is the selector type.
        """
        metrics_by_path_selector_type: Dict[str, Dict[str, List[MetricSpec]]] = {}
        for metric_spec in metrics_specs:
            # If the path is not in the dictionary, add it
            if metric_spec.path not in metrics_by_path_selector_type:
                metrics_by_path_selector_type[metric_spec.path] = {}

            # If the selector type is not in the dictionary, add it
            if (
                metric_spec.selector.type.value
                not in metrics_by_path_selector_type[metric_spec.path]
            ):
                metrics_by_path_selector_type[metric_spec.path][
                    metric_spec.selector.type.value
                ] = []

            metrics_by_path_selector_type[metric_spec.path][
                metric_spec.selector.type.value
            ].append(metric_spec)

        return metrics_by_path_selector_type

    def store_metric(self, metric_name: str, metric_value: Any):
        """
        Store the metric value in the database
        """
        self.job.name
        raise NotImplementedError("store_metric method must be implemented")

    def process_metrics_specs(self, metrics_specs: List[MetricSpec]):
        """ """

        metrics_by_path_selector_type = self._group_metrics_by_path_selector_type(
            metrics_specs
        )

        # For each file path, read the content of the file
        for path, metrics_by_selector_type in metrics_by_path_selector_type.items():
            with open(path, "r") as f:
                content = f.read()

            # Process the content based on the selector type

            # Text selector metrics
            text_selector_metrics = metrics_by_selector_type.get(
                MetricSpecSelectorType.TEXT.value, []
            )
            if text_selector_metrics:
                for metric in text_selector_metrics:
                    self.store_metric(metric.name, content)

            # JSON selector metrics
            json_selector_metrics = metrics_by_selector_type.get(
                MetricSpecSelectorType.JSON.value, []
            )
            if json_selector_metrics:
                try:
                    json_content = json.loads(content)
                    for metric in json_selector_metrics:
                        # Get the value based on the key
                        try:
                            key = metric.selector.key
                            value = copy.deepcopy(json_content)
                            if key:
                                for k in key:
                                    value = value[k]
                            self.store_metric(metric.name, value)
                        except Exception:
                            print(
                                f"Error processing JSON content in file {path} for metric {metric.name}"
                            )
                except json.JSONDecodeError:
                    print(f"Invalid JSON content in file {path}")
                except Exception:
                    print(f"Error processing JSON content in file {path}")

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput
from soar_sdk.params import Params
from soar_sdk.views.components.pie_chart import PieChartData


class StatisticsParams(Params):
    category: str


class StatisticsOutput(ActionOutput):
    category: str
    labels: list[str]
    values: list[int]


def render_statistics_chart(output: list[StatisticsOutput]) -> PieChartData:
    stats = output[0]
    colors = ["#4CAF50", "#2196F3", "#FF9800", "#F44336", "#9C27B0", "#607D8B"]

    return PieChartData(
        title=f"{stats.category} Distribution",
        labels=stats.labels,
        values=stats.values,
        colors=colors,
    )


def generate_statistics(param: StatisticsParams, soar: SOARClient) -> StatisticsOutput:
    if param.category.lower() == "test":
        breakdown = {
            "Malware": 45,
            "Phishing": 32,
            "Ransomware": 18,
            "Data Breach": 12,
            "DDoS": 8,
        }
    else:
        breakdown = {
            "Category A": 25,
            "Category B": 35,
            "Category C": 20,
            "Category D": 15,
            "Category E": 5,
        }

    return StatisticsOutput(
        category=param.category,
        labels=list(breakdown.keys()),
        values=list(breakdown.values()),
    )

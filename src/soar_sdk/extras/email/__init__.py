from soar_sdk.extras.email import email_data as rfc5322
from soar_sdk.extras.email.analysis import (
    INCOMPLETE_ANALYSIS_HEADLINE,
    EmailAnalysisResult,
    analyze_email,
    apply_warnings_to_container,
    apply_warnings_to_finding,
)
from soar_sdk.extras.email.budget import (
    MIB,
    EmailAnalysisWarning,
    EmailBudgetAssetMixin,
    EmailBudgetLimits,
    EmailBudgetLimitType,
    EmailMessageBudget,
    EmailPollBudget,
)
from soar_sdk.extras.email.email_data import (
    EmailData,
    RFC5322EmailData,
    extract_email_data,
    extract_rfc5322_email_data,
)
from soar_sdk.extras.email.processor import EmailProcessor, ProcessEmailContext

__all__ = [
    "INCOMPLETE_ANALYSIS_HEADLINE",
    "MIB",
    "EmailAnalysisResult",
    "EmailAnalysisWarning",
    "EmailBudgetAssetMixin",
    "EmailBudgetLimitType",
    "EmailBudgetLimits",
    "EmailData",
    "EmailMessageBudget",
    "EmailPollBudget",
    "EmailProcessor",
    "ProcessEmailContext",
    "RFC5322EmailData",
    "analyze_email",
    "apply_warnings_to_container",
    "apply_warnings_to_finding",
    "extract_email_data",
    "extract_rfc5322_email_data",
    "rfc5322",
]

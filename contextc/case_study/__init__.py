"""M11 real-repository historical case-study API."""

from .analysis import TaskValidation, validate_suite, validate_task
from .executor import run_case_suite, run_case_task, verify_task_determinism
from .loader import list_task_directories, load_case_study_task, load_public_case_task
from .reporting import build_report, report_markdown
from .repository import HistoricalRepository, packaged_case_study_root
from .schemas import CaseStudyExecution, CaseStudyPublicTask, HistoricalLabels, ManualReview
from .strategies import CASE_STUDY_STRATEGIES

__all__ = [
    "CASE_STUDY_STRATEGIES",
    "CaseStudyExecution",
    "CaseStudyPublicTask",
    "HistoricalLabels",
    "HistoricalRepository",
    "ManualReview",
    "TaskValidation",
    "build_report",
    "list_task_directories",
    "load_case_study_task",
    "load_public_case_task",
    "packaged_case_study_root",
    "report_markdown",
    "run_case_suite",
    "run_case_task",
    "validate_suite",
    "validate_task",
    "verify_task_determinism",
]

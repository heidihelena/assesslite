"""AssessLite — test what your analysis depends on.

Structural assumption assessment for causal analysis. AssessLite is the product,
StructuralAudit(...) opens an assessment, and .export_audit() writes the durable
audit record. Native Python interface to the AssessLite core specification v0.1;
the R implementation lives alongside it and produces schema-compatible audit records.
"""
from .core import StructuralAudit, invariance_vocabulary
from .export import export_audit
from .report import render_report

__all__ = ["StructuralAudit", "invariance_vocabulary", "export_audit", "render_report"]
__version__ = "0.2.0"

"""Intent-to-IaC generation service.

Generates governed Infrastructure as Code from natural language intent,
using organizational context (.thothcf.toml, steering docs, existing patterns)
and validating output with Checkov + OPA.
"""

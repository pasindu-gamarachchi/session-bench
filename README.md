# Session-Bench

A framework for evaluating Large Language Model (LLM) context preservation across multi-issue software development sessions.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

Session-Bench evaluates how well LLMs maintain context, code quality, and architectural understanding when solving multiple related issues sequentially - mimicking real-world software development workflows.

**Key Capabilities:**
- Multi-issue session orchestration
- Automatic dependency installation
- Real test execution (pytest, Django, etc.)
- Constraint checking & degradation detection
- Comprehensive results storage
- Pluggable LLM strategy interface

Built on [SWE-bench](https://www.swebench.com/) dataset for realistic software engineering tasks.

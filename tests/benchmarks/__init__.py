"""Benchmarks package — uses pytest-benchmark.

Run with::

    pytest tests/benchmarks/ -v
    pytest tests/benchmarks/ -v --benchmark-sort=median
    pytest tests/benchmarks/ -v --benchmark-json=results.json

To run as plain functional tests without benchmark overhead::

    pytest tests/benchmarks/ --benchmark-disable
"""

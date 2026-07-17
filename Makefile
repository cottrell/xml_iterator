# Native extension: always release unless you opt into develop-debug.
# Bare `maturin develop` (no -r) is DEBUG and will poison benches/tests.

all:
	cat Makefile

build:
	# wheel → release
	maturin build --release

develop:
	# editable install → release (~9x faster than debug; see PERF_2026-07-17.md)
	maturin develop --uv --release

develop-debug:
	maturin develop --uv

# Force release extension into the active env (idempotent enough for make).
ensure-release: develop

.PHONY: all build develop develop-debug ensure-release \
	test test-basic test-xmltodict test-performance test-fast test-comparators \
	install-test-deps benchmark benchmark-real benchmark-firds benchmark-all clean

install-test-deps: ensure-release
	# pure-Python extras only after release extension is in place
	uv pip install -e ".[test]"
	# editable reinstall can rebuild; re-assert release
	maturin develop --uv --release

test: ensure-release
	pytest

test-basic: ensure-release
	pytest tests/test_basic.py

test-xmltodict: ensure-release
	pytest tests/test_xmltodict.py

test-performance: ensure-release
	pytest tests/test_performance.py

test-comparators: ensure-release
	pytest tests/test_comparators.py

test-fast: ensure-release
	pytest -m "not slow"

# Run benchmarks comparing against xmltodict + stream comparators
benchmark: ensure-release
	python benchmark.py

# Run real-world benchmark with SwissProt XML file
benchmark-real: ensure-release
	python benchmark_real_world.py --dataset swissprot

# Run real-world benchmark with large ESMA FIRDS XML file
benchmark-firds: ensure-release
	python benchmark_real_world.py --dataset firds

# Run all real-world benchmarks
benchmark-all: ensure-release
	python benchmark_real_world.py --dataset both

clean:
	cargo clean
	find . -path ./.venv -prune -o -path ./target -prune -o -name '*.so' -print | xargs -r rm -v
	find . -path ./.venv -prune -o -path ./target -prune -o -name '*.pyc' -print | xargs -r rm -v

all:
	cat Makefile

build:
	# NOTE: make sure to build like this else is much slower
	maturin build --release

develop:
	# NOTE: installs in develop mode if that is what you want
	maturin develop --uv

.PHONY: test test-basic test-xmltodict test-performance test-fast install-test-deps benchmark

install-test-deps:
	uv pip install -e ".[test]"

test:
	pytest

test-basic:
	pytest tests/test_basic.py

test-xmltodict:
	pytest tests/test_xmltodict.py

test-performance:
	pytest tests/test_performance.py

test-fast:
	pytest -m "not slow"

# Run benchmarks comparing against xmltodict
benchmark:
	python benchmark.py

# Run real-world benchmark with SwissProt XML file
benchmark-real:
	python benchmark_real_world.py --dataset swissprot

# Run real-world benchmark with large ESMA FIRDS XML file
benchmark-firds:
	python benchmark_real_world.py --dataset firds

# Run all real-world benchmarks
benchmark-all:
	python benchmark_real_world.py --dataset both

clean:
	cargo clean
	find -name '*.so' | xargs rm -v
	find -name '*.pyc' | xargs rm -v

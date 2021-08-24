all:
	. ./venv/bin/activate
	pip install -r requirements.txt
	rm -f ../../core/pyspec/eth2spec/test/phase0/random/test_random.py
	rm -f ../../core/pyspec/eth2spec/test/altair/random/test_random.py
	python generate.py phase0 > ../../core/pyspec/eth2spec/test/phase0/random/test_random.py
	python generate.py altair > ../../core/pyspec/eth2spec/test/altair/random/test_random.py

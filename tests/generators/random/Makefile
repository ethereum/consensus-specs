all:
	if ! test -d venv; then python3 -m venv venv; fi;
	. ./venv/bin/activate
	pip3 install -r requirements.txt
	rm -f ../../core/pyspec/eth2spec/test/phase0/random/test_random.py
	rm -f ../../core/pyspec/eth2spec/test/altair/random/test_random.py
	rm -f ../../core/pyspec/eth2spec/test/bellatrix/random/test_random.py
	rm -f ../../core/pyspec/eth2spec/test/capella/random/test_random.py
	rm -f ../../core/pyspec/eth2spec/test/deneb/random/test_random.py
	python3 generate.py phase0 > ../../core/pyspec/eth2spec/test/phase0/random/test_random.py
	python3 generate.py altair > ../../core/pyspec/eth2spec/test/altair/random/test_random.py
	python3 generate.py bellatrix > ../../core/pyspec/eth2spec/test/bellatrix/random/test_random.py
	python3 generate.py capella > ../../core/pyspec/eth2spec/test/capella/random/test_random.py
	python3 generate.py deneb > ../../core/pyspec/eth2spec/test/deneb/random/test_random.py

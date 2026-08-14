install:
	pip install -r requirements.txt

check-data:
	cd data/raw && sha256sum -c ../raw_manifest.sha256

test:
	pytest -q

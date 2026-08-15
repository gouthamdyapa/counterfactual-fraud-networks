install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -q

prepare-temporal:
	python experiments/01_prepare_temf_data.py

prepare-graph:
	python experiments/09_prepare_final_graph_data.py

graph-experiments:
	python experiments/10_graph_memory_5seed_colab.py
	python experiments/11_temporal_neighbor_event_5seed_colab.py

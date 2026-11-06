from agent import graph
from pathlib import Path

graph.load_seed(Path(__file__).resolve().parents[1] / 'data' / 'seed_graph.json')
print('Graph loaded')

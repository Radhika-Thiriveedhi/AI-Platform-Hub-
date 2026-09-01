.PHONY: install build run test clean

install:
	pip install -r requirements.txt
	npm install

build:
	python -m compileall -q .
	npm run build

run:
	python main.py

test:
	pytest ai_platform_hub_50k_loc_fixed/tests/

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"

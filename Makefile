IMAGE_NAME := gisquick-project-from-file-tests
PLUGIN_DIR := $(shell pwd)

.PHONY: build test clean

build:
	docker build -t $(IMAGE_NAME) .devcontainer/

test: build
	docker run --rm \
		-v "$(PLUGIN_DIR):/plugins/gisquick_project_from_file" \
		-w /plugins/gisquick_project_from_file \
		-e QT_QPA_PLATFORM=offscreen \
		-e PYTHONPATH=/plugins \
		$(IMAGE_NAME) \
		python3 -m pytest tests/ -v $(PYTEST_ARGS)

clean:
	docker rmi $(IMAGE_NAME) || true

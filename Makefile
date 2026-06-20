.PHONY: demo gui replay test docker-demo clean crucible

crucible:
	python3 crucible.py

demo:
	PYTHONPATH=src python3 -m dtm demo

gui:
	PYTHONPATH=src python3 -u -m dtm gui

replay:
	PYTHONPATH=src python3 -m dtm replay artifacts/latest --output artifacts/replay

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

docker-demo:
	mkdir -p artifacts/docker
	docker compose up --build --abort-on-container-exit --exit-code-from monitor
	docker compose down

clean:
	rm -rf artifacts


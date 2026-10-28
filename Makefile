SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help

ENV ?= lab
TF_DIR := terraform/environments/$(ENV)
ANSIBLE_DIR := ansible
API_DIR := api
PROM_DIR := monitoring/prometheus
PLAYBOOK = cd $(ANSIBLE_DIR) && ansible-playbook -i inventories/$(ENV)

.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; print "Usage: make <target> [ENV=lab]"} \
		/^##@/ {printf "\n\033[1m%s\033[0m\n", substr($$0, 5)} \
		/^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Infrastructure (Terraform)

.PHONY: infra-init infra-plan infra-apply infra-destroy
infra-init: ## Initialise Terraform for $(ENV)
	terraform -chdir=$(TF_DIR) init

infra-plan: ## Show planned infrastructure changes
	terraform -chdir=$(TF_DIR) plan -out=tfplan

infra-apply: ## Apply the saved plan and regenerate the Ansible inventory
	terraform -chdir=$(TF_DIR) apply tfplan
	@# Rebuilt VMs get new host keys on the same IPs.
	rm -f $(ANSIBLE_DIR)/.known_hosts

infra-destroy: ## Destroy all $(ENV) VMs, volumes and networks
	terraform -chdir=$(TF_DIR) destroy

##@ Configuration (Ansible)

.PHONY: ansible-deps ping bootstrap ceph openstack-config openstack deploy
ansible-deps: ## Install required Ansible collections
	cd $(ANSIBLE_DIR) && ansible-galaxy collection install -r requirements.yml -p collections

ping: ## Check SSH reachability of every node
	cd $(ANSIBLE_DIR) && ansible all -i inventories/$(ENV) -m ansible.builtin.ping

bootstrap: ## OS baseline and hardening on every node
	$(PLAYBOOK) playbooks/bootstrap.yml

ceph: ## Deploy Ceph and create OpenStack pools and keys
	$(PLAYBOOK) playbooks/ceph.yml

openstack-config: ## Render Kolla configuration without deploying
	$(PLAYBOOK) playbooks/openstack.yml --tags kolla-install,kolla-config

openstack: ## Deploy OpenStack with Kolla-Ansible
	$(PLAYBOOK) playbooks/openstack.yml

deploy: ## Full build: bootstrap, Ceph, then OpenStack
	$(PLAYBOOK) playbooks/site.yml

##@ Quality

.PHONY: lint test tf-lint ansible-lint yaml-lint api-lint api-test rules-test pre-commit
lint: tf-lint ansible-lint yaml-lint api-lint ## Run every linter

test: api-test rules-test ## Run every test suite

tf-lint: ## terraform fmt/validate and TFLint
	terraform fmt -check -recursive terraform/
	terraform -chdir=$(TF_DIR) init -backend=false -input=false >/dev/null
	terraform -chdir=$(TF_DIR) validate
	tflint --recursive --config "$(CURDIR)/.tflint.hcl"

ansible-lint: ## ansible-lint (production profile)
	cd $(ANSIBLE_DIR) && ansible-lint

yaml-lint: ## yamllint across the repository
	yamllint --strict .

api-lint: ## ruff and mypy for the API
	cd $(API_DIR) && uv run ruff check . && uv run ruff format --check . && uv run mypy src tests

api-test: ## API unit tests with coverage
	cd $(API_DIR) && uv run pytest

rules-test: ## Validate and unit test Prometheus alerting rules
	cd $(PROM_DIR) && promtool check rules rules/*.yml && promtool test rules tests/*.test.yml

pre-commit: ## Run all pre-commit hooks against every file
	pre-commit run --all-files

##@ API

.PHONY: api-run api-image
api-run: ## Run the API locally with reload
	cd $(API_DIR) && uv run uvicorn aura_api.main:app --reload --port 8080

api-image: ## Build the API container image
	docker build -t aura-api:local $(API_DIR)

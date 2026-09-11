.PHONY: help tf-init tf-plan tf-apply ansible-ping pre-commit api-test

help:
	@echo "Project Aura Makefile"
	@echo "Usage:"
	@echo "  make tf-init    - Initialize Terraform in production environment"
	@echo "  make tf-plan    - Plan Terraform in production environment"
	@echo "  make tf-apply   - Apply Terraform in production environment"
	@echo "  make ansible-ping - Ping nodes using Ansible"
	@echo "  make pre-commit - Run pre-commit hooks on all files"
	@echo "  make api-test   - Run FastAPI unit tests"

tf-init:
	cd terraform/environments/production && terraform init

tf-plan:
	cd terraform/environments/production && terraform plan

tf-apply:
	cd terraform/environments/production && terraform apply

ansible-ping:
	cd ansible && ansible all -i inventories/production/hosts.yml -m ping

pre-commit:
	pre-commit run --all-files

api-test:
	cd api && pytest tests/

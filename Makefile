.PHONY: help test test-all test-models test-cart test-views test-stripe test-profile

PYTHON := ./venv/bin/python

help:
	@echo "Test Commands:"
	@echo "  make test          - Run all tests"
	@echo "  make test-models   - Run model tests"
	@echo "  make test-cart     - Run cart tests"
	@echo "  make test-views    - Run view tests"
	@echo "  make test-stripe   - Run Stripe tests"
	@echo "  make test-profile  - Run profile tests"

test:
	$(PYTHON) manage.py test shop.tests --verbosity=2

test-models:
	$(PYTHON) manage.py test shop.tests.test_models --verbosity=2

test-cart:
	$(PYTHON) manage.py test shop.tests.test_cart_utils --verbosity=2

test-views:
	$(PYTHON) manage.py test shop.tests.test_cart_views --verbosity=2

test-stripe:
	$(PYTHON) manage.py test shop.tests.test_stripe_integration --verbosity=2

test-profile:
	$(PYTHON) manage.py test shop.tests.test_user_profile --verbosity=2

INTRP=python3

test: create_csv.py analyze.py test_analyze.py
	@echo "Running tests..."
	$(INTRP) test_analyze.py -v


demo: create_csv.py timing.py analyze.py
	@echo "~~~ Running demo mode ~~~"
	$(INTRP) create_csv.py
	$(INTRP) timing.py
	@echo "Analyzing data..."
	$(INTRP) analyze.py -d
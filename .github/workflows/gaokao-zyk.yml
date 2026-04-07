name: Run CHSI Web Automation

on:
  workflow_dispatch:
  schedule:
    - cron: "0 1 * * *"

jobs:
  run-script:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Install Playwright browsers
        run: python -m playwright install --with-deps chromium

      - name: Run automation script
        run: python scripts/gaokao_zyk.py

      - name: Upload outputs
        if: ${{ !cancelled() }}
        uses: actions/upload-artifact@v5
        with:
          name: gaokao-zyk-output
          path: output/
          retention-days: 7

# python-version-matrix

A reusable workflow for generating matrix of runners and Python versions, fetches newest versions automatically.

## Example usage

```yaml
jobs:
  generate-matrix:
    uses: solaluset/python-version-matrix/.github/workflows/generate.yml@v1.0
    with:
      # List of runners in JSON format, mandatory
      runners: '[
        "ubuntu-latest",
        "windows-latest",
        "macos-latest"
      ]'

      # Minimal suitable Python version
      # defaults to auto (oldest non-EOL version)
      min-version: auto

      # Maximal suitable Python version
      # defaults to auto (latest version)
      max-version: auto

      # Whether to include pre-release versions
      # defaults to false
      include-pre-releases: false

      # Whether to include free threaded versions
      # defaults to false
      include-freethreaded: false

      # List of implementations to fetch
      # defaults to ["CPython"]
      implementations: '["CPython"]'

      # Whether to check target platform compatibility
      # defaults to true
      check-platform: true

  test:
    needs: [generate-matrix]
    runs-on: ${{ matrix.runner }}
    strategy:
      # Load generated matrix
      matrix: ${{ fromJson(needs.generate-matrix.outputs.matrix) }}
    steps:
      - uses: actions/setup-python@v6
        with:
          python-version: ${{ matrix.python-version }}
      - run: python --version

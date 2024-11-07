# Intro to Algorithmic Trading in Python

## Dependencies

### uv package manager

For development, we use `uv` as the package manager. Make sure you have `uv` installed.

See installation instructions [here](https://docs.astral.sh/uv/getting-started/installation/#standalone-installer).

Each microservice has its own dependencies, which are listed in the `pyproject.toml` file.

### pre-commit

We use `pre-commit` to run linting and formatting checks.

See installation instructions [here](https://pre-commit.com/#installation).

## Run the project

To run the project, use the following command:

```bash
make service-up
```

To stop the project, use the following command:

```bash
make service-down
```

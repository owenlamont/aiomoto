# Limitations

- Mixing raw Moto decorators with `aiomoto.mock_aws` in the same test is
  unsupported; the contexts manage shared state differently and can diverge.
- aiomoto wraps Moto and patches aiobotocore; s3fs should be covered automatically
  in in-process mode since it uses aiobotocore clients underneath.
- Version ranges are kept narrow and tested together. If you notice a new version of
  aiobotocore or Moto that isn't covered, please
  [raise an issue](https://github.com/owenlamont/aiomoto/issues).
- s3fs caches filesystem instances; create them inside `mock_aws` and close them so
  finalizers don't run against a closed or different event loop.
- Pandas S3 I/O: in server mode, aiomoto patches pandas to route `s3://` through
  fsspec/s3fs when those dependencies are installed.
- Polars S3 I/O is patched in server mode when polars is installed; aiomoto injects
  `storage_options` for `s3://` paths following the `auto_endpoint` mode.
- Moto proxy mode is unsupported; requesting it raises `ProxyModeError`.

## Free-threaded CPython

Free-threaded CPython 3.14t support covers aiomoto's core in-process mocking. The
pandas and polars server-mode integrations are validated on regular CPython builds
only &mdash; their dependency stacks are not yet reliable on free-threaded
interpreters, and Windows 3.14t also lacks compatible pywin32 wheels for Moto's
server dependency chain.

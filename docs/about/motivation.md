# Motivation

Like many others I wanted to use Moto with aiobotocore but found that wasn't
supported. See:

- [getmoto/moto#2039](https://github.com/getmoto/moto/issues/2039)
- [getmoto/moto#8694](https://github.com/getmoto/moto/issues/8694)

The primary motivation for creating aiomoto came from
[getmoto/moto#8513](https://github.com/getmoto/moto/issues/8513), which states that
aiobotocore support is out of scope for Moto, and the current primary Moto
maintainer suggested creating an aiomoto repo.

## Why in-process by default?

[pytest-aiomoto](https://github.com/dazza-codes/pytest-aiomoto) was an earlier
attempt at this but is not really maintained now. There is also discussion on the
aiobotocore repo about Moto support in
[aio-libs/aiobotocore#1300](https://github.com/aio-libs/aiobotocore/discussions/1300).

As far as I'm aware, both of those approaches rely on Moto's
[server mode](https://docs.getmoto.org/en/latest/docs/server_mode.html). aiomoto
makes in-process mode the default instead, for one reason: **speed**. In-process
mocking avoids the cost of spinning a Moto server up and down, which is also slower
than other local AWS services such as in-memory dynamodb-local. So the default mode
needs no server at all &mdash; aiomoto runs Moto-style mock contexts in the same
thread / process the tests run in.

[Server mode](../guides/server-mode.md) is still supported as an opt-in for the
cases that genuinely need a real HTTP endpoint &mdash; notably pandas / polars S3
I/O and other tooling that expects an endpoint.

Both modes are safe under parallel test runners such as
[pytest-xdist](https://pytest-xdist.readthedocs.io/): each worker is a separate
process, so server mode starts one Moto server per worker on an OS-assigned
ephemeral port with a fully isolated backend &mdash; no port clashes and no shared
state. Speed is the only reason to reach for in-process mode over server mode.

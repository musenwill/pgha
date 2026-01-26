#!/usr/bin/env python
from patroni.postgresql.misc import postgres_version_to_int, get_major_from_minor_version
from patroni.utils import get_postgres_version


if __name__ == '__main__':
    bin_minor = postgres_version_to_int(get_postgres_version("../pkg/postgres/bin", "postgres"))
    bin_major = get_major_from_minor_version(bin_minor)
    print(bin_minor, bin_major)

from contextvars import ContextVar


# Internal legacy callers remain able to read the old partition. The HTTP API
# always sets an authenticated owner or the distinct offline owner.
request_owner = ContextVar("request_owner", default="default_test_user")

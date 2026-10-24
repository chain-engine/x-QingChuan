import tomllib

with open(r"E:\01Codes\02GitHub\chain-engine\x-QingChuan\uv.lock", "rb") as f:
    lock = tomllib.load(f)

wanted = {
    "build", "bcrypt", "anyio", "attrs", "certifi", "aiohttp-retry",
    "apscheduler", "backoff", "cachetools", "annotated-doc", "annotated-types",
    "aiosqlite", "banks", "aiohttp", "watchfiles", "httpcore", "httpx", "httpx2",
    "multidict", "propcache", "limits", "narwhals", "networkx", "jinja2",
    "chromadb", "langchain", "langchain-text-splitters", "langfuse",
    "llama-index-core", "milvus-lite", "pymilvus", "pymupdf", "rank-bm25",
    "jsonpath-ng", "ml-dtypes", "python-ulid", "mypy-extensions", "rich",
    "distlib", "platformdirs", "python-discovery", "mpmath", "langgraph-checkpoint-redis",
}
found = {}
for pkg in lock.get("package", []):
    name = pkg.get("name")
    if name in wanted:
        found[name] = pkg.get("version")

missing = []
for w in sorted(wanted):
    v = found.get(w)
    if v:
        missing.append(f"{w}=={v}")
    else:
        print(f"# {w}=MISSING-IN-LOCK")
print(" ".join(missing))

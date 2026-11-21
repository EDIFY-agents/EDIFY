"""Python, parsed with the standard library's syntax tree.

Exact rather than scanned: every symbol below is a real definition, every import
edge is a real import, and a file that does not parse produces no symbols and says
so rather than producing plausible ones.
"""

from __future__ import annotations

import ast

from ..model import Edge, Extraction, Node, fingerprint, node_id

# Names a route decorator can carry. Recognising these is what puts an HTTP route
# on the map for the framework families that actually appear in Python services.
_ROUTE_DECORATORS = {
    "route", "get", "post", "put", "patch", "delete", "head", "options",
    "websocket", "api_route",
}
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "websocket"}


def extract(rel_path: str, source: str) -> Extraction:
    out = Extraction(languages={"python"})
    file_id = node_id("file", rel_path, ".")
    module_name = rel_path[:-3].replace("/", ".").removesuffix(".__init__")

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        # No nodes for a file we could not parse. A missing symbol is a visible
        # gap; an invented one is a fact-shaped guess.
        return out

    module_id = node_id("module", rel_path, ".")
    out.nodes.append(Node(module_id, "module", rel_path, 1, module_name))
    out.edges.append(Edge(file_id, "defines", module_id))

    owners: dict[int, str] = {}
    for node in tree.body:
        _visit_top(node, rel_path, module_id, out, "", owners)
    _scan(tree, file_id, owners, out)
    return out


def _visit_top(
    node: ast.AST, rel_path: str, module_id: str, out: Extraction, prefix: str, owners: dict[int, str]
) -> None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        name = prefix + node.name
        sym_id = _emit(node, name, rel_path, module_id, out, _signature(node))
        _routes(node, rel_path, sym_id, out)
        # Calls anywhere under this function, nested defs included, are its references.
        owners[id(node)] = sym_id

    elif isinstance(node, ast.ClassDef):
        name = prefix + node.name
        bases = ", ".join(_expr(b) for b in node.bases)
        sym_id = _emit(node, name, rel_path, module_id, out, f"class {node.name}({bases})")
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Methods are public surface; nesting stops at one level, which is
                # where the value stops and the churn starts.
                if not child.name.startswith("_") or child.name == "__init__":
                    _visit_top(child, rel_path, module_id, out, f"{name}.", owners)

    elif isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                name = prefix + target.id
                _emit(node, name, rel_path, module_id, out, f"{target.id} = ...")

    elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        if node.target.id.isupper():
            _emit(node, prefix + node.target.id, rel_path, module_id, out, f"{node.target.id}: ...")


def _emit(node: ast.AST, name: str, rel_path: str, module_id: str, out: Extraction, sig: str) -> str:
    sym_id = node_id("symbol", rel_path, name)
    line = getattr(node, "lineno", 1)
    out.nodes.append(Node(sym_id, "symbol", rel_path, line, name, fingerprint(sig)))
    out.edges.append(Edge(module_id, "defines", sym_id))
    return sym_id


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in node.args.posonlyargs + node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    args += [a.arg for a in node.args.kwonlyargs]
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {_expr(node.returns)}" if node.returns is not None else ""
    return f"{prefix} {node.name}({', '.join(args)}){returns}"


def _routes(node: ast.FunctionDef | ast.AsyncFunctionDef, rel_path: str, sym_id: str, out: Extraction) -> None:
    """Flask, FastAPI, Django-ninja and friends all decorate with a path literal."""
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        attr = dec.func
        if not isinstance(attr, ast.Attribute) or attr.attr not in _ROUTE_DECORATORS:
            continue
        path = None
        for arg in dec.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                path = arg.value
                break
        if path is None:
            continue
        method = attr.attr.upper() if attr.attr in _HTTP_METHODS else "ANY"
        name = f"{method} {path}"
        route_id = node_id("route", rel_path, name)
        out.nodes.append(Node(route_id, "route", rel_path, dec.lineno, name, fingerprint(name)))
        out.edges.append(Edge(route_id, "exposes", sym_id))


def _scan(tree: ast.AST, file_id: str, owners: dict[int, str], out: Extraction) -> None:
    """One walk for every import and every call.

    A call is a reference from the indexed function it sits under, resolved
    against the repository after the walk. Indexed functions never nest inside
    each other, so each call has at most one owner.
    """
    refs = out.pending_refs
    call, name_t, attr_t = ast.Call, ast.Name, ast.Attribute
    imports, node_t, ctx_t = (ast.Import, ast.ImportFrom), ast.AST, ast.expr_context
    stack: list[tuple[ast.AST, str | None]] = [(tree, None)]
    pop, push = stack.pop, stack.append
    while stack:
        node, owner = pop()
        kind = node.__class__
        if kind is call:
            if owner is not None:
                func = node.func  # type: ignore[attr-defined]
                if func.__class__ is name_t:
                    refs.append((owner, func.id, "references"))
                elif func.__class__ is attr_t:
                    refs.append((owner, func.attr, "references"))
        elif kind in imports:
            _imports(node, file_id, out)  # type: ignore[arg-type]
        elif owner is None:
            owner = owners.get(id(node))
        for f in node._fields:
            value = getattr(node, f, None)
            if value.__class__ is list:
                for item in value:
                    if isinstance(item, node_t):
                        push((item, owner))
            elif isinstance(value, node_t) and not isinstance(value, ctx_t):
                push((value, owner))


def _imports(node: ast.Import | ast.ImportFrom, file_id: str, out: Extraction) -> None:
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.pending_refs.append((file_id, alias.name, "imports"))
    elif node.module and not node.level:
        out.pending_refs.append((file_id, node.module, "imports"))
        for alias in node.names:
            out.pending_refs.append((file_id, f"{node.module}.{alias.name}", "imports"))
    elif node.level:
        # A relative import resolves against this file's own package, which the
        # resolver knows and this pass does not.
        base = node.module or ""
        out.pending_refs.append((file_id, "." * node.level + base, "imports"))
        for alias in node.names:
            joined = f"{base}.{alias.name}" if base else alias.name
            out.pending_refs.append((file_id, "." * node.level + joined, "imports"))


def _expr(node: ast.AST | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - unparse covers everything we emit
        return type(node).__name__

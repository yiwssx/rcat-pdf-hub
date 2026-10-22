#!/usr/bin/env python3
"""T90-0: validate source-mapped parameter contracts without changing runtime behavior.

Standard-library only: inspect declared request-model fields and route bindings,
not dynamic imports, execution of registry strings, or worker dispatch.
"""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMETERS = ROOT / "contracts/pdf-operation-parameters.v1.json"
CAPABILITIES = ROOT / "contracts/pdf-tools.v1.json"
SCHEMAS = ROOT / "apps/api/app/schemas.py"
ROUTES = ROOT / "apps/api/app/routers/pdf.py"
PRIMITIVE_NAMES = {"str": "string", "int": "integer", "float": "number", "bool": "boolean"}
VALID_TYPES = {"string", "integer", "number", "boolean", "array", "object"}
PARAMETER_STATUSES = {"legacy_projection", "pending_design"}


def literal(node):
    return ast.literal_eval(node)


def descriptor(annotation, aliases):
    if isinstance(annotation, ast.Name):
        if annotation.id in PRIMITIVE_NAMES:
            return PRIMITIVE_NAMES[annotation.id], False, None
        if annotation.id in aliases:
            return "string", False, aliases[annotation.id]
        return annotation.id, False, None
    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        if annotation.value.id == "list":
            return "array", False, None
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        left, _, enum = descriptor(annotation.left, aliases)
        if isinstance(annotation.right, ast.Constant) and annotation.right.value is None:
            return left, True, enum
        if isinstance(annotation.left, ast.Constant) and annotation.left.value is None:
            right, _, enum = descriptor(annotation.right, aliases)
            return right, True, enum
    raise ValueError(f"Unsupported request annotation: {ast.dump(annotation)}")


def inspect_source_models(source, target_models):
    tree = ast.parse(source)
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key, value = node.targets[0].id, node.value
            if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name) and value.value.id == "Literal":
                aliases[key] = [literal(v) for v in value.slice.elts] if isinstance(value.slice, ast.Tuple) else [literal(value.slice)]
    models = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name not in target_models:
            continue
        fields = {}
        for item in node.body:
            if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
                continue
            kind, nullable, enum = descriptor(item.annotation, aliases)
            desc = {"type": kind, "nullable": nullable, "required": item.value is None}
            if enum is not None:
                desc["enum"] = enum
            if item.value is not None and isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "Field":
                desc["required"] = not any(keyword.arg == "default" for keyword in item.value.keywords)
                arguments = {keyword.arg: literal(keyword.value) for keyword in item.value.keywords if keyword.arg and keyword.arg in {
                    "default", "ge", "le", "min_length", "max_length", "pattern"
                }}
                if "default" in arguments:
                    desc["default"] = arguments["default"]
                    desc["required"] = False
                for src, dst in (("ge", "minimum"), ("le", "maximum"), ("min_length", "min_length"), ("max_length", "max_length"), ("pattern", "pattern")):
                    if src in arguments:
                        desc[dst] = arguments[src]
            elif item.value is not None:
                desc["default"] = literal(item.value)
                desc["required"] = False
            fields[item.target.id] = desc
        if fields:
            models[node.name] = fields
    return models


def inspect_routes(source):
    tree = ast.parse(source)
    routes = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute) or dec.func.attr != "post" or not dec.args:
                continue
            route = literal(dec.args[0])
            if not isinstance(route, str):
                continue
            model = None
            for arg in node.args.args:
                if arg.arg == "req" and isinstance(arg.annotation, ast.Name):
                    model = arg.annotation.id
            submitted = set()
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "_create_job":
                    if len(call.args) > 2 and isinstance(call.args[2], ast.Constant):
                        submitted.add(call.args[2].value)
            routes["/api/v1/pdf" + route] = (model, submitted)
    return routes


def validate(contract, capabilities, models, routes):
    errors = []
    def fail(message):
        errors.append(message)

    if contract.get("schema_version") != "1.0.0" or contract.get("status") != "source-mapped-planning-only":
        fail("parameter document must be versioned and planning-only")
    definitions = contract.get("operations")
    baseline = capabilities.get("existing", {}).get("backend_operations", [])
    if not isinstance(definitions, dict) or set(definitions) != set(baseline) or len(definitions) != 13:
        return errors + ["parameter definitions must map exactly 13 baseline operations"]
    for operation, definition in definitions.items():
        context = f"{operation}"
        if not isinstance(definition, dict):
            fail(context + ": invalid definition")
            continue
        route, model = definition.get("route"), definition.get("request_model")
        if route not in routes or routes[route][0] != model or operation not in routes[route][1]:
            fail(context + ": route/model/dispatch binding drift")
        source_fields = models.get(model)
        if not source_fields:
            fail(context + ": request model absent")
            continue
        selectors = definition.get("selector_fields")
        ignored = definition.get("ignored_request_fields")
        parameters = definition.get("parameters")
        if not isinstance(selectors, list) or not isinstance(ignored, list) or not isinstance(parameters, dict):
            fail(context + ": invalid selector/ignored/parameter types")
            continue
        combined = selectors + ignored + list(parameters)
        if len(set(combined)) != len(combined) or set(combined) != set(source_fields):
            fail(context + ": request fields not exactly classified")
        if any(field not in {"file_id", "file_ids", "stamp_file_id"} for field in selectors):
            fail(context + ": invalid selector field")
        for name, field in parameters.items():
            if not isinstance(field, dict) or field.get("type") not in VALID_TYPES or type(field.get("required")) is not bool:
                fail(context + ": invalid typed parameter " + name)
                continue
            source = source_fields.get(name)
            if source is None:
                fail(context + ": missing source parameter " + name)
                continue
            if field.get("type") != source["type"] or field["required"] != source["required"]:
                fail(context + ": parameter type/required drift " + name)
            for attribute in ("default", "minimum", "maximum", "min_length", "max_length", "pattern", "nullable"):
                if field["type"] == "array" and attribute in {"min_length", "max_length"}:
                    continue
                if attribute == "nullable" and not source["nullable"] and attribute not in field:
                    continue
                if field.get(attribute, object()) != source.get(attribute, object()):
                    # Missing values compare as missing on both sides (except nullable above).
                    if attribute not in field and attribute not in source:
                        continue
                    fail(context + ": parameter constraint/default drift " + name + "." + attribute)
            if "enum" in source and field.get("enum") != source["enum"]:
                fail(context + ": alias enumeration drift " + name)
            if "enum" in field and (not isinstance(field["enum"], list) or len(field["enum"]) == 0 or len(set(map(str,field["enum"]))) != len(field["enum"])):
                fail(context + ": invalid enum " + name)
            if field["type"] == "array":
                nested = field.get("items")
                if not isinstance(nested, dict) or nested.get("type") != "object" or not isinstance(nested.get("properties"), dict):
                    fail(context + ": array lacks typed item shape " + name)
                if context == "organize" and name == "pages" and isinstance(nested, dict) and isinstance(nested.get("properties"), dict):
                    child = models.get("OrganizePage", {})
                    if set(nested["properties"]) != set(child) or set(nested.get("required_properties", [])) != {k for k, v in child.items() if v.get("required")}:
                        fail(context + ": nested page fields drift")
                    for child_name, child_field in nested["properties"].items():
                        source_child = child.get(child_name, {})
                        for attr in ("type", "minimum", "maximum", "default"):
                            if attr in source_child and child_field.get(attr) != source_child[attr]:
                                fail(context + ": nested page property drift " + child_name + "." + attr)
                if "min_items" in field and field["min_items"] != source.get("min_length"):
                    fail(context + ": array lower-bound drift " + name)
                if "max_items" in field and field["max_items"] != source.get("max_length"):
                    fail(context + ": array upper-bound drift " + name)
        if not isinstance(definition.get("notes"), list):
            fail(context + ": missing implementation notes")
    entries = capabilities.get("tools", [])
    if not isinstance(entries, list) or len(entries) != 90:
        return errors + ["capability registry missing 90 tool entries"]
    for tool in entries:
        mapping = tool.get("legacy", {}).get("operations", [])
        reference = tool.get("parameter_contract", {})
        if reference.get("status") not in PARAMETER_STATUSES:
            fail(str(tool.get("id")) + ": missing contract readiness")
            continue
        refs = reference.get("operation_refs")
        if not isinstance(refs, list) or refs != mapping or any(op not in definitions for op in refs):
            fail(str(tool.get("id")) + ": contract reference drift")
        if reference.get("status") != ("legacy_projection" if mapping else "pending_design"):
            fail(str(tool.get("id")) + ": inflated parameter readiness")
        if tool.get("runtime_enabled") is not False:
            fail(str(tool.get("id")) + ": planned tool enabled without runtime approval")
    return errors


def main():
    params = json.loads(PARAMETERS.read_text(encoding="utf-8"))
    capabilities = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    models = inspect_source_models(
        SCHEMAS.read_text(encoding="utf-8"),
        {item["request_model"] for item in params["operations"].values()} | {"OrganizePage"},
    )
    routes = inspect_routes(ROUTES.read_text(encoding="utf-8"))
    errors = validate(params, capabilities, models, routes)
    for problem in errors:
        print("T90 parameters FAIL: " + problem, file=sys.stderr)
    if errors:
        return 1
    projected = sum(t["parameter_contract"]["status"] == "legacy_projection" for t in capabilities["tools"])
    print(f"T90 parameters: PASS (13 legacy schemas, {projected} tool projections, {90-projected} pending, 0 new routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

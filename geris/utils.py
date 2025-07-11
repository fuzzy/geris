import inspect
from typing import get_args, get_origin


def func2tool(p):
    retv = {
        "type": "function",
        "function": {
            "parameters": {"type": "object", "properties": {}, "required": []}
        },
    }
    data = [
        [tuple(tkn.split(":")) for tkn in ln.split("; ")]
        for ln in p.__doc__.split("\n")
    ]
    sig = inspect.signature(p)

    # type helper
    def typeof(n):
        if n is str or n == "str":
            return {"type": "string"}
        elif n is int or n == "int":
            return {"type": "integer"}
        elif n is float or n == "float":
            return {"type": "number"}
        elif n is bool or n == "bool":
            return {"type": "boolean"}
        elif get_origin(n) is list:
            _retv = {"type": "array", "items": typeof(get_args(n)[0])}
            return _retv
        else:
            return {"type": "unknown"}

    # parse function name and arg types out of inspect data
    retv["function"]["name"] = p.__name__
    for k, v in sig.parameters.items():
        val = typeof(v.annotation)
        retv["function"]["parameters"]["properties"][k] = val

    # now parse the docstring to fill in extra details
    for datum in data:
        key = datum[0][0]
        keys = retv["function"]["parameters"]["properties"].keys()
        for item in datum:
            if item[0] == "description" and key not in keys:
                retv["function"][item[0]] = item[1]
            elif item[0] == "required" and key not in keys:
                retv["function"]["parameters"]["required"] = item[1].split(",")
            elif item[0] in keys:
                retv["function"]["parameters"]["properties"][item[0]]["description"] = (
                    item[1]
                )
            elif item[0] == "enum" and key in keys:
                retv["function"]["parameters"]["properties"][key][item[0]] = item[
                    1
                ].split(",")
            elif item[0] == "default" and key in keys:
                retv["function"]["parameters"]["properties"][key][item[0]] = item[1]

    return retv

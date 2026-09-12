"""Evaluate the export's small formula vocabulary and store XLSX cached values.

openpyxl writes formulas but does not calculate them. Cached results let preview
readers display the export before Excel performs its next recalculation.
"""

import ast
import json
import operator
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from openpyxl.formula.tokenizer import Tokenizer


def formula_values(workbook):
    """Evaluate only supported export expressions, without executing Python code."""
    results = {}
    visiting = set()

    def numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

    def cell_value(sheet_name, coordinate):
        key = sheet_name, coordinate
        if key in results:
            return results[key]
        if key in visiting:
            raise ValueError(f"Circular export formula at {sheet_name}!{coordinate}")
        cell = workbook[sheet_name][coordinate]
        if cell.data_type != "f":
            return cell.value
        visiting.add(key)
        expression = []
        for token in Tokenizer(cell.value).items:
            if token.subtype == "RANGE":
                target_sheet, separator, target_cell = token.value.rpartition("!")
                if not separator:
                    target_sheet, target_cell = sheet_name, token.value
                elif target_sheet.startswith("'"):
                    target_sheet = target_sheet[1:-1].replace("''", "'")
                expression.append(f"CELL({json.dumps(target_sheet)},{json.dumps(target_cell)})")
            elif token.subtype == "TEXT":
                expression.append(json.dumps(token.value[1:-1].replace('""', '"')))
            elif token.type == "OPERATOR-INFIX" and token.value == "<>":
                expression.append("!=")
            else:
                expression.append(token.value)
        result = evaluate(ast.parse("".join(expression), mode="eval").body)
        visiting.remove(key)
        results[key] = result
        return result

    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            operation = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Div: operator.truediv}.get(type(node.op))
            if operation:
                return operation(evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            operation = {ast.NotEq: operator.ne, ast.Gt: operator.gt}.get(type(node.ops[0]))
            if operation:
                return operation(evaluate(node.left), evaluate(node.comparators[0]))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            name = node.func.id
            if name == "IF" and len(node.args) == 3:
                return evaluate(node.args[1] if evaluate(node.args[0]) else node.args[2])
            args = [evaluate(arg) for arg in node.args]
            if name == "CELL" and len(args) == 2:
                return cell_value(*args)
            if name == "ISNUMBER" and len(args) == 1:
                return numeric(args[0])
            if name == "AND":
                return all(args)
            numbers = [value for value in args if numeric(value)]
            if name == "COUNT":
                return len(numbers)
            if name == "SUM":
                return sum(numbers)
            if name == "AVERAGE" and numbers:
                return sum(numbers) / len(numbers)
        raise ValueError("Unsupported export formula expression")

    for sheet in workbook:
        for row in sheet:
            for cell in row:
                if cell.data_type == "f":
                    cell_value(sheet.title, cell.coordinate)
    return results


def save_with_formula_results(workbook) -> bytes:
    """Preserve formulas and attach calculated numeric/text results to their XML."""
    results = formula_values(workbook)
    source = BytesIO()
    workbook.save(source)
    output = BytesIO()
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    tag = lambda name: f"{{{namespace}}}{name}"
    sheets = {f"xl/worksheets/sheet{index}.xml": sheet.title
              for index, sheet in enumerate(workbook, 1)}
    with ZipFile(source) as original, ZipFile(output, "w") as saved:
        for entry in original.infolist():
            data = original.read(entry.filename)
            if entry.filename in sheets:
                root = ET.fromstring(data)
                for cell in root.iter(tag("c")):
                    key = sheets[entry.filename], cell.get("r")
                    if key not in results:
                        continue
                    result = results[key]
                    cell.set("t", "str" if isinstance(result, str) else "n")
                    value = cell.find(tag("v"))
                    if value is None:
                        value = ET.SubElement(cell, tag("v"))
                    value.text = str(result)
                data = ET.tostring(root, encoding="utf-8")
            saved.writestr(entry, data)
    return output.getvalue()

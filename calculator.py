import ast
import math
import operator
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Calculator API")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class Calculation(BaseModel):
	expression: str


OPERATORS = {
	ast.Add: operator.add,
	ast.Sub: operator.sub,
	ast.Mult: operator.mul,
	ast.Div: operator.truediv,
	ast.Mod: operator.mod,
	ast.Pow: operator.pow,
}
UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def evaluate(node: ast.AST) -> int | float:
	if isinstance(node, ast.Expression):
		return evaluate(node.body)
	if isinstance(node, ast.Constant) and type(node.value) in (int, float):
		if not math.isfinite(node.value):
			raise ValueError("Numbers must be finite")
		return node.value
	if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
		left = evaluate(node.left)
		right = evaluate(node.right)
		if isinstance(node.op, ast.Pow) and abs(right) > 100:
			raise ValueError("Exponent is too large")
		result = OPERATORS[type(node.op)](left, right)
		if type(result) not in (int, float) or not math.isfinite(result):
			raise ValueError("Result must be a finite real number")
		return result
	if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPERATORS:
		return UNARY_OPERATORS[type(node.op)](evaluate(node.operand))
	raise ValueError("Only basic arithmetic expressions are supported")


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
	return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/cacl")
@app.post("/api/calc", include_in_schema=False)
async def calculate(payload: Calculation) -> dict[str, int | float]:
	expression = payload.expression.strip()
	if not expression or len(expression) > 256:
		raise HTTPException(status_code=400, detail="Enter an expression up to 256 characters")
	try:
		tree = ast.parse(expression, mode="eval")
		if sum(1 for _ in ast.walk(tree)) > 128:
			raise ValueError("Expression is too complex")
		result = evaluate(tree)
	except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as error:
		raise HTTPException(status_code=400, detail=str(error) or "Invalid expression") from error
	return {"result": result}
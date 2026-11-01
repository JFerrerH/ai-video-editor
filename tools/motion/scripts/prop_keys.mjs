// Declared props of every overlay component and scene primitive, read from their TypeScript types.
//
//   node scripts/prop_keys.mjs              → {"<Name>": {"file": "src/…/<Name>.tsx", "keys": ["lines", "lines[].at", …]}}
//   node scripts/prop_keys.mjs --skeleton X → a draft <X>.schema.json from the types (annotate it by hand)
//
// The coverage test (tools/tests/test_overlay_schema.py) compares `keys` with each schema's
// properties in both directions. Nested keys are listed for object and array-of-object props whose
// type is declared in src/ (not React or CSS types). `durationInFrames` is the engine's, never listed.
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.join(ROOT, "src");
const ENGINE_KEYS = new Set(["durationInFrames"]);
const MAX_DEPTH = 3;

const program = ts.createProgram([path.join(SRC, "Overlay.tsx"), path.join(SRC, "scenes/index.ts")], {
  jsx: ts.JsxEmit.ReactJSX,
  module: ts.ModuleKind.Preserve,
  moduleResolution: ts.ModuleResolutionKind.Bundler,
  target: ts.ScriptTarget.ES2018,
  strict: true,
  esModuleInterop: true,
  skipLibCheck: true,
  noEmit: true,
});
const checker = program.getTypeChecker();

/** name → declaration of each entry of `export const <block> = { A, B, … }` in a file. */
function registry(file, block) {
  const sf = program.getSourceFile(path.join(SRC, file));
  const out = new Map();
  ts.forEachChild(sf, (node) => {
    if (!ts.isVariableStatement(node)) return;
    for (const d of node.declarationList.declarations) {
      if (d.name.getText(sf) !== block || !d.initializer || !ts.isObjectLiteralExpression(d.initializer)) continue;
      for (const p of d.initializer.properties) {
        let sym = ts.isShorthandPropertyAssignment(p)
          ? checker.getShorthandAssignmentValueSymbol(p)
          : checker.getSymbolAtLocation(p.initializer);
        if (sym && sym.flags & ts.SymbolFlags.Alias) sym = checker.getAliasedSymbol(sym);
        out.set(p.name.getText(sf), sym);
      }
    }
  });
  return out;
}

const ownType = (t) =>
  (t.aliasSymbol ?? t.symbol)?.declarations?.some((d) => {
    const f = d.getSourceFile().fileName;
    return f.startsWith(SRC) && !f.includes("node_modules");
  }) ?? false;

const nonNullable = (t) => (t.isUnion() ? checker.getNonNullableType(t) : t);

/** The object type to descend into for a prop (its element type for arrays), or null. */
function inner(t) {
  t = nonNullable(t);
  if (checker.isArrayType(t)) t = nonNullable(checker.getTypeArguments(t)[0]);
  if (t.isUnion() || !(t.flags & ts.TypeFlags.Object) || t.getCallSignatures().length) return null;
  if (checker.isArrayType(t)) return null;
  return ownType(t) || (t.objectFlags & ts.ObjectFlags.Anonymous) ? t : null;
}

function keys(t, prefix, depth, out) {
  for (const p of checker.getPropertiesOfType(t)) {
    if (!prefix && ENGINE_KEYS.has(p.name)) continue;
    const pt = checker.getTypeOfSymbol(p);
    const isArr = checker.isArrayType(nonNullable(pt));
    const key = prefix + p.name;
    out.push(key);
    const sub = depth < MAX_DEPTH ? inner(pt) : null;
    if (sub && sub.getProperties().length && !checker.getIndexInfosOfType(sub).length) {
      keys(sub, key + (isArr ? "[]." : "."), depth + 1, out);
    }
  }
  return out;
}

function propsType(sym) {
  const decl = sym.valueDeclaration ?? sym.declarations[0];
  const sig = checker.getTypeOfSymbolAtLocation(sym, decl).getCallSignatures()[0];
  return { type: checker.getTypeOfSymbolAtLocation(sig.getParameters()[0], decl), file: decl.getSourceFile().fileName };
}

// ── skeleton: JSON-schema draft from a type ──────────────────────────────
function schemaOf(t, depth) {
  const optional = t.isUnion() && t.types.some((x) => x.flags & ts.TypeFlags.Undefined);
  const nullable = t.isUnion() && t.types.some((x) => x.flags & ts.TypeFlags.Null);
  t = nonNullable(t);
  if (nullable) {
    const s = schemaOf(t, depth);
    return { ...s, type: [...[s.type].flat(), "null"], ...(s.enum ? { enum: [...s.enum, null] } : {}) };
  }
  if (t.isUnion()) {
    const lits = t.types.filter((x) => x.isLiteral() || x.flags & ts.TypeFlags.BooleanLiteral);
    if (lits.length === t.types.length && t.types.every((x) => x.isStringLiteral())) {
      return { type: "string", enum: t.types.map((x) => x.value) };
    }
    if (t.types.every((x) => x.flags & ts.TypeFlags.BooleanLiteral)) return { type: "boolean" };
    if (t.types.every((x) => x.isNumberLiteral())) return { type: "number", enum: t.types.map((x) => x.value) };
    const kinds = [...new Set(t.types.map((x) => schemaOf(x, depth).type).flat())].filter(Boolean);
    return { type: kinds.length === 1 ? kinds[0] : kinds };
  }
  if (t.flags & ts.TypeFlags.StringLike) return t.isStringLiteral() ? { type: "string", enum: [t.value] } : { type: "string" };
  if (t.flags & ts.TypeFlags.NumberLike) return { type: "number" };
  if (t.flags & ts.TypeFlags.BooleanLike) return { type: "boolean" };
  if (checker.isArrayType(t)) return { type: "array", items: schemaOf(checker.getTypeArguments(t)[0], depth + 1) };
  if (checker.isTupleType(t)) return { type: "array", items: schemaOf(checker.getTypeArguments(t)[0], depth + 1) };
  if (t.flags & ts.TypeFlags.Object && !t.getCallSignatures().length) {
    const idx = checker.getIndexInfosOfType(t);
    if (idx.length) return { type: "object", additionalProperties: schemaOf(idx[0].type, depth + 1) };
    if (depth > MAX_DEPTH || !(ownType(t) || t.objectFlags & ts.ObjectFlags.Anonymous)) return { type: "object", additionalProperties: true };
    const properties = {};
    const required = [];
    for (const p of checker.getPropertiesOfType(t)) {
      if (depth === 0 && ENGINE_KEYS.has(p.name)) continue;
      properties[p.name] = schemaOf(checker.getTypeOfSymbol(p), depth + 1);
      if (!(p.flags & ts.SymbolFlags.Optional)) required.push(p.name);
    }
    return { type: "object", ...(required.length ? { required } : {}), properties };
  }
  return optional ? {} : { "x-unsupported": checker.typeToString(t) };
}

const all = new Map([...registry("Overlay.tsx", "REGISTRY"), ...registry("scenes/index.ts", "SCENES")]);
all.delete("Captions"); // engine-owned: built by shortform.caption_event(), never written in a spec

const skel = process.argv.indexOf("--skeleton");
if (skel >= 0) {
  const name = process.argv[skel + 1];
  if (!all.has(name)) throw new Error(`no component ${name}`);
  const { type } = propsType(all.get(name));
  console.log(JSON.stringify({ title: name, "x-layout": "float", ...schemaOf(type, 0) }, null, 2));
} else {
  const out = {};
  for (const [name, sym] of [...all].sort()) {
    const { type, file } = propsType(sym);
    out[name] = { file: path.relative(ROOT, file), keys: keys(type, "", 0, []) };
  }
  console.log(JSON.stringify(out, null, 1));
}

/**
 * Static checks for the frontend, with no dependencies.
 *
 *     node frontend/check.mjs
 *
 * Why not ESLint: it means npm, a `node_modules`, and a build-adjacent
 * toolchain, which `_docs/decisions.md` #3 deliberately avoided. That trade can
 * be revisited — it is a real one, and a real linter would catch more than this
 * does — but it is the user's call, not something to slip in through a lint task.
 *
 * What this catches without any of that:
 *
 *   - syntax errors, via `node --check` on every module;
 *   - imports that point at files which do not exist;
 *   - imported names a module does not export;
 *   - imports that are never used.
 *
 * That is most of what actually breaks a no-build frontend: a typo'd path or a
 * renamed export, neither of which shows up until the browser hits that line.
 */

import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { readdirSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const problems = [];

function walk(dir) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) found.push(...walk(full));
    else if (entry.endsWith(".js") || entry.endsWith(".mjs")) found.push(full);
  }
  return found;
}

const files = walk(join(ROOT, "src"));

/* ---------------------------------------------------------------- syntax */

const scratch = mkdtempSync(join(tmpdir(), "nextlane-check-"));
try {
  for (const file of files) {
    const copy = join(scratch, "module.mjs");
    writeFileSync(copy, readFileSync(file));
    try {
      execFileSync(process.execPath, ["--check", copy], { stdio: "pipe" });
    } catch (error) {
      const detail = String(error.stderr || error.message)
        .split("\n")
        .find((line) => line.includes("Error")) || "syntax error";
      problems.push(`${relative(ROOT, file)}: ${detail.trim()}`);
    }
  }
} finally {
  rmSync(scratch, { recursive: true, force: true });
}

/* ------------------------------------------------------- imports/exports */

const exported = new Map();
const imported = [];

for (const file of files) {
  const source = readFileSync(file, "utf8");

  const names = new Set();
  for (const match of source.matchAll(/^export\s+(?:async\s+)?(?:function|const|let|class)\s+(\w+)/gm)) {
    names.add(match[1]);
  }
  for (const match of source.matchAll(/^export\s*\{([^}]*)\}/gm)) {
    for (const part of match[1].split(",")) {
      const name = part.trim().split(/\s+as\s+/).pop();
      if (name) names.add(name.trim());
    }
  }
  exported.set(file, names);

  for (const match of source.matchAll(/import\s*(?:\{([^}]*)\}|\*\s*as\s*\w+|\w+)?\s*from\s*["'](\.[^"']+)["']/g)) {
    imported.push({
      file,
      names: (match[1] || "")
        .split(",")
        .map((part) => part.trim().split(/\s+as\s+/)[0].trim())
        .filter(Boolean),
      target: resolve(dirname(file), match[2]),
      source,
    });
  }
}

for (const entry of imported) {
  if (!exported.has(entry.target)) {
    problems.push(
      `${relative(ROOT, entry.file)}: imports ${relative(ROOT, entry.target)}, which does not exist`
    );
    continue;
  }

  const available = exported.get(entry.target);
  for (const name of entry.names) {
    if (!available.has(name)) {
      problems.push(
        `${relative(ROOT, entry.file)}: imports "${name}" from ` +
          `${relative(ROOT, entry.target)}, which does not export it`
      );
      continue;
    }

    // Count uses outside the import statement itself.
    const uses = entry.source.match(new RegExp(`\\b${name}\\b`, "g")) || [];
    if (uses.length < 2) {
      problems.push(`${relative(ROOT, entry.file)}: imports "${name}" but never uses it`);
    }
  }
}

/* --------------------------------------------------------------- verdict */

if (problems.length) {
  console.error(`frontend: ${problems.length} problem(s)\n`);
  for (const problem of problems) console.error(`  ${problem}`);
  process.exit(1);
}

console.log(`frontend: ${files.length} modules checked, all clean`);

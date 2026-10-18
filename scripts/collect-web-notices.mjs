// SPDX-License-Identifier: Apache-2.0
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const output = path.resolve(process.argv[2] ?? ".opencommerce/web-legal");
const appName = process.argv[3] ?? "web";
if (!/^[a-z][a-z0-9-]{0,39}$/.test(appName)) throw new Error("invalid app name");
const standalone = path.join(root, `apps/${appName}/.next/standalone`);
const seen = new Set();
const packages = [];
const legalName = /(^|[._-])(licen[sc]e|notice|copying|copyright|authors)([._-]|$)|third.?party.*notic/i;

function legalFiles(directory, relative = "") {
  const files = [];
  for (const entry of readdirSync(path.join(directory, relative), { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".git") continue;
    const name = path.join(relative, entry.name);
    if (entry.isDirectory()) files.push(...legalFiles(directory, name));
    else if (entry.isFile() && legalName.test(entry.name)) files.push(name);
  }
  return files.sort();
}

function visit(directory) {
  directory = realpathSync(directory);
  if (seen.has(directory)) return;
  seen.add(directory);
  const manifest = JSON.parse(readFileSync(path.join(directory, "package.json"), "utf8"));
  const id = `${manifest.name}@${manifest.version}`;
  const firstParty = manifest.name.startsWith("@open-commerce/") || manifest.name === "open-commerce-agent";
  if (!firstParty) {
    let noticeDirectory = directory;
    let files = legalFiles(directory);
    let source = "installed package";
    if (!files.length && id === "@next/env@15.5.27") {
      noticeDirectory = path.join(root, "security/third-party/next-15.5.27");
      files = ["LICENSE"];
      source = "https://raw.githubusercontent.com/vercel/next.js/v15.5.27/license.md";
    }
    if (!files.length && id === "client-only@0.0.1") {
      noticeDirectory = path.join(root, "security/third-party/react-19.2.8");
      files = ["LICENSE"];
      source = "https://raw.githubusercontent.com/facebook/react/v19.2.8/LICENSE";
    }
    if (!files.length && manifest.name.startsWith("@img/sharp-libvips-") && manifest.version === "1.3.4") {
      noticeDirectory = path.join(root, "security/third-party/sharp-libvips-1.3.4");
      files = ["THIRD-PARTY-NOTICES.md", "native-manifest.json", "native-notices.tar.gz"];
      const native = JSON.parse(readFileSync(path.join(noticeDirectory, "native-manifest.json"), "utf8"));
      const actualVersions = JSON.parse(readFileSync(path.join(directory, "versions.json"), "utf8"));
      const keys = Object.keys(actualVersions).sort();
      if (!native.complete || JSON.stringify(keys) !== JSON.stringify(Object.keys(native.versions).sort()) ||
          keys.some((key) => native.versions[key] !== actualVersions[key])) {
        throw new Error(`${id}: native notice inventory does not match the shipped library`);
      }
      const nativeBytes = readFileSync(path.join(noticeDirectory, "native-notices.tar.gz"));
      if (createHash("sha256").update(nativeBytes).digest("hex") !== native.bundle_sha256) {
        throw new Error(`${id}: native notice archive hash differs`);
      }
      source = "https://github.com/lovell/sharp-libvips/tree/ebb95f8add54eee8bed840e3fb587e4cbec857d7";
    }
    if (!files.length) throw new Error(`${id}: no upstream legal text found`);
    const records = files.map((relative) => {
      const bytes = readFileSync(path.join(noticeDirectory, relative));
      const destination = path.join(output, "third-party", id, relative);
      mkdirSync(path.dirname(destination), { recursive: true });
      writeFileSync(destination, bytes);
      return { path: relative, sha256: createHash("sha256").update(bytes).digest("hex") };
    });
    if (manifest.name.startsWith("@img/sharp-libvips-")) {
      for (const relative of ["README.md", "versions.json"]) {
        const bytes = readFileSync(path.join(directory, relative));
        const destination = path.join(output, "third-party", id, relative);
        mkdirSync(path.dirname(destination), { recursive: true });
        writeFileSync(destination, bytes);
        records.push({ path: relative, sha256: createHash("sha256").update(bytes).digest("hex") });
      }
    }
    packages.push({ name: manifest.name, version: manifest.version, license: manifest.license ?? null, source, files: records });
  }
}

function inspectBundle(directory) {
  const relative = path.relative(standalone, directory);
  if (relative.includes("/next/dist/compiled/")) return;
  const metadata = path.join(directory, "package.json");
  if (existsSync(metadata)) {
    const bundled = JSON.parse(readFileSync(metadata, "utf8"));
    if (bundled.name && bundled.version) {
      const source = path.join(root, relative);
      const installed = JSON.parse(readFileSync(path.join(source, "package.json"), "utf8"));
      if (installed.name !== bundled.name || installed.version !== bundled.version) {
        throw new Error(`stale standalone package: ${bundled.name}`);
      }
      visit(source);
    }
  }
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) inspectBundle(path.join(directory, entry.name));
  }
}

if (existsSync(output)) throw new Error("choose a new notice output directory");
mkdirSync(output, { recursive: true });
inspectBundle(standalone);
if (!packages.some((entry) => entry.name === "next")) throw new Error("standalone Next.js dependency is absent");
packages.sort((a, b) => `${a.name}@${a.version}`.localeCompare(`${b.name}@${b.version}`, "en"));
writeFileSync(path.join(output, "manifest.json"), JSON.stringify({ scope: "actual standalone packages and their compiled notices; upstream text bytes unchanged", packages }, null, 2) + "\n");
console.log(`Collected original legal files for ${packages.length} runtime packages`);

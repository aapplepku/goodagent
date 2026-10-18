import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";
import { format } from "prettier";

const raw = await readFile(process.argv[2], "utf8");
const schema = JSON.parse(raw);
const ast = await openapiTS(schema, {
  alphabetize: true,
  defaultNonNullable: false,
  silent: true,
});
const names = new Set();
const aliases = Object.keys(schema.components.schemas)
  .sort()
  .map((key) => {
    const name = key.replace(/-Output$/, "").replace(/-Input$/, "Input");
    if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(name) || names.has(name)) {
      throw new Error(`Ambiguous TypeScript component alias: ${key}`);
    }
    names.add(name);
    return `export type ${name} = components["schemas"][${JSON.stringify(key)}];`;
  });
aliases.push(
  'export type ScenarioId = components["schemas"]["ScenarioSummary"]["id"];',
  'export type RankingMode = NonNullable<components["schemas"]["SearchRequest"]["mode"]>;',
  'export type ServiceStatus = components["schemas"]["MetaResponse"]["status"];',
);
const source = `/* Generated from openapi/openapi.json by openapi-typescript. Do not edit. */
/* Schema SHA-256: ${createHash("sha256").update(raw).digest("hex")} */
${astToString(ast)}
${aliases.join("\n")}
`;
process.stdout.write(
  await format(source, {
    parser: "typescript",
    printWidth: 100,
    trailingComma: "none",
  }),
);

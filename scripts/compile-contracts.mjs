import fs from "node:fs";
import solc from "solc";
const sources = Object.fromEntries(
  fs
    .readdirSync("contracts/src")
    .map((name) => [
      name,
      { content: fs.readFileSync(`contracts/src/${name}`, "utf8") },
    ]),
);
const output = JSON.parse(
  solc.compile(
    JSON.stringify({
      language: "Solidity",
      sources,
      settings: {
        optimizer: { enabled: true, runs: 200 },
        outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } },
      },
    }),
  ),
);
for (const error of output.errors ?? []) console.error(error.formattedMessage);
if (output.errors?.some((error) => error.severity === "error")) process.exit(1);
for (const [file, contracts] of Object.entries(output.contracts)) {
  fs.mkdirSync(`contracts/out/${file}`, { recursive: true });
  for (const [name, artifact] of Object.entries(contracts))
    fs.writeFileSync(
      `contracts/out/${file}/${name}.json`,
      JSON.stringify({
        abi: artifact.abi,
        bytecode: { object: `0x${artifact.evm.bytecode.object}` },
      }),
    );
}

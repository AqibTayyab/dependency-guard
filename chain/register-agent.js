// SPDX-License-Identifier: Apache-2.0
// Registers the agent on Solana devnet using the 8004-solana SDK.

const fs = require("fs");
const { Connection, Keypair, clusterApiUrl } = require("@solana/web3.js");
const { SolanaSDK } = require("8004-solana");

async function main() {
  const keyPath = process.env.DEPGUARD_KEYPAIR_PATH;
  if (!keyPath) throw new Error("Set DEPGUARD_KEYPAIR_PATH to your keypair file");

  const secret = Uint8Array.from(JSON.parse(fs.readFileSync(keyPath, "utf8")));
  const kp = Keypair.fromSecretKey(secret);

  const connection = new Connection(clusterApiUrl("devnet"), "confirmed");
  const sdk = new SolanaSDK({ cluster: "devnet", wallet: kp });

  console.log("Registering Dependency Guard Agent on Devnet...");

  // Register the agent asset
  const agent = await sdk.registerAgent({
    name: "Dependency Guard Agent",
    symbol: "DEPGUARD",
    description: "Automated dependency safety and vulnerability audit agent",
    agentUri: "https://raw.githubusercontent.com/AqibTayyab/dependency-guard/main/agent-metadata.json",
  });

  console.log(JSON.stringify({
    status: "success",
    agentAsset: agent.asset ? agent.asset.toString() : agent.toString(),
    owner: kp.publicKey.toString()
  }, null, 2));
}

main().catch((e) => {
  console.error("Agent registration failed:", e.message);
  process.exit(1);
});
// SPDX-License-Identifier: Apache-2.0
// Reads a scan report (JSON) from stdin, writes a Memo transaction on Solana devnet,
// and prints {"signature": ..., "explorer_url": ...} as JSON.

const fs = require("fs");
const crypto = require("crypto");
const {
  Connection, Keypair, PublicKey, Transaction,
  TransactionInstruction, sendAndConfirmTransaction, clusterApiUrl,
} = require("@solana/web3.js");

const MEMO_PROGRAM_ID = new PublicKey("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr");

async function main() {
  const keyPath = process.env.DEPGUARD_KEYPAIR_PATH;
  if (!keyPath) throw new Error("Set DEPGUARD_KEYPAIR_PATH to your keypair file");

  const text = fs.readFileSync(0, "utf8").replace(/^\uFEFF/, "");
  const report = JSON.parse(text);
  const sha = report.report_sha256 || crypto.createHash("sha256").update(text).digest("hex");

  const secret = Uint8Array.from(JSON.parse(fs.readFileSync(keyPath, "utf8")));
  const kp = Keypair.fromSecretKey(secret);

  const s = report.summary || {};
  const memo = ["depguard:v1", `${report.ecosystem}:${report.input_file}`, s.verdict, s.score, sha].join(" | ");

  const ix = new TransactionInstruction({
    keys: [{ pubkey: kp.publicKey, isSigner: true, isWritable: false }],
    programId: MEMO_PROGRAM_ID,
    data: Buffer.from(memo, "utf8"),
  });

  const connection = new Connection(clusterApiUrl("devnet"), "confirmed");
  const signature = await sendAndConfirmTransaction(connection, new Transaction().add(ix), [kp]);

  console.log(JSON.stringify({
    signature,
    explorer_url: `https://explorer.solana.com/tx/${signature}?cluster=devnet`,
    memo,
  }));
}

main().catch((e) => { console.error("log-validation failed:", e.message); process.exit(1); });
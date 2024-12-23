import { fileURLToPath } from "url";
import path from "path";
import fs from "fs";
import {
  getLlama,
  LlamaChatSession
} from "node-llama-cpp";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  const llama = await getLlama();

  // 1. Load the model
  const modelPath = path.join(__dirname, "../models", "llama-2-7b-chat.Q4_K_M.gguf");
  if (!fs.existsSync(modelPath)) {
    console.log("Model file not found:", modelPath);
    return;
  }
  const model = await llama.loadModel({
    modelPath,
    nCtx: 1024,  // optionally set context window
    nThreads: 4, // optionally set CPU threads
    seed: 0,     // optional
  });

  // 2. Create a context & session
  const context = await model.createContext();
  const session = new LlamaChatSession({
    contextSequence: context.getSequence(),
  });

  // 3. Optionally define a grammar
  const grammar = await llama.createGrammarForJsonSchema({
    type: "object",
    properties: {
      greeting: { type: "string" },
      number:   { type: "number" },
    },
    required: ["greeting", "number"],
  });

  // 4. Send a prompt
  const prompt = "Hello, I'm John. It's a pleasure to meet you!";
  const outputText = await session.prompt(prompt, { grammar });
  console.log("Raw model output:", outputText);

  // 5. Parse the JSON if grammar was used
  try {
    const parsed = grammar.parse(outputText);
    console.log("Parsed JSON from model:", parsed);
  } catch (parseError) {
    console.error("Could not parse JSON from model output:", parseError);
  }
}

main().catch(console.error);

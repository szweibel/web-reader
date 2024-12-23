// test_langchain_with_llm.mjs
import path from "path";
import { fileURLToPath } from "url";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { getLlama, LlamaChatSession } from "node-llama-cpp";

// Figure out our current file & dir
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// dirname is actually up one level
const MODEL_DIR = path.join(__dirname, "..",);

// 1) Create a chat prompt with clear role markers and instructions
const systemPrompt = "You are a translator. You will receive text in {input_language} and respond with ONLY the translation in {output_language}. Do not add any explanations or additional text.";
const humanPrompt = "Translate this {input_language} text to {output_language}: {text}";
const chatPrompt = ChatPromptTemplate.fromMessages([
  ["system", systemPrompt],
  ["human", humanPrompt],
]);

async function runCustom() {
  // 2) Format the prompt with some input variables:
  const promptMessages = await chatPrompt.formatMessages({
    input_language: "English",
    output_language: "French",
    text: "I love programming.",
  });

  // 3) Point to the GGUF model file
  const modelPath = path.join(
    MODEL_DIR,
    "models",
    "llama-2-7b-chat.Q4_K_M.gguf"
  );

  const llama = await getLlama();
  const model = await llama.loadModel({
    modelPath,
    nCtx: 1024,
    nThreads: 4,
    seed: 0,
  });

  // 4) Create a context & chat session
  const context = await model.createContext();
  const session = new LlamaChatSession({
    contextSequence: context.getSequence(),
  });

  // 5) Format messages with clear role markers
  const formattedPrompt = promptMessages.map(msg => {
    if (msg.role === 'system') return `<|im_start|>system\n${msg.content}\n<|im_end|>`;
    if (msg.role === 'human') return `<|im_start|>user\n${msg.content}\n<|im_end|>`;
    return msg.content;
  }).join('\n') + '\n<|im_start|>assistant\n';
  
  const rawOutput = await session.prompt(formattedPrompt);
  console.log("LLM response:", rawOutput);
}

runCustom().catch(console.error);

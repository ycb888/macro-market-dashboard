import { readFile, rename, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const input = resolve(process.argv[2] || "data/market_news.json");
const snapshot = JSON.parse(await readFile(input, "utf8"));
const pending = snapshot.items.filter((item) => item.facts && !item.facts_zh && !item.translation_checked);
if (!pending.length) process.exit(0);

const { env, pipeline } = await import("@huggingface/transformers");
env.cacheDir = resolve(".model-cache");
const translate = await pipeline("translation", "Xenova/nllb-200-distilled-600M", {
  dtype: "q8",
  revision: "261c31d1a5732c67cdd16d80e8d6088507c7ccea",
});

function figures(text) {
  const normalized = text.normalize("NFKC").replace(/(\d),(?=\d{3}\b)/g, "$1");
  return new Set(normalized.match(/\d+(?:\.\d+)?/g) || []);
}

function checkedTranslation(source, result) {
  if (!result || !/[\u3400-\u9fff]/u.test(result) || result.length > 270) return null;
  const translatedFigures = figures(result);
  const sourceFigures = figures(source);
  if ([...sourceFigures].some((figure) => !translatedFigures.has(figure))
      || [...translatedFigures].some((figure) => !sourceFigures.has(figure))) return null;
  const foreignPhrases = result.match(/\b[A-Za-z]{2,}(?: +[A-Za-z]{2,}){2,}\b/g) || [];
  if (foreignPhrases.some((phrase) => !source.toLowerCase().includes(phrase.toLowerCase()))) return null;

  return result
    .replaceAll("联邦储备委员会", "美联储")
    .replaceAll("联邦开放市场委员会", "联邦公开市场委员会")
    .replaceAll("折扣贷款利率", "贴现贷款利率");
}

let translated = 0;
for (let start = 0; start < pending.length; start += 6) {
  const batch = pending.slice(start, start + 6);
  const output = await translate(batch.map((item) => item.facts), {
    src_lang: "eng_Latn", tgt_lang: "zho_Hans",
    max_new_tokens: 130, num_beams: 3, no_repeat_ngram_size: 4,
  });
  for (const [index, item] of batch.entries()) {
    const summary = checkedTranslation(item.facts, output[index]?.translation_text?.trim());
    if (summary) {
      item.facts_zh = summary;
      translated += 1;
    }
    item.translation_checked = true;
  }
}
const temporary = `${input}.tmp`;
await writeFile(temporary, JSON.stringify(snapshot, null, 2) + "\n", "utf8");
await rename(temporary, input);
console.log(`Chinese summaries generated: ${translated}/${pending.length}`);

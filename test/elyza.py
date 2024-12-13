import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

import torch
print(torch.cuda.is_available())

# 定数
DEFAULT_SYSTEM_PROMPT = "あなたは誠実で優秀な日本人のアシスタントです。特に指示が無い場合は、常に日本語で回答してください。"
text = "仕事の熱意を取り戻すためのアイデアを5つ挙げてください。"
model_name = "elyza/Llama-3-ELYZA-JP-8B"

# トークナイザーとモデルのロード
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,  # GPU向けに半精度を使用
    device_map="auto",          # GPUに自動割り当て
)

model.eval()  # 推論モードに設定

# プロンプトの設定
messages = [
    {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
    {"role": "user", "content": text},
]
prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

# 入力トークン化
token_ids = tokenizer.encode(
    prompt, add_special_tokens=False, return_tensors="pt"
).to("cuda")  # GPUに移動

# モデル推論
with torch.no_grad():
    output_ids = model.generate(
        token_ids,
        max_new_tokens=1200,
        do_sample=True,
        temperature=0.6,
        top_p=0.9,
    )

# 出力デコード
output = tokenizer.decode(
    output_ids.tolist()[0][token_ids.size(1):], skip_special_tokens=True
)

print(output)

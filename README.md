# 卒論のバックエンド

## 実行方法
```
pip install -r requirements.txt
```
```
uvicorn main:app --reload --host 127.0.0.1 --port 8888
```

## GPUの利用状況確認
```
watch -n 1 nvidia-smi
```

### APIの実験(curl)
```
curl -X POST "https://ibera.cps.akita-pu.ac.jp//conversion_with_elyza" \
-H "Content-Type: application/json" \
-d '{"text": "こんにちは、元気ですか？"}'
```

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from transformers import AutoModelForCausalLM, AutoTokenizer
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import pytz
import torch

app = FastAPI()

# 日本時間のタイムゾーンを設定
JST = pytz.timezone('Asia/Tokyo')

origins = [
    "http://localhost:5173",
    "http://localhost:8888",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8888",
    "https://ibera.cps.akita-pu.ac.jp"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 許可するオリジン
    allow_credentials=True,  # Cookieを許可する場合
    allow_methods=["*"],  # 許可するHTTPメソッド
    allow_headers=["*"],  # 許可するHTTPヘッダー
)

DATABASE_URL = "sqlite:///./comments.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    # タイムスタンプに日本時間を設定
    time = Column(DateTime, default=lambda: datetime.now(JST))
    page = Column(Integer, nullable=False)
    user = Column(String, nullable=False)
    user_comment = Column(Text, nullable=False)

    replies = relationship("Reply", back_populates="comment", cascade="all, delete-orphan")

class Reply(Base):
    __tablename__ = "replies"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False)
    # タイムスタンプに日本時間を設定
    time = Column(DateTime, default=lambda: datetime.now(JST))
    reply_user = Column(String, nullable=False)
    reply_user_comment = Column(Text, nullable=False)
    modified_reply_user_comment = Column(Text, nullable=False)

    comment = relationship("Comment", back_populates="replies")

Base.metadata.create_all(bind=engine)

class CommentRequest(BaseModel):
    page: int
    user: str
    user_comment: str

class ReplyRequest(BaseModel):
    comment_id: int
    reply_user: str
    reply_user_comment: str

class MessageRequest(BaseModel):
    text: str

class MessageResponse(BaseModel):
    modified_message: str

model_name = "elyza/Llama-3-ELYZA-JP-8B"
tokenizer = AutoTokenizer.from_pretrained(model_name)
if tokenizer.pad_token is None:
    tokenizer.add_special_tokens({'pad_token': '[PAD]'})

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="auto").to(device)
model.resize_token_embeddings(len(tokenizer))
model.eval()

def get_system_prompt():
    return (
        f"""
    あなたは寛容で優しいアシスタントです．
    以下の条件に従ってテキストを生成してください．

    \## 制約条件
    - 入力されたテキストは意味合いは変えない．
    - 入力されたテキストがユーザーに害を与える場合は優しい表現，違う表現に変更してください．
    - きつい表現，嫌味等を含んでいないと判断できる場合はそのまま出力してください．
    - 出力形式は，修正したテキストのみにしてください．
    """
    )

def get_few_shot_prompt(text):
    return (
        f"""
    以下は入力と出力の例です．それに従って回答してください．

    \## 出力例1 
    入力：あなたの考えは失敗するので私の考えが正しいです
    あなたの考えは失敗の可能性もあるので私の意見も参考にするといいと思います

    \## 出力例2
    入力：もっと深くまで読み込まないとダメだよ
    〇〇な奥深さがあって面白いよ

    \## 出力例3
    入力：お前アホ
    おまぬけさん

    - 出力形式は，修正したテキストのみにしてください．

    入力：{text}
    """
    )

def elyza(text):
    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": get_few_shot_prompt(text)},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    token_ids = tokenizer.encode(prompt, add_special_tokens=False, return_tensors="pt", max_length=512, truncation=True)
    with torch.no_grad():
        output_ids = model.generate(
            token_ids.to(device),
            max_new_tokens=512,
            do_sample=True,
            temperature=0.6,
            top_p=0.9,
        )
    return tokenizer.decode(output_ids.tolist()[0][token_ids.size(1):], skip_special_tokens=True)

def comment_to_frontend_format(c: Comment):
    return {
        "id": c.id,
        "username": c.user,
        "userid": f"@{c.user.lower()}",  # ユーザーIDを追加
        "text": c.user_comment,
        "timestamp": c.time.isoformat(),
        "replies": [
            {
                "username": r.reply_user,
                "userid": f"@{r.reply_user.lower()}",  # 返信ユーザーIDを追加
                "text": r.modified_reply_user_comment,
                "timestamp": r.time.isoformat()
            }
            for r in c.replies
        ],
        "showReplyForm": False,
        "replyText": ""
    }

@app.post("/comments")
def create_comment(request: CommentRequest):
    db = SessionLocal()
    try:
        new_comment = Comment(page=request.page, user=request.user, user_comment=request.user_comment)
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        frontend_comment = comment_to_frontend_format(new_comment)
        return {"message": "Comment created successfully", "comment": frontend_comment}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        db.close()

@app.get("/comments")
def get_all_comments():
    db = SessionLocal()
    try:
        comments = db.query(Comment).all()
        result = [comment_to_frontend_format(c) for c in comments]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        db.close()

@app.post("/replies")
def create_reply(request: ReplyRequest):
    db = SessionLocal()
    try:
        comment = db.query(Comment).filter(Comment.id == request.comment_id).first()
        if comment is None:
            raise HTTPException(status_code=404, detail="Comment not found")

        original_reply = elyza(request.reply_user_comment)

        new_reply = Reply(
            comment_id=request.comment_id,
            reply_user=request.reply_user,
            reply_user_comment=request.reply_user_comment,
            modified_reply_user_comment=original_reply
        )
        db.add(new_reply)
        db.commit()
        db.refresh(new_reply)

        updated_comment = db.query(Comment).filter(Comment.id == request.comment_id).first()
        frontend_comment = comment_to_frontend_format(updated_comment)

        return {"message": "Reply created successfully", "comment": frontend_comment}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        db.close()

@app.post("/conversion_with_elyza", response_model=MessageResponse)
def conversion_with_elyza(request: MessageRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    modified_message = elyza(request.text)
    return MessageResponse(modified_message=modified_message)

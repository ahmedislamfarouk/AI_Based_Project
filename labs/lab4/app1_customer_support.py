import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_openai import ChatOpenAI

# 1. Vectorization (3 Knowledge Bases)
loader = DirectoryLoader('./knowledge', glob="./*.txt", loader_cls=TextLoader)
docs = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)
vector_db = FAISS.from_documents(chunks, HuggingFaceEmbeddings())

# 2. Memory & LLM
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, output_key="answer")
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

# 3. Retrieval Chain
qa = ConversationalRetrievalChain.from_llm(llm, vector_db.as_retriever(), memory=memory)

# 4. Specialized Tools (Functions)
def track_order(order_id): return f"Order {order_id}: In Transit"
def check_stock(item): return f"Item '{item}': Available"

# Usage
if __name__ == "__main__":
    query = "What is the return policy?"
    ans = qa.invoke({"question": query})
    print(f"Response: {ans['answer']}")
